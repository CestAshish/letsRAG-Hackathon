import os
import json
import logging
from typing import List, Dict, Any

from app.retrieval import StructuralHybridRetriever
from app.agent.prompts import get_system_prompt
from app.agent.tools import (
    AGENT_TOOLS, 
    execute_calculator, 
    execute_create_pdf_summary, 
    execute_send_message
)
from app.adapters.llm_adapter import LLMAdapter

logger = logging.getLogger(__name__)

class SOTAAgent:
    """
    Core Intelligence for the Legal RAG System.
    Handles tool loop execution and language model interactions.
    """
    def __init__(self):
        # Delegate LLM setup and interactions to the adapter (picks up env variables automatically)
        self.llm = LLMAdapter()
        self.retriever = StructuralHybridRetriever()
        
        # Load indexes from the app/data directory
        app_dir = os.path.dirname(os.path.dirname(__file__))
        chunks_path = os.path.join(app_dir, "data", "corpus_blocks_hierarchical.json")
        toc_path = os.path.join(app_dir, "data", "toc_tree.json")
        
        if os.path.exists(chunks_path) and os.path.exists(toc_path):
            self.retriever.load_and_index(chunks_path, toc_path)
            
    def _format_docs_for_context(self, docs: List[Dict[str, Any]], doc_id_to_idx: Dict[str, int], all_docs: List[Dict[str, Any]]) -> str:
        """Helper to properly track and format retrieved documents."""
        if not docs:
            return "No results found."
            
        formatted_texts = []
        for d in docs:
            if d["id"] not in doc_id_to_idx:
                idx = len(all_docs)
                doc_id_to_idx[d["id"]] = idx
                all_docs.append(d)
                
                node_path = d["metadata"].get("node_path", [])
                heading = " > ".join(node_path) if node_path else d["metadata"].get("parent_heading", "None")
                page = d["metadata"].get("page", 1)
                
                try:
                    page_num = int(page)
                except:
                    page_num = 1
                    
                if page_num <= 44 and (not node_path and heading in ["None", ""]):
                    heading = "Preamble & Recitals"
                    
                lines = d["metadata"].get("lines", [])
                
                text_block = f"[Chunk {idx+1} | Heading: {heading} | Page: {page}]\n"
                if d.get("is_outline"):
                    text_block += f"  {d.get('text', '')}\n"
                elif lines:
                    for l in lines:
                        text_block += f"  [L{l.get('num', 0)}] {l.get('text', '')}\n"
                else:
                    text_block += f"  {d.get('text', '')}\n"
                    
                formatted_texts.append(text_block)
            else:
                idx = doc_id_to_idx[d["id"]]
                formatted_texts.append(f"[Chunk {idx+1} already provided in context]")
            
        return "\n\n".join(formatted_texts)

    def run(self, query: str, history: List[Dict[str, str]] = None) -> Dict[str, Any]:
        """Main execution loop for answering a user's query."""
        if not history: 
            history = []
            
        messages = [{"role": "system", "content": get_system_prompt()}]
        for msg in history:
            messages.append({"role": msg["role"], "content": msg["content"]})
        messages.append({"role": "user", "content": query})

        all_docs = []
        doc_id_to_idx = {}
        trajectory = []
        
        total_prompt_tokens = 0
        total_completion_tokens = 0
        
        MAX_TURNS = 5
        turns = 0
        
        while turns <= MAX_TURNS + 1:
            from app.observability import track_agent_loop, track_tool_used, set_agent_status
            track_agent_loop()
            
            # Dynamically inject state awareness into the system prompt
            base_prompt = get_system_prompt()
            state_awareness = f"\n\n[SYSTEM STATE AWARENESS]\nYou are currently on Agent Turn {turns} (Max {MAX_TURNS} before cutoff).\n"
            if trajectory:
                state_awareness += "Tools used so far for this specific query:\n"
                for i, t in enumerate(trajectory):
                    state_awareness += f"  - Turn {i}: {t['tool']}\n"
            else:
                state_awareness += "No tools have been used yet for this query.\n"
            
            messages[0]["content"] = base_prompt + state_awareness

            try:
                set_agent_status("Synthesizing response..." if turns > 0 else "Analyzing query...")
                # ALWAYS pass tools to the API to prevent 400 Bad Request crashes if the LLM hallucinates a call.
                # We will intercept forbidden tool calls gracefully in the python logic below.
                current_tools = AGENT_TOOLS
                
                res = self.llm.chat_completion(
                    messages=messages,
                    tools=current_tools,
                    temperature=0
                )
                
                if hasattr(res, 'usage') and res.usage:
                    total_prompt_tokens += res.usage.prompt_tokens
                    total_completion_tokens += res.usage.completion_tokens
                    
            except Exception as e:
                logger.error(f"Generation failed: {e}")
                return {
                    "query": query,
                    "generation": "I'm sorry, I encountered an error communicating with the model.",
                    "documents": all_docs,
                    "trajectory": trajectory
                }
                
            msg = res.choices[0].message
            msg_dict = {"role": msg.role, "content": msg.content or ""}
            
            if msg.tool_calls:
                msg_dict["tool_calls"] = [
                    {
                        "id": tc.id, 
                        "type": tc.type, 
                        "function": {"name": tc.function.name, "arguments": tc.function.arguments}
                    }
                    for tc in msg.tool_calls
                ]
            
            messages.append(msg_dict)
            
            if msg.tool_calls:
                if turns >= MAX_TURNS:
                    for tool_call in msg.tool_calls:
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": "ERROR: Maximum search turns reached. You MUST synthesize your final answer using retrieved context."
                        })
                    turns += 1 # Ensure we break out of the while loop on the next check!
                    continue
                    
                turns += 1
                for tool_call in msg.tool_calls:
                    fn_name = tool_call.function.name
                    track_tool_used(fn_name)
                    
                    try:
                        args = json.loads(tool_call.function.arguments)
                    except:
                        args = {}
                        
                    logger.info(f"Agent calling tool {fn_name} with args {args}")
                    tool_res = ""
                    
                    search_count = sum(1 for t in trajectory if t["tool"] in ["search_content", "search_structure"])
                    
                    if fn_name in ["search_content", "search_structure"] and search_count >= 2:
                        tool_res = "ERROR: You have reached the strict limit of 2 searches per query. You MUST stop searching and immediately synthesize a response based on the context you already have."
                    elif fn_name == "search_content":
                        set_agent_status("Searching AI Act database...")
                        qs = args.get("queries") or args.get("query") or [query]
                        if isinstance(qs, str): qs = [qs]
                        
                        # Defensive sanitization — only strip full boilerplate phrases, not standalone words
                        import re
                        cleaned_qs = []
                        for q in qs:
                            clean_q = re.sub(r'(?i)\b(the\s+)?eu\s+ai\s+act\b', '', q).strip()
                            clean_q = re.sub(r'(?i)\b(the\s+)?ai\s+act\b', '', clean_q).strip()
                            clean_q = re.sub(r'(?i)\bthe\s+act\b', '', clean_q).strip()
                            clean_q = re.sub(r'\s+', ' ', clean_q).strip()
                            if clean_q != q.strip():
                                logger.warning(f"DEBUG INTERCEPT: Stripped boilerplate from query: '{q}' -> '{clean_q}'")
                            cleaned_qs.append(clean_q if clean_q else q)
                        qs = cleaned_qs
                        
                        intents = [{"semantic_confidence": 1.0, "keyword_confidence": 1.0, "article_confidence": 0.0} for _ in qs]
                        res_batches = self.retriever.search_batch_parallel(qs, intents)
                        flattened = [doc for batch in res_batches for doc in batch]
                        tool_res = self._format_docs_for_context(flattened, doc_id_to_idx, all_docs)
                        
                    elif fn_name == "search_structure":
                        set_agent_status("Retrieving legal articles...")
                        targets = args.get("targets") or args.get("target") or [query]
                        if isinstance(targets, str): targets = [targets]
                        intents = [{"semantic_confidence": 0.0, "keyword_confidence": 0.0, "article_confidence": 1.0, "target_articles": [t]} for t in targets]
                        res_batches = self.retriever.search_batch_parallel(targets, intents)
                        flattened = [doc for batch in res_batches for doc in batch]
                        tool_res = self._format_docs_for_context(flattened, doc_id_to_idx, all_docs)
                        
                    elif fn_name == "calculator":
                        set_agent_status("Calculating...")
                        exprs = args.get("expressions") or args.get("expression") or []
                        if isinstance(exprs, str): exprs = [exprs]
                        tool_res = execute_calculator(exprs)
                        
                    elif fn_name == "check_summary":
                        set_agent_status("Searching memory...")
                        from app.agent.tools import execute_check_summary
                        tool_res = execute_check_summary(args.get("query", ""))
                        
                    elif fn_name == "create_pdf_summary":
                        set_agent_status("Generating PDF report...")
                        tool_res = execute_create_pdf_summary(args.get("title", "Summary"), args.get("content", ""))
                        
                    elif fn_name == "send_message":
                        set_agent_status("Formatting message...")
                        tool_res = execute_send_message(args.get("message", ""))
                        
                    elif fn_name == "analyze_risk_tier":
                        set_agent_status("Formulating risk assessment wizard...")
                        from app.agent.tools import execute_analyze_risk_tier
                        tool_res = execute_analyze_risk_tier(args.get("questions", []))
                        
                    else:
                        tool_res = f"Unknown tool: {fn_name}"
                        
                    # Save trace
                    trajectory.append({"tool": fn_name, "args": args})
                    
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": tool_res
                    })
            else:
                # Agent answered, stop loop
                break
                
        logger.info(f"Query complete | Total In: {total_prompt_tokens} | Total Out: {total_completion_tokens}")
        
        return {
            "query": query,
            "generation": msg.content or "No answer provided.",
            "documents": all_docs,
            "trajectory": trajectory,
            "usage": {
                "prompt_tokens": total_prompt_tokens,
                "completion_tokens": total_completion_tokens,
                "total_tokens": total_prompt_tokens + total_completion_tokens
            }
        }
