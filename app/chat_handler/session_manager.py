import os
import json
from typing import List, Dict, Any

class SessionManager:
    """Handles the persistence of raw chat messages within the chat_handler/data/sessions/ directory."""
    
    def __init__(self):
        self.base_dir = os.path.join(os.path.dirname(__file__), "data", "sessions")
        os.makedirs(self.base_dir, exist_ok=True)
        
    def _get_session_dir(self, session_id: str) -> str:
        session_dir = os.path.join(self.base_dir, session_id)
        os.makedirs(session_dir, exist_ok=True)
        return session_dir
        
    def _get_chat_file(self, session_id: str) -> str:
        return os.path.join(self._get_session_dir(session_id), "raw_chat.json")
        
    def load_session(self, session_id: str) -> List[Dict[str, Any]]:
        """Loads the raw chat history for a session."""
        chat_file = self._get_chat_file(session_id)
        if os.path.exists(chat_file):
            with open(chat_file, "r", encoding="utf-8") as f:
                return json.load(f)
        return []
        
    def save_message(self, session_id: str, message: Dict[str, Any]):
        """Appends a new message to the session's raw chat history."""
        history = self.load_session(session_id)
        history.append(message)
        with open(self._get_chat_file(session_id), "w", encoding="utf-8") as f:
            json.dump(history, f, indent=2)
            
    def get_all_sessions(self) -> List[Dict[str, str]]:
        """Returns a list of all sessions with their titles, sorted by newest."""
        if not os.path.exists(self.base_dir):
            return []
        
        session_dirs = [d for d in os.listdir(self.base_dir) if os.path.isdir(os.path.join(self.base_dir, d))]
        
        # Sort by modification time
        session_dirs.sort(key=lambda d: os.path.getmtime(os.path.join(self.base_dir, d)), reverse=True)
        
        result = []
        for sid in session_dirs:
            history = self.load_session(sid)
            title = "New Chat"
            if history:
                first_msg = history[0].get("content", "")
                title = first_msg[:30] + "..." if len(first_msg) > 30 else first_msg
            result.append({"id": sid, "title": title})
        
        return result

    def delete_session(self, session_id: str):
        import shutil
        session_dir = os.path.join(self.base_dir, session_id)
        if os.path.exists(session_dir):
            shutil.rmtree(session_dir)
