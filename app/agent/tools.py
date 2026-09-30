import os
import re
import logging
import simpleeval
from fpdf import FPDF
from app.adapters.webhook_adapter import WebhookAdapter

logger = logging.getLogger(__name__)

# --- Tool Schemas for the LLM ---

AGENT_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_content",
            "description": "Search the EU AI Act using semantic and keyword search. Best for concepts, rules, definitions, and general queries.",
            "parameters": {
                "type": "object",
                "properties": {
                    "queries": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "A list of search queries. CRITICAL: Use ONLY minimal, dense keywords (e.g. 'guidelines minors'). NEVER include boilerplate like 'EU AI Act', 'AI', or 'Act' in these strings, as it destroys the vector search math."
                    }
                },
                "required": ["queries"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_structure",
            "description": "Fetch specific structural nodes from the Act. Use this ONLY when the user explicitly names parts of the law.",
            "parameters": {
                "type": "object",
                "properties": {
                    "targets": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "A list of exact node names to fetch (e.g. ['Article 51', 'Chapter 2', 'Annex XIII'])."
                    }
                },
                "required": ["targets"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "calculator",
            "description": "Perform mathematical calculations (e.g., adding fines, percentages, or square roots). You MUST use this tool for ALL math. Do not attempt mental math.",
            "parameters": {
                "type": "object",
                "properties": {
                    "expressions": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "A list of valid mathematical expressions (e.g. ['95 * 89', 'math.sqrt(8455)']). Batch multiple independent calculations into this single payload."
                    }
                },
                "required": ["expressions"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_pdf_summary",
            "description": "Creates a PDF file. The content MUST be extremely specific, thorough, and highly detailed with structured information. Do NOT provide short summaries. The frontend will automatically render a download button for the user.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "The title of the PDF document."
                    },
                    "content": {
                        "type": "string",
                        "description": "The highly detailed, comprehensive content to include in the PDF. IMPORTANT: For the References section at the end of the document, ONLY list the exact 1 to 5 Articles you explicitly retrieved and used. DO NOT hallucinate references, and DO NOT list every Article in the Act."
                    }
                },
                "required": ["title", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "send_message",
            "description": "Sends a highly detailed, professional message to an external Slack/Teams channel. The message content MUST be purely factual and structured. Do NOT include any conversational filler, greetings (e.g., 'Here is the info...'), or closing remarks (e.g., 'Let me know if...').",
            "parameters": {
                "type": "object",
                "properties": {
                    "message": {
                        "type": "string",
                        "description": "The strictly professional, factual content to send. No conversational fluff."
                    }
                },
                "required": ["message"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "analyze_risk_tier",
            "description": "Generates a sequence of Yes/No questions to determine the risk tier of a user's AI system. IMPORTANT: Your questions MUST target official EU AI Act classifications (Annex III High-Risk areas or Article 5 Prohibited practices). However, you MUST translate these into plain-English for the user. Do NOT use legal jargon like 'Article 5' or 'Annex III' in the questions. Instead, explain the concept (e.g., 'Does the system use subliminal techniques or social scoring?'). The UI will render these as an interactive wizard.",
            "parameters": {
                "type": "object",
                "properties": {
                    "questions": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "A list of 3-5 highly specific Yes/No questions needed to classify the AI under the EU AI Act."
                    }
                },
                "required": ["questions"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "check_summary",
            "description": "Searches past conversation summaries. You MUST use this tool ANY TIME the user asks you to remember something, says 'check again', 'check records', 'look back', or challenges your memory. Do NOT apologize and give up without calling this tool first! You MUST formulate a specific, context-aware semantic search query. NEVER just copy the user's exact words.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "A standalone, highly specific search query formulated from the context. For example, if the user says 'check chat history' after asking 'do you remember my name', your query MUST be 'user name' or 'what is the user's name'. Do NOT pass 'check chat history'."
                    }
                },
                "required": ["query"]
            }
        }
    }
]

# --- Standalone Tool Implementations ---

_summarizer_instance = None

def execute_check_summary(query: str) -> str:
    from app.observability import current_session_id
    from app.chat_handler.summarizer import AsyncChatSummarizer
    
    session_id = current_session_id.get()
    if not session_id:
        return "ERROR: No active session available."
        
    global _summarizer_instance
    if _summarizer_instance is None:
        _summarizer_instance = AsyncChatSummarizer()
        
    return _summarizer_instance.search_summaries(session_id, query)

def execute_calculator(expressions: list) -> str:
    """Safely evaluates multiple mathematical expressions in a single batch."""
    import math
    try:
        # Give simple_eval access to standard math functions like sqrt
        functions = simpleeval.DEFAULT_FUNCTIONS.copy()
        functions.update({"sqrt": math.sqrt, "math.sqrt": math.sqrt})
        
        results = []
        for expr in expressions:
            calc_result = simpleeval.simple_eval(expr, functions=functions)
            results.append(f"{expr} = {calc_result}")
            
        return "Calculations successful:\n" + "\n".join(results)
    except Exception as e:
        return f"Error evaluating expressions: {str(e)}"

