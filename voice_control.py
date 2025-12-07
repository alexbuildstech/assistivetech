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
import random

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
        
        print("🔊 Advanced VoiceController initialized")
        print(f"   STT: Groq Whisper (whisper-large-v3-turbo)")
        print(f"   TTS: Edge-TTS ({self.EDGE_VOICE})")
        print(f"   History: conversation_history.json")
        print(f"   Controls: Call start_recording() and stop_recording() directly")

    def _initialize_groq_client(self):
        """Initialize Groq API client for Whisper STT."""
        if not self.GROQ_API_KEY:
            print("❌ GROQ_API_KEY not set. Voice recognition disabled.")
            return None
        
        try:
            client = Groq(api_key=self.GROQ_API_KEY)
            # Test connection
            client.models.list()
            print("✅ Groq client initialized successfully")
            return client
        except Exception as e:
            print(f"❌ Failed to initialize Groq client: {e}")
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
            print("⚠️ No audio player found (install mpv, ffmpeg, or mpg123)")
            return None
    
    def start_recording(self):
        """Start recording audio - PUBLIC method for direct calls."""
        if self.is_recording:
            print("⚠️ Already recording")
            return False
        
        if not self.groq_client:
            print("❌ Groq client not initialized. Cannot record.")
            return False
        
        self.is_recording = True
        self.transcription_ready.clear()
        print("🎤 Recording started (press 'S' to stop)")
        
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
        print("⏹️ Recording stopped")
        
        # Stop stream
        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None
        
        # Close wave file
        if self.wave_file:
            self.wave_file.close()
            self.wave_file = None
        
        print("🧠 Transcribing...")
        
        # Get audio data
        self.audio_buffer.seek(0)
        audio_data = self.audio_buffer.read()
        
        # Transcribe synchronously (blocking)
        self._transcribe_audio(audio_data)
        
        # Wait for transcription to complete (with timeout)
        if self.transcription_ready.wait(timeout=10):
            result = self.transcribed_text
            self.transcribed_text = None
            return result
        else:
            print("❌ Transcription timeout")
            return None
    
    def _transcribe_audio(self, audio_data):
        """Transcribe audio using Groq Whisper."""
        try:
            transcription = self.groq_client.audio.transcriptions.create(
                file=("audio.wav", audio_data),
                model="whisper-large-v3-turbo",
                language="en"
            )
            
            text = transcription.text.strip()
            print(f"📝 Transcription: {text}")
            
            self.transcribed_text = text
            self.transcription_ready.set()
            
        except Exception as e:
            print(f"❌ Transcription error: {e}")
            self.transcribed_text = None
            self.transcription_ready.set()
    
    def _initialize_gemini_chat(self):
        """Initialize Gemini client for general chat."""
        try:
            from google import genai
            client = genai.Client(api_key=config.API_KEY)
            return client
        except Exception as e:
            print(f"❌ Failed to initialize Gemini for chat: {e}")
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
        
        print("🎤 Waiting for voice input (press 'C' to record, 'S' to stop)...")
        
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
        # Kill the mpv process if it's running
        if hasattr(self, 'current_mpv_process') and self.current_mpv_process and self.current_mpv_process.poll() is None:
            try:
                self.current_mpv_process.terminate()
                self.current_mpv_process.wait(timeout=0.5) # Give it a moment to terminate
                if self.current_mpv_process.poll() is None: # If still running, force kill
                    self.current_mpv_process.kill()
                print("🛑 TTS stopped")
            except Exception as e:
                print(f"⚠️ Error stopping TTS: {e}")
            finally:
                self.current_mpv_process = None

    def speak(self, text, async_mode=True):
        """
        Speak text using Edge-TTS with robust file-based playback.
        Supports #PAUSE(x) tokens.
        """
        if not text or not text.strip():
            return
        
        # Add to history
        self.conversation_manager.add_turn("assistant", text)
        
        # Filter out emojis
        text = re.sub(r'[\U00010000-\U0010ffff]', '', text)
        
        # Stop any currently playing audio before starting new one
        self.stop_speaking()

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
        Async TTS: Robust file-based playback with #PAUSE support.
        Optimized for latency using RAM disk and tuned player flags.
        """
        try:
            # 1. Parse #PAUSE(x) tokens
            tokens = re.split(r'(#PAUSE\([\d\.]+\))', text)
            
            for token in tokens:
                # Check if it's a pause token
                pause_match = re.match(r'#PAUSE\(([\d\.]+)\)', token)
                if pause_match:
                    duration = float(pause_match.group(1))
                    time.sleep(duration)
                    continue
                
                if not token.strip():
                    continue
                
                # 2. Generate audio to file (RAM DISK)
                # Use unique name to allow parallel generation if needed
                filename = os.path.join(self.tts_temp_dir, f"nova_tts_{int(time.time()*1000)}_{random.randint(0,1000)}.mp3")
                
                communicate = Communicate(token, self.EDGE_VOICE, rate=self.EDGE_RATE)
                await communicate.save(filename)
                
                # 3. Play audio file (blocking until done)
                # Optimized flags for lowest latency
                # 3. Play audio file (blocking until done, but interruptible)
                # Optimized flags for lowest latency
                if shutil.which("mpv"):
                    self.current_mpv_process = subprocess.Popen(
                        ["mpv", 
                         "--no-terminal", 
                         "--vo=null",  # No video output
                         "--audio-buffer=0",  # Minimize buffer
                         "--no-cache", 
                         "--volume=100", 
                         filename],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL
                    )
                elif shutil.which("ffplay"):
                    self.current_mpv_process = subprocess.Popen(
                        ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", filename],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL
                    )
                
                # Wait for process to finish
                if self.current_mpv_process:
                    self.current_mpv_process.wait()
                    self.current_mpv_process = None
                
                # Clean up
                if os.path.exists(filename):
                    os.remove(filename)
                    
        except Exception as e:
            print(f"❌ Edge-TTS playback error: {e}")

    def chat_with_nova(self, text):
        """
        Send text to Gemini (Nova persona) for general conversation.
        Includes conversation history for context.
        """
        if not self.gemini_chat_client:
            self.speak("I'm having trouble connecting to my brain.", async_mode=True)
            return

        print(f"🤖 Nova thinking about: '{text}'")
        
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
            print(f"🤖 Nova says: {reply}")
            self.speak(reply, async_mode=True)
            
        except Exception as e:
            print(f"❌ Nova chat error: {e}")
            self.speak("Sorry, I spaced out for a second.", async_mode=True)

    def parse_command(self, text):
        """
        Parse voice command using Gemini (Chat-First Routing).
        The Chat Model decides if it needs to see (VISUAL_QUERY) or just chat.
        """
        if not text:
            return None
        
        # Add to history
        self.conversation_manager.add_turn("user", text)
        print(f"🧠 Processing input: '{text}'")
        
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
            print("⚡ Fast Path: Visual Query detected")
            return {"intent": "visual_qa", "params": {"question": text}}

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
                print("👉 Route: VISUAL_QUERY (Detected by Chat Model)")
                return {"intent": "visual_qa", "params": {"question": text}}
            
            # Otherwise, it's a normal chat response
            print(f"👉 Route: CHAT (Direct Response)")
            print(f"🤖 Nova says: {reply}")
            
            # Return as direct response so we don't call Gemini again
            return {"intent": "direct_response", "params": {"response": reply}}
            
        except Exception as e:
            print(f"❌ Routing error: {e}")
            return {"intent": "chat_with_nova", "params": {"text": text}}

    def get_help_text(self):
        """Return help text for voice commands."""
        return "I'm Nova. You can ask me to track objects, describe the scene, read text, or just chat. Press C to talk."
