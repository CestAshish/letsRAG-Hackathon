import asyncio
import json
import os
import faiss
import numpy as np
from typing import List, Dict, Any
from sentence_transformers import SentenceTransformer
from app.chat_handler.session_manager import SessionManager
from app.adapters.llm_adapter import LLMAdapter
from app.observability import log_telemetry

class AsyncChatSummarizer:
    def __init__(self):
        self.manager = SessionManager()
        self.llm = LLMAdapter()
        
        provider = os.environ.get("LR_EMBEDDING_PROVIDER", "local")
        if provider == "huggingface_api":
            from app.retrieval import HuggingFaceAPIEmbeddings
            self.embedder = HuggingFaceAPIEmbeddings()
        else:
            from sentence_transformers import SentenceTransformer
            self.embedder = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
        
    def _get_faiss_path(self, session_id: str) -> str:
        return os.path.join(self.manager._get_session_dir(session_id), "faiss_index.bin")
        
    def _get_summaries_path(self, session_id: str) -> str:
        return os.path.join(self.manager._get_session_dir(session_id), "summaries.json")
        
    def _get_meta_path(self, session_id: str) -> str:
        return os.path.join(self.manager._get_session_dir(session_id), "meta.json")

    async def check_and_summarize(self, session_id: str):
        """Checks if a new summary is needed based on the 20-message rule, and runs it if so."""
        try:
            # We must run this in a thread or just do the blocking work directly but yielding to event loop
            # For simplicity in this demo, we'll execute it synchronously in an async wrapper
            await asyncio.to_thread(self._run_summarization, session_id)
        except Exception as e:
            print(f"Error in background summarization: {str(e)}")

    def _run_summarization(self, session_id: str):
        history = self.manager.load_session(session_id)
        meta_path = self._get_meta_path(session_id)
        
        meta = {"last_summarized_index": 0}
        if os.path.exists(meta_path):
            with open(meta_path, "r", encoding="utf-8") as f:
                meta = json.load(f)
                
        unsummarized = len(history) - meta["last_summarized_index"]
        
        # If there are 20 or more unsummarized messages (10 turns)
        if unsummarized >= 20:
            target_messages = history[meta["last_summarized_index"] : meta["last_summarized_index"] + 20]
            
            # Format for LLM
            prompt = "Please summarize the following 20 messages (10 turns) of conversation between a User and a Legal AI Assistant. Focus on the core topics discussed, the rules explained, and any user preferences or specific articles mentioned. Keep it to one detailed paragraph.\n\n"
            for m in target_messages:
                prompt += f"{m['role'].upper()}: {m['content']}\n"
                
            messages = [{"role": "user", "content": prompt}]
            
            # Generate summary
            res = self.llm.chat_completion(messages=messages, temperature=0.3)
            summary_text = res.choices[0].message.content
            
            # Vectorize
            embedding = self.embedder.encode([summary_text], convert_to_numpy=True)
            
            # Save to FAISS
            faiss_path = self._get_faiss_path(session_id)
            if os.path.exists(faiss_path):
                index = faiss.read_index(faiss_path)
            else:
                index = faiss.IndexFlatL2(embedding.shape[1])
                
            index.add(embedding)
            faiss.write_index(index, faiss_path)
            
            # Save text
            summaries_path = self._get_summaries_path(session_id)
            summaries = []
            if os.path.exists(summaries_path):
                with open(summaries_path, "r", encoding="utf-8") as f:
                    summaries = json.load(f)
                    
            summaries.append(summary_text)
            with open(summaries_path, "w", encoding="utf-8") as f:
                json.dump(summaries, f, indent=2)
                
            # Update meta
            meta["last_summarized_index"] += 20
            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump(meta, f)
                
            print(f"Background summarization complete for session {session_id}. Generated summary for 20 messages.")

    def search_summaries(self, session_id: str, query: str, top_k: int = 2) -> str:
        """Used by the check_summary tool to retrieve past context."""
        faiss_path = self._get_faiss_path(session_id)
        summaries_path = self._get_summaries_path(session_id)
        
        if not os.path.exists(faiss_path) or not os.path.exists(summaries_path):
            return "No previous conversation summaries exist for this session yet."
            
        index = faiss.read_index(faiss_path)
        with open(summaries_path, "r", encoding="utf-8") as f:
            summaries = json.load(f)
            
        q_emb = self.embedder.encode([query], convert_to_numpy=True)
        distances, indices = index.search(q_emb, k=min(top_k, len(summaries)))
        
        results = []
        for i, idx in enumerate(indices[0]):
            if idx != -1:
                results.append(f"Past Summary {i+1}: {summaries[idx]}")
                
        if not results:
            return "No relevant past conversations found."
            
        return "\n\n".join(results)
