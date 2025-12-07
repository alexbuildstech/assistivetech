import json
import os
import time
from datetime import datetime

class ConversationManager:
    """
    Manages conversation history and persists it to a JSON file.
    Provides context for both Vision and Language AIs.
    """
    
    def __init__(self, history_file="conversation_history.json", max_turns=20):
        self.history_file = history_file
        self.max_turns = max_turns
        self.history = self._load_history()
        
    def _load_history(self):
        """Load history from JSON file."""
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                print(f"⚠️ Failed to load history: {e}")
                return []
        return []
    
    def save_history(self):
        """Save history to JSON file."""
        try:
            with open(self.history_file, 'w') as f:
                json.dump(self.history, f, indent=2)
        except Exception as e:
            print(f"❌ Failed to save history: {e}")
            
    def add_turn(self, role, text):
        """
        Add a turn to the history.
        role: "user" or "assistant"
        text: The spoken text
        """
        entry = {
            "timestamp": datetime.now().isoformat(),
            "role": role,
            "text": text
        }
        self.history.append(entry)
        
        # Trim history if too long
        if len(self.history) > self.max_turns:
            self.history = self.history[-self.max_turns:]
            
        self.save_history()
        
    def get_context_string(self, limit=5):
        """
        Get recent history formatted as a string for AI prompts.
        """
        recent = self.history[-limit:] if limit > 0 else []
        context = ""
        for entry in recent:
            role_name = "User" if entry["role"] == "user" else "Nova"
            context += f"{role_name}: {entry['text']}\n"
        return context.strip()

    def get_recent_history(self, limit=5):
        """Get raw list of recent turns."""
        return self.history[-limit:] if limit > 0 else []

    def clear_history(self):
        """Clear all history."""
        self.history = []
        self.save_history()
