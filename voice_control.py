"""
Advanced Voice Control Module for Assistive Navigation.
Uses Groq Whisper for STT and Edge-TTS for high-quality speech synthesis.
Based on nova/novastt.py implementation.
"""

import sounddevice as sd
from pynput import keyboard
import numpy as np
import io
import wave
import threading
import asyncio
import time
import random
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
    
    # API Configuration
    GROQ_API_KEY = getattr(config, 'GROQ_API_KEY', None)
    EDGE_VOICE = "en-US-AndrewNeural"  # Faster, lower latency voice
    EDGE_RATE = "+15%"  # Faster for responsiveness
    
    # Audio settings for STT (Whisper Native)
    STT_SAMPLERATE = 16000  # Whisper is trained on 16kHz - higher rates degrade accuracy
    STT_CHANNELS = 1
    STT_CHUNK = 2048       # Reduced for latency
    STT_DTYPE = "int16"    # Standard for speech
    
    def __init__(self):
        """Initialize advanced voice controller."""
        # STT state
        self.is_recording = False
        self.stream = None
        self.wave_file = None
        self.audio_buffer = None
        self.transcribed_text = None
        self.transcription_ready = threading.Event()
        
        # History Manager
        self.conversation_manager = ConversationManager()
        
        # Keyboard listener - DISABLED (conflicts with OpenCV waitKey)
        self.listener = None
        self.recording_active = True
        self.last_key_time = 0  # Debounce for key presses
        
        # Initialize clients
        self.groq_client = self._initialize_groq_client()
        self.gemini_chat_client = self._initialize_gemini_chat()
        
        # TTS player command
        self.player_command = self._get_player_command()
        
        # TTS Temp Directory (Use RAM disk if available for speed)
        self.tts_temp_dir = "/dev/shm" if os.path.exists("/dev/shm") else "/tmp"
        
        print("[VOICE] Advanced VoiceController initialized")
        print(f"   STT: Groq Whisper (whisper-large-v3-turbo)")
        print(f"   TTS: Edge-TTS ({self.EDGE_VOICE})")
        print(f"   History: conversation_history.json")
        print(f"   Controls: Call start_recording() and stop_recording() directly")

    def _initialize_groq_client(self):
        """Initialize Groq API client for Whisper STT."""
        if not self.GROQ_API_KEY:
            print("[ERROR] GROQ_API_KEY not set. Voice recognition disabled.")
            return None
        
        try:
            client = Groq(api_key=self.GROQ_API_KEY)
            # Test connection
            client.models.list()
            print("[VOICE] Groq client initialized successfully")
            return client
        except Exception as e:
            print(f"[ERROR] Failed to initialize Groq client: {e}")
            return None
    
    def _get_player_command(self):
        """Detect available audio player."""
        if shutil.which("mpv"):
            # Increased buffer and disabled terminal output to prevent stuttering
            return ["mpv", "--no-terminal", "--audio-buffer=1.0", "--keep-open=no", "-"]
        elif shutil.which("ffplay"):
            return ["ffplay", "-nodisp", "-autoexit", "-loglevel", "warning", 
                   "-fflags", "nobuffer", "-i", "-"]
        elif shutil.which("mpg123"):
            return ["mpg123", "-q", "--buffer", "8192", "-"]
        else:
            print("[WARNING] No audio player found (install mpv, ffmpeg, or mpg123)")
            return None
    
    def start_recording(self):
        """Start recording audio - PUBLIC method for direct calls."""
        if self.is_recording:
            print("[WARNING] Already recording")
            return False
        
        if not self.groq_client:
            print("[ERROR] Groq client not initialized. Cannot record.")
            return False
        
        self.is_recording = True
        self.transcription_ready.clear()
        print("[VOICE] Recording started (press 'S' to stop)")
        
        # Initialize audio buffer
        self.audio_buffer = io.BytesIO()
        self.wave_file = wave.open(self.audio_buffer, "wb")
        self.wave_file.setnchannels(self.STT_CHANNELS)
        self.wave_file.setsampwidth(np.dtype(self.STT_DTYPE).itemsize)
        self.wave_file.setframerate(self.STT_SAMPLERATE)
        
        def audio_callback(indata, frames, time, status):
            if status:
                print(f"Audio status: {status}")
            if self.is_recording and self.wave_file:
                self.wave_file.writeframes(indata.tobytes())
        
        # Start audio stream
        self.stream = sd.InputStream(
            samplerate=self.STT_SAMPLERATE,
            blocksize=self.STT_CHUNK,
            dtype=self.STT_DTYPE,
            channels=self.STT_CHANNELS,
            callback=audio_callback
        )
        self.stream.start()
        return True
    
    def stop_recording(self):
        """Stop recording and transcribe - PUBLIC method that waits for transcription."""
        if not self.is_recording:
            return None
        
        self.is_recording = False
        print("[VOICE] Recording stopped")
        
        # Stop stream
        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None
        
        # Close wave file
        if self.wave_file:
            self.wave_file.close()
            self.wave_file = None
        
        print("[VOICE] Transcribing...")
        
        # Get audio data
        self.audio_buffer.seek(0)
        audio_data = self.audio_buffer.read()
        
        # Transcribe synchronously for lower latency (no thread overhead)
        return self._transcribe_audio_sync(audio_data)
    
    def _transcribe_audio_sync(self, audio_data):
        """Transcribe audio using Groq Whisper synchronously for lowest latency."""
        try:
            transcription = self.groq_client.audio.transcriptions.create(
                file=("audio.wav", audio_data),
                model="whisper-large-v3-turbo",
                language="en"
            )
            
            text = transcription.text.strip()
            print(f"[VOICE] Transcription: {text}")
            return text
            
        except Exception as e:
            print(f"[ERROR] Transcription error: {e}")
            return None
    
    def _initialize_gemini_chat(self):
        """Initialize Gemini client for general chat."""
        try:
            from google import genai
            client = genai.Client(api_key=config.API_KEY)
            return client
        except Exception as e:
            print(f"[ERROR] Failed to initialize Gemini for chat: {e}")
            return None

    # Keyboard listener REMOVED - conflicts with OpenCV's waitKey()
    # Use start_recording() and stop_recording() directly instead

    def listen(self):
        """
        Blocking wait for voice input.
        Returns transcribed text when available.
        """
        # Clear previous transcription
        self.transcribed_text = None
        
        print("[VOICE] Waiting for voice input (press 'C' to record, 'S' to stop)...")
        
        # Wait for transcription to appear
        while self.transcribed_text is None:
            if not self.recording_active:
                return None
            threading.Event().wait(0.1)
        
        result = self.transcribed_text
        self.transcribed_text = None  # Clear for next use
        return result.lower() if result else None

    def stop_speaking(self):
        """Stop any ongoing TTS playback immediately."""
        self._stop_requested = True
        # Kill the mpv/ffplay process if it's running
        process = getattr(self, 'current_mpv_process', None)
        if process and process.poll() is None:
            try:
                print("[VOICE] Stopping TTS playback...")
                process.terminate()
                try:
                    process.wait(timeout=0.3) # Faster timeout for real-time
                except subprocess.TimeoutExpired:
                    process.kill()
            except Exception as e:
                print(f"[WARNING] Error stopping TTS: {e}")
        
        self.current_mpv_process = None

    def speak(self, text, async_mode=True):
        """
        Speak text using Edge-TTS with robust streaming playback.
        Supports #PAUSE(x) tokens.
        """
        if not text or not text.strip():
            return
        
        self._stop_requested = False # Reset flag for new playback
        
        # Add to history
        self.conversation_manager.add_turn("assistant", text)
        
        # Filter out emojis
        text = re.sub(r'[\U00010000-\U0010ffff]', '', text)
        
        # Stop any currently playing audio before starting new one
        self.stop_speaking()
        
        self._stop_requested = False # Reset flag for new playback AFTER stopping previous
        
        if async_mode:
            threading.Thread(
                target=self._speak_sync,
                args=(text,),
                daemon=True
            ).start()
        else:
            self._speak_sync(text)

    def _speak_sync(self, text):
        """Synchronous TTS wrapper."""
        try:
            asyncio.run(self._async_speak(text))
        except Exception as e:
            print(f"❌ TTS error: {e}")

    async def _async_speak(self, text):
        """
        Async TTS: High-performance streaming with sentence splitting and #PAUSE support.
        Pipes audio directly to the player for minimal latency (No disk I/O).
        """
        try:
            # 1. Parse tokens (#PAUSE and Sentences)
            # First split by #PAUSE tokens
            raw_tokens = re.split(r'(#PAUSE\([\d\.]+\))', text)
            
            # Further split non-pause tokens into sentences to start speaking faster
            chunks = [s for s in raw_tokens if s.strip()] # Filter empty
            
            # Simple splitter for now
            final_chunks = []
            for chunk in chunks:
                if re.match(r'#PAUSE\(([\d\.]+)\)', chunk):
                    final_chunks.append(chunk)
                else:
                    sentences = re.split(r'(?<=[.!?])\s+', chunk)
                    final_chunks.extend([s for s in sentences if s.strip()])
            
            print(f"[TTS] Streaming TTS: Split into {len(final_chunks)} chunks")

            for i, chunk in enumerate(final_chunks):
                # Check for interrupted flag or new playback
                if hasattr(self, '_stop_requested') and self._stop_requested:
                    break

                pause_match = re.match(r'#PAUSE\(([\d\.]+)\)', chunk)
                if pause_match:
                    duration = float(pause_match.group(1))
                    await asyncio.sleep(duration)
                    continue

                if not chunk.strip():
                    continue

                # 2. Detect optimal player command
                cmd = None
                if shutil.which("mpv"):
                    # Ultra-low latency mpv config
                    cmd = ["mpv", "--no-terminal", "--vo=null", "--audio-buffer=0", 
                           "--cache=no", "--demuxer-max-bytes=128k", "--volume=100", "-"]
                elif shutil.which("ffplay"):
                    cmd = ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", 
                           "-fflags", "nobuffer", "-i", "pipe:0"]
                
                if not cmd:
                    print("[WARNING] No audio player found for streaming.")
                    break

                # 3. Start player process
                # Increase demuxer-thread-priority for smooth streaming
                self.current_mpv_process = subprocess.Popen(
                    cmd,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                
                # 4. Stream from Edge-TTS directly to player stdin with retries
                retries = 2
                while retries > 0:
                    try:
                        print(f"[TTS] Starting stream for chunk {i}: '{chunk[:20]}...' (Retries: {2-retries})")
                        communicate = Communicate(chunk, self.EDGE_VOICE, rate=self.EDGE_RATE)
                        chunk_count = 0
                        async for chunk_data in communicate.stream():
                            if chunk_data["type"] == "audio":
                                chunk_count += 1
                                if self.current_mpv_process and self.current_mpv_process.stdin:
                                    try:
                                        self.current_mpv_process.stdin.write(chunk_data["data"])
                                        self.current_mpv_process.stdin.flush()
                                    except (BrokenPipeError, IOError):
                                        print(f"[WARNING] Player stdin broken at chunk {chunk_count}")
                                        break
                        
                        print(f"[TTS] Stream complete for chunk {i} ({chunk_count} audio chunks)")
                        break # Success
                    except Exception as e:
                        retries -= 1
                        print(f"[WARNING] Streaming retry {2-retries} due to: {e}")
                        if retries == 0:
                            print(f"[ERROR] Failed to stream chunk {i} after multiple attempts.")
                        await asyncio.sleep(0.5)
                
                # 5. Wait for playback to finish
                if self.current_mpv_process and self.current_mpv_process.stdin:
                    try:
                        self.current_mpv_process.stdin.close()
                        self.current_mpv_process.wait()
                    except:
                        pass
                self.current_mpv_process = None
                    
        except Exception as e:
            print(f"[ERROR] Edge-TTS streaming error: {e}")

    def chat_with_nova(self, text):
        """
        Send text to Gemini (Nova persona) for general conversation.
        Includes conversation history for context.
        """
        if not self.gemini_chat_client:
            self.speak("I'm having trouble connecting to my brain.", async_mode=True)
            return

        print(f"[AI] Processing: '{text}'")
        
        # Get context
        context = self.conversation_manager.get_context_string(limit=5)
        full_prompt = f"""
        [Conversation History]
        {context}
        
        [User's Current Input]
        User: {text}
        
        Reply as Nova (witty, helpful, concise).
        """
        
        try:
            # Use the new Google GenAI SDK format
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
        """
        Parse voice command using Gemini (Chat-First Routing).
        The Chat Model decides if it needs to see (VISUAL_QUERY) or just chat.
        """
        if not text:
            return None
        
        # Add to history
        self.conversation_manager.add_turn("user", text)
        print(f"[VOICE] Processing input: '{text}'")
        
        # FAST PATH: Check for explicit visual keywords to save latency
        # (Still useful for obvious cases)
        lower_text = text.lower()
        visual_keywords = [
            "see", "look", "what is this", "describe", "read", "identify",
            "what's this", "whats this", "tell me what", "what do you think",
            "try again", "again", "better view", "different", "use your visual",
            "use the visual", "check", "analyze", "examine"
        ]
        if any(w in lower_text for w in visual_keywords):
            print("[VOICE] Fast Path: Visual Query detected")
            return {"intent": "visual_qa", "params": {"question": text}}

        # COMMAND PATH: Check for specific navigation/system commands
        # 1. Track/Find Object
        match = re.search(r"(track|find|follow|locate|search for)\s+(?:the\s+)?(.+)", lower_text)
        if match:
            obj_name = match.group(2).strip()
            # Remove punc
            obj_name = re.sub(r'[^\w\s]', '', obj_name)
            print(f"[VOICE] Command Detected: Track '{obj_name}'")
            return {"intent": "track_object", "params": {"object": obj_name}}
        
        # 2. Mode Operations
        if "navigation" in lower_text or "track mode" in lower_text:
            return {"intent": "mode_navigation"}
        elif "obstacle" in lower_text or "avoid" in lower_text:
            return {"intent": "mode_obstacle"}
        elif "social" in lower_text or "people" in lower_text:
            return {"intent": "mode_social"}
        elif "explore" in lower_text or "exploration" in lower_text:
            return {"intent": "mode_exploration"}
        
        # 3. Stop/Reset
        if "stop" in lower_text or "quit" in lower_text or "cancel" in lower_text:
             if "tracking" in lower_text or "stop" == lower_text:
                 return {"intent": "stop_tracking"}
             if "quit" in lower_text:
                 return {"intent": "quit"}

        # 4. Help
        if "help" in lower_text or "what can you do" in lower_text:
            return {"intent": "help"}

        # SLOW PATH: Ask Gemini (Chat Model)
        # It will reply with "VISUAL_QUERY" if it needs vision, or the actual chat response.
        if not self.gemini_chat_client:
            return {"intent": "chat_with_nova", "params": {"text": text}}

        try:
            # Get context
            context = self.conversation_manager.get_context_string(limit=5)
            full_prompt = f"""
            [Conversation History]
            {context}
            
            [User's Current Input]
            User: {text}
            
            INSTRUCTIONS:
            1. If the user's input requires seeing the current camera feed (e.g. "what is this?", "describe the scene", "try again", "read this"), reply with EXACTLY: VISUAL_QUERY
            2. If the user's input is general chat, a joke request, or a question NOT requiring vision, reply as Nova (witty, direct).
            
            Do NOT output VISUAL_QUERY for general conversation.
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
            
            # Check for Visual Query Token
            if "VISUAL_QUERY" in reply:
                print("[VOICE] Route: VISUAL_QUERY (Detected by Chat Model)")
                return {"intent": "visual_qa", "params": {"question": text}}
            
            # Otherwise, it's a normal chat response
            print(f"[VOICE] Route: CHAT (Direct Response)")
            print(f"[AI] Response: {reply}")
            
            # Return as direct response so we don't call Gemini again
            return {"intent": "direct_response", "params": {"response": reply}}
            
        except Exception as e:
            print(f"[ERROR] Routing error: {e}")
            return {"intent": "chat_with_nova", "params": {"text": text}}

    def get_help_text(self):
        """Return help text for voice commands."""
        return "I'm Nova. You can ask me to track objects, describe the scene, read text, or just chat. Press C to talk."
