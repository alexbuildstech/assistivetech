"""
Advanced Voice Control Module for Assistive Navigation.
Uses Groq Whisper for STT and Edge-TTS for high-quality speech synthesis.
Based on nova/novastt.py implementation.
"""

import sounddevice as sd
import numpy as np
import io
import wave
import threading
import asyncio
from groq import Groq
from edge_tts import Communicate
import subprocess
import shutil
import config
import re
import os

from conversation_manager import ConversationManager


class VoiceController:
    """
    Advanced voice controller with:
    - Groq Whisper (whisper-large-v3-turbo) for STT
    - Edge-TTS for natural speech synthesis
    - C/S key control for recording
    """

    GROQ_API_KEY = getattr(config, 'GROQ_API_KEY', None)
    EDGE_VOICE = "en-US-AndrewNeural"
    EDGE_RATE = "+15%"

    STT_SAMPLERATE = 16000
    STT_CHANNELS = 1
    STT_CHUNK = 2048
    STT_DTYPE = "int16"

    def __init__(self):
        self.is_recording = False
        self.stream = None
        self.wave_file = None
        self.audio_buffer = None
        self.transcribed_text = None
        self.transcription_ready = threading.Event()

        self.conversation_manager = ConversationManager()
        self.listener = None
        self.recording_active = True
        self.last_key_time = 0

        self._recording_lock = threading.Lock()
        self._tts_lock = threading.Lock()
        self._tts_generation = 0
        self.current_mpv_process = None
        self.current_tts_generation = None
        self._shutdown = threading.Event()
        self._tts_thread = None
        self.chat_persona_enabled = getattr(config, 'ENABLE_CHAT_PERSONA', False)

        self.groq_client = self._initialize_groq_client()
        self.gemini_chat_client = self._initialize_gemini_chat() if self.chat_persona_enabled else None
        self.player_command = self._get_player_command()
        self.tts_temp_dir = "/dev/shm" if os.path.exists("/dev/shm") else "/tmp"

        print("[VOICE] Advanced VoiceController initialized")
        print(f"   STT: Groq Whisper ({config.WHISPER_MODEL})")
        print(f"   TTS: Edge-TTS ({self.EDGE_VOICE})")
        print(f"   Chat persona: {'enabled' if self.chat_persona_enabled else 'disabled'}")
        print("   History: conversation_history.json")
        print("   Controls: Call start_recording() and stop_recording() directly")

    def _initialize_groq_client(self):
        if not self.GROQ_API_KEY:
            print("[ERROR] GROQ_API_KEY not set. Voice recognition disabled.")
            return None

        try:
            client = Groq(api_key=self.GROQ_API_KEY)
            client.models.list()
            print("[VOICE] Groq client initialized successfully")
            return client
        except Exception as e:
            print(f"[ERROR] Failed to initialize Groq client: {e}")
            return None

    def _initialize_gemini_chat(self):
        try:
            from google import genai
            return genai.Client(api_key=config.API_KEY)
        except Exception as e:
            print(f"[ERROR] Failed to initialize Gemini for chat: {e}")
            return None

    def _get_player_command(self):
        if shutil.which("mpv"):
            return ["mpv", "--no-terminal", "--audio-buffer=1.0", "--keep-open=no", "-"]
        if shutil.which("ffplay"):
            return ["ffplay", "-nodisp", "-autoexit", "-loglevel", "warning", "-fflags", "nobuffer", "-i", "-"]
        if shutil.which("mpg123"):
            return ["mpg123", "-q", "--buffer", "8192", "-"]
        print("[WARNING] No audio player found (install mpv, ffmpeg, or mpg123)")
        return None

    def start_recording(self):
        with self._recording_lock:
            if self.is_recording:
                print("[WARNING] Already recording")
                return False

            if not self.groq_client:
                print("[ERROR] Groq client not initialized. Cannot record.")
                return False

            if self._shutdown.is_set():
                return False

            print("[VOICE] Recording started (press 'S' to stop)")
            self.transcription_ready.clear()
            self.audio_buffer = io.BytesIO()
            self.wave_file = wave.open(self.audio_buffer, "wb")
            self.wave_file.setnchannels(self.STT_CHANNELS)
            self.wave_file.setsampwidth(np.dtype(self.STT_DTYPE).itemsize)
            self.wave_file.setframerate(self.STT_SAMPLERATE)
            self.is_recording = True

        def audio_callback(indata, frames, time, status):
            if status:
                print(f"Audio status: {status}")
            with self._recording_lock:
                if self.is_recording and self.wave_file and not self._shutdown.is_set():
                    self.wave_file.writeframes(indata.tobytes())

        try:
            self.stream = sd.InputStream(
                samplerate=self.STT_SAMPLERATE,
                blocksize=self.STT_CHUNK,
                dtype=self.STT_DTYPE,
                channels=self.STT_CHANNELS,
                callback=audio_callback
            )
            self.stream.start()
            return True
        except Exception as e:
            print(f"[ERROR] Failed to start recording: {e}")
            with self._recording_lock:
                self.is_recording = False
                self._close_recording_resources_locked()
                self.audio_buffer = None
            return False

    def _close_recording_resources_locked(self):
        if self.stream:
            try:
                self.stream.stop()
            except Exception:
                pass
            try:
                self.stream.close()
            except Exception:
                pass
            self.stream = None

        if self.wave_file:
            try:
                self.wave_file.close()
            except Exception:
                pass
            self.wave_file = None

    def _close_recording_resources(self):
        with self._recording_lock:
            self._close_recording_resources_locked()

    def stop_recording(self):
        with self._recording_lock:
            if not self.is_recording:
                return None

            self.is_recording = False
            print("[VOICE] Recording stopped")
            self._close_recording_resources_locked()

            if not self.audio_buffer:
                return None

            print("[VOICE] Transcribing...")
            try:
                self.audio_buffer.seek(0)
                audio_data = self.audio_buffer.read()
            finally:
                self.audio_buffer = None

        if not audio_data or self._shutdown.is_set():
            return None

        return self._transcribe_audio_sync(audio_data)

    def _transcribe_audio_sync(self, audio_data):
        if self._shutdown.is_set() or not self.groq_client:
            return None
        try:
            transcription = self.groq_client.audio.transcriptions.create(
                file=("audio.wav", audio_data),
                model=config.WHISPER_MODEL,
                language="en",
                timeout=20
            )
            if self._shutdown.is_set():
                return None
            text = transcription.text.strip()
            print(f"[VOICE] Transcription: {text}")
            return text
        except Exception as e:
            print(f"[ERROR] Transcription error: {e}")
            return None

    def listen(self):
        self.transcribed_text = None
        print("[VOICE] Waiting for voice input (press 'C' to record, 'S' to stop)...")

        while self.transcribed_text is None:
            if not self.recording_active:
                return None
            threading.Event().wait(0.1)

        result = self.transcribed_text
        self.transcribed_text = None
        return result.lower() if result else None

    def stop_speaking(self):
        with self._tts_lock:
            self._tts_generation += 1
            process = self.current_mpv_process
            self.current_mpv_process = None
            self.current_tts_generation = None
        if process and process.poll() is None:
            try:
                print("[VOICE] Stopping TTS playback...")
                process.terminate()
                try:
                    process.wait(timeout=0.3)
                except subprocess.TimeoutExpired:
                    process.kill()
            except Exception as e:
                print(f"[WARNING] Error stopping TTS: {e}")

    def speak(self, text, async_mode=True):
        if not text or not text.strip() or self._shutdown.is_set():
            return

        text = re.sub(r'[\U00010000-\U0010ffff]', '', text)
        if not text.strip():
            return

        self.conversation_manager.add_turn("assistant", text)
        self.stop_speaking()
        with self._tts_lock:
            generation = self._tts_generation

        if async_mode:
            self._tts_thread = threading.Thread(target=self._speak_sync, args=(text, generation), daemon=True)
            self._tts_thread.start()
        else:
            self._speak_sync(text, generation)

    def _speak_sync(self, text, generation):
        try:
            asyncio.run(self._async_speak(text, generation))
        except Exception as e:
            print(f"❌ TTS error: {e}")
        finally:
            with self._tts_lock:
                if self.current_tts_generation == generation:
                    self.current_tts_generation = None
                    self.current_mpv_process = None
                if self._tts_thread and not self._tts_thread.is_alive():
                    self._tts_thread = None

    def _build_stream_player_command(self):
        if shutil.which("mpv"):
            return ["mpv", "--no-terminal", "--vo=null", "--audio-buffer=0", "--cache=no", "--demuxer-max-bytes=128k", "--volume=100", "-"]
        if shutil.which("ffplay"):
            return ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", "-fflags", "nobuffer", "-i", "pipe:0"]
        return None

    def _close_player_process(self, process, generation):
        if process and process.stdin:
            try:
                process.stdin.close()
            except Exception:
                pass
        if process:
            try:
                process.wait(timeout=1)
            except Exception:
                pass
        with self._tts_lock:
            if self.current_tts_generation == generation:
                self.current_mpv_process = None
                self.current_tts_generation = None

    async def _async_speak(self, text, generation):
        try:
            raw_tokens = re.split(r'(#PAUSE\([\d\.]+\))', text)
            chunks = [s for s in raw_tokens if s.strip()]

            final_chunks = []
            for chunk in chunks:
                if re.match(r'#PAUSE\(([\d\.]+)\)', chunk):
                    final_chunks.append(chunk)
                else:
                    final_chunks.extend([s for s in re.split(r'(?<=[.!?])\s+', chunk) if s.strip()])

            print(f"[TTS] Streaming TTS: Split into {len(final_chunks)} chunks")

            for i, chunk in enumerate(final_chunks):
                with self._tts_lock:
                    if self._shutdown.is_set() or generation != self._tts_generation:
                        break

                pause_match = re.match(r'#PAUSE\(([\d\.]+)\)', chunk)
                if pause_match:
                    await asyncio.sleep(float(pause_match.group(1)))
                    continue

                if not chunk.strip():
                    continue

                cmd = self._build_stream_player_command()
                if not cmd:
                    print("[WARNING] No audio player found for streaming.")
                    break

                process = subprocess.Popen(
                    cmd,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                abort_process = False
                with self._tts_lock:
                    if self._shutdown.is_set() or generation != self._tts_generation:
                        abort_process = True
                    else:
                        self.current_mpv_process = process
                        self.current_tts_generation = generation
                if abort_process:
                    if process.poll() is None:
                        process.terminate()
                    self._close_player_process(process, generation)
                    break

                retries = 2
                while retries > 0:
                    with self._tts_lock:
                        if self._shutdown.is_set() or generation != self._tts_generation:
                            retries = 0
                            break
                    try:
                        print(f"[TTS] Starting stream for chunk {i}: '{chunk[:20]}...' (Retries: {2 - retries})")
                        communicate = Communicate(chunk, self.EDGE_VOICE, rate=self.EDGE_RATE)
                        chunk_count = 0
                        async for chunk_data in communicate.stream():
                            with self._tts_lock:
                                if self._shutdown.is_set() or generation != self._tts_generation:
                                    chunk_count = None
                                    break
                                active_process = self.current_mpv_process if self.current_tts_generation == generation else None
                            if chunk_data["type"] == "audio" and active_process and active_process.stdin:
                                chunk_count += 1
                                try:
                                    active_process.stdin.write(chunk_data["data"])
                                    active_process.stdin.flush()
                                except (BrokenPipeError, IOError):
                                    print(f"[WARNING] Player stdin broken at chunk {chunk_count}")
                                    break

                        if chunk_count is not None:
                            print(f"[TTS] Stream complete for chunk {i} ({chunk_count} audio chunks)")
                        break
                    except Exception as e:
                        retries -= 1
                        print(f"[WARNING] Streaming retry {2 - retries} due to: {e}")
                        if retries == 0:
                            print(f"[ERROR] Failed to stream chunk {i} after multiple attempts.")
                        await asyncio.sleep(0.5)

                self._close_player_process(process, generation)
        except Exception as e:
            print(f"[ERROR] Edge-TTS streaming error: {e}")
            with self._tts_lock:
                process = self.current_mpv_process if self.current_tts_generation == generation else None
            self._close_player_process(process, generation)

    def chat_with_nova(self, text):
        if not self.chat_persona_enabled:
            self.speak("Chat mode is disabled right now. Ask me to track, describe, read, or find something.", async_mode=True)
            return

        if not self.gemini_chat_client:
            self.speak("I'm having trouble connecting to my brain.", async_mode=True)
            return

        print(f"[AI] Processing: '{text}'")
        context = self.conversation_manager.get_context_string(limit=5)
        full_prompt = f"""
        [Conversation History]
        {context}

        [User's Current Input]
        User: {text}

        Reply as Nova (witty, helpful, concise).
        """

        try:
            response = self.gemini_chat_client.models.generate_content(
                model=config.GENERAL_CHAT_MODEL,
                contents=full_prompt,
                config={
                    "system_instruction": config.NOVA_SYSTEM_PROMPT,
                    "temperature": 0.7,
                    "max_output_tokens": 100,
                }
            )
            reply = response.text.strip()
            print(f"[AI] Response: {reply}")
            self.speak(reply, async_mode=True)
        except Exception as e:
            print(f"[ERROR] Chat error: {e}")
            self.speak("Sorry, I encountered an error processing your request.", async_mode=True)

    def parse_command(self, text):
        if not text:
            return None

        self.conversation_manager.add_turn("user", text)
        print(f"[VOICE] Processing input: '{text}'")
        lower_text = text.lower()

        if "describe" in lower_text and ("scene" in lower_text or "surroundings" in lower_text or "around" in lower_text):
            print("[VOICE] Command Detected: Describe Scene")
            return {"intent": "describe_scene"}

        visual_keywords = [
            "see", "look", "what is this", "read", "identify",
            "what's this", "whats this", "tell me what", "what do you think",
            "try again", "again", "better view", "different", "use your visual",
            "use the visual", "check", "analyze", "examine"
        ]
        if any(w in lower_text for w in visual_keywords):
            print("[VOICE] Fast Path: Visual Query detected")
            return {"intent": "visual_qa", "params": {"question": text}}

        match = re.search(r"(track|find|follow|locate|search for)\s+(?:the\s+)?(.+)", lower_text)
        if match:
            obj_name = re.sub(r'[^\w\s]', '', match.group(2).strip())
            print(f"[VOICE] Command Detected: Track '{obj_name}'")
            return {"intent": "track_object", "params": {"object": obj_name}}

        if "navigation" in lower_text or "track mode" in lower_text:
            return {"intent": "mode_navigation"}
        if "obstacle" in lower_text or "avoid" in lower_text:
            return {"intent": "mode_obstacle"}
        if "social" in lower_text or "people" in lower_text:
            return {"intent": "mode_social"}
        if "explore" in lower_text or "exploration" in lower_text:
            return {"intent": "mode_exploration"}

        if "stop" in lower_text or "quit" in lower_text or "cancel" in lower_text:
            if "tracking" in lower_text or lower_text == "stop":
                return {"intent": "stop_tracking"}
            if "quit" in lower_text:
                return {"intent": "quit"}

        if "help" in lower_text or "what can you do" in lower_text:
            return {"intent": "help"}

        recall_match = re.search(r"(where('?s| is| are)( my| the)?|have you seen( my)?|last saw)\s+(.+?)(\?|$)", lower_text)
        if recall_match:
            obj_name = re.sub(r'[^\w\s]', '', recall_match.group(5).strip())
            print(f"[VOICE] Command Detected: Recall '{obj_name}'")
            return {"intent": "recall_object", "params": {"object": obj_name}}

        if not self.chat_persona_enabled:
            return {
                "intent": "direct_response",
                "params": {"response": "Chat mode is disabled right now. Ask me to track, describe, read, or find something."}
            }

        if not self.gemini_chat_client:
            return {"intent": "unknown"}

        try:
            context = self.conversation_manager.get_context_string(limit=5)
            full_prompt = f"""
            [Conversation History]
            {context}

            [User's Current Input]
            User: {text}

            INSTRUCTIONS:
            1. If the user's input requires seeing the current camera feed, reply with EXACTLY: VISUAL_QUERY
            2. If the user's input is general chat, reply as Nova.
            """

            response = self.gemini_chat_client.models.generate_content(
                model=config.GENERAL_CHAT_MODEL,
                contents=full_prompt,
                config={
                    "system_instruction": config.NOVA_SYSTEM_PROMPT,
                    "temperature": 0.7,
                    "max_output_tokens": 150,
                }
            )
            reply = response.text.strip()

            if "VISUAL_QUERY" in reply:
                print("[VOICE] Route: VISUAL_QUERY (Detected by Chat Model)")
                return {"intent": "visual_qa", "params": {"question": text}}

            print("[VOICE] Route: CHAT (Direct Response)")
            print(f"[AI] Response: {reply}")
            return {"intent": "direct_response", "params": {"response": reply}}
        except Exception as e:
            print(f"[ERROR] Routing error: {e}")
            return {"intent": "unknown"}

    def get_help_text(self):
        return "I'm Nova. You can ask me to track objects, describe the scene, read text, or find something. Press C to talk."

    def close(self):
        self.recording_active = False
        self._shutdown.set()
        self.stop_speaking()
        tts_thread = self._tts_thread
        if tts_thread and tts_thread.is_alive() and tts_thread is not threading.current_thread():
            tts_thread.join(timeout=1.0)
        self._close_recording_resources()
        with self._recording_lock:
            self.audio_buffer = None
            self.is_recording = False

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass
