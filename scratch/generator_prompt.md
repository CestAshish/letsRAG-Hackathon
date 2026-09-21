# Role
You are an expert AI assisting a student in generating a massive, high-quality test suite for their RAG (Retrieval-Augmented Generation) system based on the EU AI Act.

# The Strategy (140 Questions Total)
We are generating exactly 140 questions by processing the EU AI Act in chunks of 10 pages. There will be 14 chunks in total (the last chunk will have 14 pages). 
For every chunk I provide, you must return exactly **10 high-quality questions** that strictly follow the distribution below.

# Per-Chunk Distribution (Exactly 10 Questions)
Every time I give you a chunk of pages, generate exactly:
1. **3 Factual questions**: Clear, verifiable answers from the text.
2. **2 Cross-reference questions**: Questions that require combining information. (Must use one of these sub-types: `adjacent_chunks`, `same_document`, `repeated`, `contradictory`, `summary_vs_detail`).
3. **3 Stress-test questions**: Tricky questions to break the AI. (Must use one of these sub-types: `paraphrased`, `exact_term`, `yes_no`, `temporal`, `negation`, `multi_hop`, `table_list`, `edge_of_chunk`, `language_variation`, `on_topic_unanswerable`, `multi_part`).
4. **1 Out-of-scope question**: A question the system should NOT answer, loosely related to the current topic but unanswerable from the text.
5. **1 Ambiguous question**: A vague question where a human would ask for clarification.

*(Note: Ensure 1 out of the 10 questions in each batch is marked `"priority": true` to signify it's a critical, core-use-case question.)*

# Input Format
I will provide the JSON data of the extracted pages for the current chunk.
Example:
```json
[
  {"source": "EU_AI_Act.pdf", "page": 1, "text": "..."},
  {"source": "EU_AI_Act.pdf", "page": 2, "text": "..."}
]
```

# Output Format
Output ONLY valid JSON containing the 10 new questions. Do not include markdown code blocks (```json) around the output, just raw JSON. Do not include a counter, just the array of questions.

[
  {
    "question": "...",
    "expected_answer": "...",
    "source": "EU_AI_Act.pdf",
    "page": <page_number_integer>,
    "category": "<factual|cross-reference|stress-test|out-of-scope|ambiguous>",
    "sub_type": "<include ONLY if category is cross-reference or stress-test>",
    "difficulty": "<easy|medium|hard>",
    "priority": <true_or_false>,
    "expected_chunks": [
      {"source": "EU_AI_Act.pdf", "page": <page_number_integer>}
    ] // NOTE: Set this exactly to `null` (not an empty array) for out-of-scope and ambiguous questions.
  }
]
