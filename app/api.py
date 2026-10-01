import os
import logging
import asyncio
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Any
from dotenv import load_dotenv

from app.agent.core import SOTAAgent
from app.chat_handler.session_manager import SessionManager
from app.chat_handler.summarizer import AsyncChatSummarizer
from app.observability import init_message_telemetry, get_telemetry, get_agent_status

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="SOTA Legal RAG API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

agent = SOTAAgent()
session_manager = SessionManager()
summarizer = AsyncChatSummarizer()

class QueryRequest(BaseModel):
    query: str
    session_id: str
    message_id: str

class QueryResponse(BaseModel):
    answer: str
    sources: List[Dict[str, Any]]
    trajectory: List[Dict[str, Any]] = []

@app.get("/api/download/{filename}")
def download_file(filename: str):
    safe_filename = os.path.basename(filename)
    if not os.path.exists(safe_filename):
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(
        path=safe_filename, 
        filename=safe_filename, 
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={safe_filename}"}
    )

@app.get("/api/sessions")
def get_sessions():
    return {"sessions": session_manager.get_all_sessions()}

@app.delete("/api/sessions/{session_id}")
def delete_session(session_id: str):
    session_manager.delete_session(session_id)
    return {"status": "SUCCESS"}

@app.get("/api/chat/{session_id}")
def get_chat_history(session_id: str):
    return {"messages": session_manager.load_session(session_id)}

@app.get("/api/status/{session_id}")
def get_status(session_id: str):
    return {"status": get_agent_status(session_id)}

@app.get("/api/analytics/{message_id}")
def get_analytics(message_id: str):
    telemetry = get_telemetry(message_id)
    if not telemetry:
        raise HTTPException(status_code=404, detail="Telemetry not found")
    return telemetry

class WebhookRequest(BaseModel):
    message: str

@app.post("/api/send_webhook")
def send_webhook(req: WebhookRequest):
    from app.adapters.webhook_adapter import WebhookAdapter
    webhook_url = os.environ.get("TEAMS_WEBHOOK_URL") or os.environ.get("SLACK_WEBHOOK_URL")
    if not webhook_url:
        return {"status": "MOCK_SUCCESS", "message": req.message}
    try:
        WebhookAdapter.send_post(url=webhook_url, payload={"text": req.message})
        return {"status": "SUCCESS"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/chat", response_model=QueryResponse)
async def ask_question(req: QueryRequest, background_tasks: BackgroundTasks):
    init_message_telemetry(req.message_id, req.session_id)
    try:
        # Load full history
        history = session_manager.load_session(req.session_id)
        
        # Save user query
        user_msg = {"role": "user", "content": req.query, "id": req.message_id}
        session_manager.save_message(req.session_id, user_msg)
        
        # Truncate context to last 20 messages for LLM context window
        context_history = history[-20:] if len(history) > 20 else history
        history_dicts = [{"role": msg["role"], "content": msg["content"]} for msg in context_history]
        
        # Execute agent workflow
        result = await asyncio.to_thread(agent.run, req.query, history_dicts)
        
        answer = result.get("generation", "I'm sorry, I couldn't generate a response.")
        docs = result.get("documents", [])
        trajectory = result.get("trajectory", [])
        
        # Format sources to save and return
        sources = []
        for d in docs:
            sources.append({
                "page": d["metadata"].get("page", 1),
                "bbox": d["metadata"].get("bbox", []),
                "node_path": d["metadata"].get("node_path", []),
                "lines": d["metadata"].get("lines", []),
                "is_outline": d.get("is_outline", False),
                "text": d.get("text", "")[:200]
            })

        # Save assistant response
        asst_msg = {
            "role": "assistant", 
            "content": answer, 
            "id": req.message_id + "_reply",
            "sources": sources,
            "trajectory": trajectory,
            "message_id_ref": req.message_id # to link analytics button
        }
        session_manager.save_message(req.session_id, asst_msg)
        
        # Trigger background summarizer for memory (fail-safe checks inside summarizer)
        background_tasks.add_task(summarizer.check_and_summarize, req.session_id)
            
        return QueryResponse(answer=answer, sources=sources, trajectory=trajectory)
        
    except Exception as e:
        logger.exception(f"Error processing query: {req.query}")
        raise HTTPException(status_code=500, detail="Internal server error.")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.api:app", host="0.0.0.0", port=8000, reload=True)
