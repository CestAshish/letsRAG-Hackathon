# EU AI Act Legal RAG Agent

A highly sophisticated Retrieval-Augmented Generation (RAG) assistant designed to help legal professionals, developers, and policymakers navigate, analyze, and classify systems under the **EU AI Act (Regulation (EU) 2024/1689)**.

The system features a Python/FastAPI backend powered by Groq's high-speed inference, a React/Vite frontend with an interactive PDF chunk viewer, and a suite of specialized agentic tools.

## 🚀 Features & Tool Flows

The AI agent is equipped with several powerful tools that it can dynamically chain together to solve complex legal queries:

1. **Semantic Search (`search_content`)**
   - **Flow**: User asks a conceptual question (e.g., "What are the rules for biometric categorization?"). The agent executes a semantic search across the embedded AI Act database.
   - **Protection**: Includes a strict python-level keyword interceptor to strip out noisy boilerplate words ("EU AI Act", "Act") to protect vector math integrity. Features an automatic 2-turn batch-query fallback for vague questions.

2. **Structural Search (`search_structure`)**
   - **Flow**: User asks for a specific Article, Chapter, or Annex (e.g., "Show me Article 51"). The agent bypasses semantic search and instantly retrieves the exact structural nodes from the document tree.

3. **Risk Assessment Wizard (`analyze_risk_tier`)**
   - **Flow**: User asks to classify their AI system.
   - 1. Agent asks for a basic description.
   - 2. Agent invokes the wizard tool, which renders an interactive UI questionnaire in the React frontend.
   - 3. User submits answers via the UI.
   - 4. Agent automatically batches the answers into a multi-query search to find the exact rules, then determines the risk tier.

4. **PDF Report Generation (`create_pdf_summary`)**
   - **Flow**: User asks for a formal summary or the agent finishes a Risk Assessment. The agent compiles the data, generates HTML, and the backend converts it into a beautifully styled PDF document with a dedicated "References" section. 

5. **Teams Webhook (`send_message`)**
   - **Flow**: User asks to notify their team. The agent drafts a professional message, shows a preview in the UI, and upon user approval, dispatches it to a Microsoft Teams channel via a webhook URL.

6. **Mathematical Calculator (`calculator`)**
   - **Flow**: User asks to calculate potential fines (e.g., "35 million EUR or 7% of 1.2 billion"). The agent strictly avoids mental math, batches the equations into the calculator tool, and returns precise results.

---

## 🛠️ Setup Instructions

Follow these exact steps to run the project from a fresh zip extraction.

### 1. Environment Configuration

1. In the root directory of the project, you will find a `.env.example` file.
2. Rename or copy it to `.env`:
   ```bash
   cp .env.example .env
   ```
3. Open `.env` and configure your API keys. You can choose between **Groq** (default) or **OpenAI**:
   - `LLM_PROVIDER`: Set to `groq` or `openai`.
   - `OPENAI_API_KEY`: Your OpenAI API key (if using `openai`). Defaults to `gpt-4o-mini`.
   - `GROQ_API_KEY`: Your Groq API key (if using `groq`). Defaults to `openai/gpt-oss-20b`.
   - `TEAMS_WEBHOOK_URL`: Your Microsoft Teams webhook URL (required for the `send_message` tool).

### 2. Backend Setup (Python)

This project uses `uv` for lightning-fast Python package management. 

1. Ensure you have Python 3.11+ and `uv` installed.
2. Open a terminal in the root directory.
3. Sync the dependencies and create a virtual environment:
   ```bash
   uv sync
   ```
4. Activate the virtual environment:
   - **Windows**: `.venv\Scripts\activate`
   - **Mac/Linux**: `source .venv/bin/activate`
5. *(Optional)* If you want to use the PDF generation feature, ensure `playwright` browsers are installed (if using playwright adapter, otherwise `fpdf2` is already installed via requirements).
6. Start the FastAPI backend:
   ```bash
   uvicorn app.main:app --reload --port 8000
   ```

### 3. Frontend Setup (React/Vite)

1. Open a **second** terminal window.
2. Navigate to the frontend directory:
   ```bash
   cd frontend
   ```
3. Install the Node.js dependencies:
   ```bash
   npm install
   ```
4. Start the Vite development server:
   ```bash
   npm run dev
   ```
5. Open your browser and navigate to the URL provided by Vite (usually `http://localhost:5173`).

---

## 🏗️ Architecture & Interaction

- **State Isolation**: The React frontend uses isolated chat states. You can open multiple chats in the sidebar without loading statuses or messages bleeding between them.
- **Citation Mechanics**: The agent outputs standard Markdown links (e.g., `[Article 51](#chunk-1)`). The ReactMarkdown engine intercepts these `#chunk-X` links and turns them into interactive UI triggers that open the original PDF directly to the highlighted source text.
- **Telemetry**: All LLM actions, tool arguments, and execution times are logged natively into `app/data/telemetry/`. Click "View Analytics & Logs" on any AI message to see the exact decision tree.
