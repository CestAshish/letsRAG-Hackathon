import os
from openai import OpenAI
from typing import List, Dict, Any
from app.observability import log_telemetry, track_llm_call

class LLMAdapter:
    """
    Adapter for interacting with the LLM API (e.g., Groq, OpenAI).
    Centralizes all API calls and logs interactions.
    """
    def __init__(self, api_key: str = None, base_url: str = None, model: str = None):
        self.provider = os.getenv("LLM_PROVIDER", "groq").lower()
        
        if self.provider == "openai":
            self.model = model or os.getenv("OPENAI_MODEL", "gpt-4o-mini")
            api_key = api_key or os.getenv("OPENAI_API_KEY", "dummy_key")
            # OpenAI doesn't need a custom base_url unless specifically configured
            self.client = OpenAI(api_key=api_key)
            log_telemetry("INFO", f"LLMAdapter initialized for OpenAI model: {self.model}")
        else:
            self.model = model or os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")
            api_key = api_key or os.getenv("GROQ_API_KEY", "dummy_key")
            base_url = base_url or "https://api.groq.com/openai/v1"
            self.client = OpenAI(api_key=api_key, base_url=base_url)
            log_telemetry("INFO", f"LLMAdapter initialized for Groq model: {self.model} at {base_url}")

    def chat_completion(self, messages: List[Dict[str, Any]], tools: List[Dict[str, Any]] = None, temperature: float = 0.0):
        """Executes a chat completion request with the underlying LLM."""
        log_telemetry("INFO", f"LLMAdapter: Sending chat completion request. Message count: {len(messages)}. Tools provided: {bool(tools)}.")
        try:
            kwargs = {
                "model": self.model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": 4096,
                "frequency_penalty": 0.2
            }
            if tools:
                kwargs["tools"] = tools
                kwargs["tool_choice"] = "auto"
                
            response = self.client.chat.completions.create(**kwargs)
            log_telemetry("INFO", "LLMAdapter: Received successful chat completion response.")
            
            # Track tokens
            if response.usage:
                track_llm_call(
                    prompt_tokens=response.usage.prompt_tokens,
                    completion_tokens=response.usage.completion_tokens
                )
            
            return response
        except Exception as e:
            log_telemetry("ERROR", f"LLMAdapter: Error during chat completion - {str(e)}")
            raise
