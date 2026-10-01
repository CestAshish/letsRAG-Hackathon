import contextvars
import time
from typing import Dict, List, Any

# Context variables to trace execution across async/sync layers
current_message_id = contextvars.ContextVar("current_message_id", default=None)
current_session_id = contextvars.ContextVar("current_session_id", default=None)

# In-memory store for real-time telemetry, backed by disk to survive hot-reloads
import json
import os

TELEMETRY_DIR = os.path.join(os.path.dirname(__file__), "data", "telemetry")
os.makedirs(TELEMETRY_DIR, exist_ok=True)

telemetry_store: Dict[str, Dict[str, Any]] = {}

def _flush_telemetry(msg_id: str):
    """Saves telemetry to disk so it survives backend restarts."""
    if msg_id in telemetry_store:
        try:
            path = os.path.join(TELEMETRY_DIR, f"{msg_id}.json")
            with open(path, "w") as f:
                json.dump(telemetry_store[msg_id], f)
        except Exception as e:
            print(f"Failed to flush telemetry: {e}")

def init_message_telemetry(message_id: str, session_id: str = None):
    current_message_id.set(message_id)
    if session_id:
        current_session_id.set(session_id)
        
    telemetry_store[message_id] = {
        "analytics": {
            "total_agent_loops": 0,
            "llm_calls": 0,
            "hf_calls": 0,
            "total_prompt_tokens": 0,
            "total_completion_tokens": 0,
            "total_tokens": 0,
            "tools_used": []
        },
        "logs": []
    }
    _flush_telemetry(message_id)

def log_telemetry(level: str, message: str):
    msg_id = current_message_id.get()
    if msg_id and msg_id in telemetry_store:
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        telemetry_store[msg_id]["logs"].append(f"[{timestamp}] [{level}] {message}")
        _flush_telemetry(msg_id)
    else:
        print(f"[{level}] {message}")

def track_llm_call(prompt_tokens: int, completion_tokens: int):
    msg_id = current_message_id.get()
    if msg_id and msg_id in telemetry_store:
        analytics = telemetry_store[msg_id]["analytics"]
        analytics["llm_calls"] += 1
        analytics["total_prompt_tokens"] += prompt_tokens
        analytics["total_completion_tokens"] += completion_tokens
        analytics["total_tokens"] += (prompt_tokens + completion_tokens)
        _flush_telemetry(msg_id)

def track_hf_call():
    msg_id = current_message_id.get()
    if msg_id and msg_id in telemetry_store:
        telemetry_store[msg_id]["analytics"]["hf_calls"] += 1
        _flush_telemetry(msg_id)

def track_agent_loop():
    msg_id = current_message_id.get()
    if msg_id and msg_id in telemetry_store:
        telemetry_store[msg_id]["analytics"]["total_agent_loops"] += 1
        _flush_telemetry(msg_id)

def track_tool_used(tool_name: str):
    msg_id = current_message_id.get()
    if msg_id and msg_id in telemetry_store:
        if tool_name not in telemetry_store[msg_id]["analytics"]["tools_used"]:
            telemetry_store[msg_id]["analytics"]["tools_used"].append(tool_name)
            _flush_telemetry(msg_id)

def get_telemetry(message_id: str) -> Dict[str, Any]:
    # First check memory
    if message_id in telemetry_store:
        return telemetry_store[message_id]
    
    # If not in memory (due to hot-reload), check disk
    path = os.path.join(TELEMETRY_DIR, f"{message_id}.json")
    if os.path.exists(path):
        try:
            with open(path, "r") as f:
                data = json.load(f)
                telemetry_store[message_id] = data
                return data
        except:
            pass
            
    return None

# Live status polling
live_status_store: Dict[str, str] = {}

def set_agent_status(status: str):
    session_id = current_session_id.get()
    if session_id:
        live_status_store[session_id] = status

def get_agent_status(session_id: str) -> str:
    return live_status_store.get(session_id, "Thinking...")