def execute_create_pdf_summary(title: str, content: str) -> str:
    """
    Creates a State-of-the-Art PDF file using Playwright (Chromium) for flawless rendering.
    """
    try:
        import markdown
        import re
        from playwright.sync_api import sync_playwright
        
        # 1. Convert Markdown to HTML (Tables, Code Blocks)
        html_content = markdown.markdown(content, extensions=['tables', 'fenced_code', 'sane_lists'])
        
        # 2. Professional CSS Template (Fully supports modern CSS: Flexbox, table-layout, break-word)
        html_template = f"""
        <!DOCTYPE html>
        <html>
        <head>
        <meta charset="UTF-8">
        <style>
            @page {{
                size: A4;
                margin: 20mm;
            }}
            body {{
                font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, Roboto, Helvetica, Arial, sans-serif;
                color: #1f2937;
                line-height: 1.6;
                font-size: 11pt;
            }}
            h1, h2, h3, h4 {{
                color: #111827;
                font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, Roboto, Helvetica, Arial, sans-serif;
                page-break-after: avoid;
            }}
            h1 {{ font-size: 24pt; border-bottom: 2px solid #e5e7eb; padding-bottom: 8px; margin-bottom: 24px; }}
            h2 {{ font-size: 18pt; margin-top: 32px; border-bottom: 1px solid #f3f4f6; padding-bottom: 4px; }}
            h3 {{ font-size: 14pt; margin-top: 24px; }}
            p, ul, ol {{ margin-bottom: 16px; }}
            
            table {{
                width: 100%;
                border-collapse: collapse;
                margin: 24px 0;
                table-layout: fixed; /* Forces strict column constraints */
                word-wrap: break-word; /* Absolutely guarantees no overlap */
                page-break-inside: auto;
            }}
            tr {{ page-break-inside: avoid; page-break-after: auto; }}
            th, td {{
                border: 1px solid #d1d5db;
                padding: 12px;
                text-align: left;
                vertical-align: top;
                overflow-wrap: break-word;
            }}
            th {{
                background-color: #f9fafb;
                font-weight: 600;
                color: #374151;
                font-size: 9pt;
                text-transform: uppercase;
                letter-spacing: 0.05em;
            }}
            tr:nth-child(even) {{ background-color: #f9fafb; }}
            
            code {{
                background-color: #f3f4f6;
                padding: 2px 6px;
                border-radius: 4px;
                font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
                font-size: 9.5pt;
                color: #be185d;
                word-wrap: break-word;
                white-space: pre-wrap;
            }}
            pre {{
                background-color: #1f2937;
                padding: 16px;
                border-radius: 8px;
                overflow-x: auto;
                page-break-inside: avoid;
            }}
            pre code {{
                background-color: transparent;
                color: #e5e7eb;
                padding: 0;
            }}
            blockquote {{
                border-left: 4px solid #9ca3af;
                padding-left: 16px;
                color: #4b5563;
                margin-left: 0;
                font-style: italic;
            }}
        </style>
        </head>
        <body>
            <h1>{title}</h1>
            {html_content}
        </body>
        </html>
        """
        
        # Enforce safe file naming
        safe_filename = re.sub(r'[^a-zA-Z0-9_\-]', '', title.replace(' ', '_').lower())
        if not safe_filename: 
            safe_filename = "summary"
        safe_filename = safe_filename + ".pdf"
        
        # 3. Render PDF flawlessly using Chromium Engine
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.set_content(html_template, wait_until="networkidle")
            page.pdf(
                path=safe_filename,
                format="A4",
                print_background=True,
                margin={"top": "20mm", "bottom": "20mm", "left": "20mm", "right": "20mm"},
                display_header_footer=True,
                footer_template='<div style="font-size: 9px; font-family: sans-serif; text-align: center; width: 100%; color: #6b7280; padding-top: 10px; border-top: 1px solid #e5e7eb;">Page <span class="pageNumber"></span> of <span class="totalPages"></span> &nbsp;|&nbsp; Generated by SOTA Legal RAG</div>',
                header_template="<div></div>"
            )
            browser.close()
            
        return f"Successfully created PDF summary at: {safe_filename}. IMPORTANT MANDATE: In your final chat response to the user, you MUST ONLY output the exact phrase 'Your report is ready.' followed by the relevant [Chunk X] citation tags, and absolutely nothing else! The UI will render the download button."
    except Exception as e:
        logger.error(f"Failed to create PDF: {str(e)}")
        return f"Failed to create PDF: {str(e)}"

def execute_send_message(message: str) -> str:
    """
    Stages a message to an external webhook.
    The actual sending is intercepted and handled by the frontend confirmation button.
    """
    import uuid
    staging_id = str(uuid.uuid4())[:8]
    return f"Message drafted successfully (Staging ID: {staging_id}). IMPORTANT: In your final chat response, you MUST output the exact full text of the drafted message so the user can review it before clicking the UI button!"

def execute_analyze_risk_tier(questions: list) -> str:
    """
    Stages a risk analysis wizard.
    """
    import uuid
    staging_id = str(uuid.uuid4())[:8]
    return f"Risk analysis wizard staged (ID: {staging_id}). The UI will collect the Yes/No answers for these {len(questions)} questions. IMPORTANT: Do NOT output the questions in your text response. Just say 'I have generated a Risk Assessment wizard. Please complete it below.'"
