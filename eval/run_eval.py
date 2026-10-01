import os
import sys
import json
from tqdm import tqdm

# Add root directory to python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.agent.core import SOTAAgent
from app.adapters.llm_adapter import LLMAdapter

def print_metrics(graded_results, batch_idx, total_batches):
    metrics = {
        "overall": {"correct": 0, "total": 0},
        "by_category": {},
        "by_subtype": {}
    }
    
    for r in graded_results:
        score = int(r.get("score", 0))
        cat = r.get("category", "unknown")
        sub = r.get("sub_type", "unknown")
        
        metrics["overall"]["total"] += 1
        metrics["overall"]["correct"] += score
        
        if cat not in metrics["by_category"]:
            metrics["by_category"][cat] = {"correct": 0, "total": 0}
        metrics["by_category"][cat]["total"] += 1
        metrics["by_category"][cat]["correct"] += score
        
        if sub not in metrics["by_subtype"]:
            metrics["by_subtype"][sub] = {"correct": 0, "total": 0}
        metrics["by_subtype"][sub]["total"] += 1
        metrics["by_subtype"][sub]["correct"] += score
        
    print("\n" + "="*60)
    print(f"EVALUATION METRICS (After Batch {batch_idx}/{total_batches})")
    print("="*60)
    
    total = metrics["overall"]["total"]
    correct = metrics["overall"]["correct"]
    print(f"Overall Accuracy: {correct}/{total} ({(correct/total)*100 if total > 0 else 0:.1f}%)")
    
    print("\n--- By Category ---")
    for k, v in metrics["by_category"].items():
        print(f"  {k}: {v['correct']}/{v['total']} ({(v['correct']/v['total'])*100 if v['total'] > 0 else 0:.1f}%)")
        
    print("\n--- By SubType ---")
    for k, v in metrics["by_subtype"].items():
        print(f"  {k}: {v['correct']}/{v['total']} ({(v['correct']/v['total'])*100 if v['total'] > 0 else 0:.1f}%)")
    print("="*60 + "\n")
    
    with open("eval/metrics_report.json", "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2)

def run_eval():
    print("Loading questions...")
    with open("eval/all_140_questions.json", "r", encoding="utf-8") as f:
        all_questions = json.load(f)
        
    print(f"Loaded {len(all_questions)} questions.")

    graded_file = "eval/graded_results.json"
    
    if os.path.exists(graded_file):
        print(f"Found existing graded results in {graded_file}. Resuming...")
        with open(graded_file, "r", encoding="utf-8") as f:
            graded_results = json.load(f)
    else:
        graded_results = []
        
    # Filter out already processed
    processed_qs = {r["question"] for r in graded_results}
    questions_to_process = [q for q in all_questions if q["question"] not in processed_qs]
    
    BATCH_SIZE = 10
    total_batches = (len(all_questions) + BATCH_SIZE - 1) // BATCH_SIZE
    
    if not questions_to_process:
        print("All questions have already been processed!")
        print_metrics(graded_results, total_batches, total_batches)
        return

    print("Initializing SOTA Agent & LLM Evaluator...")
    agent = SOTAAgent()
    llm = LLMAdapter()
    
    # Figure out which batch we are currently starting on
    start_batch = (len(graded_results) // BATCH_SIZE) + 1

    # Chunk the remaining questions into batches
    batches = [questions_to_process[i:i + BATCH_SIZE] for i in range(0, len(questions_to_process), BATCH_SIZE)]
    
    for batch_idx_offset, batch in enumerate(batches):
        current_batch = start_batch + batch_idx_offset
        print(f"\nProcessing Batch {current_batch}/{total_batches} ({len(batch)} questions)...")
        
        # 1. Generate Predictions for the batch
        batch_results = []
        for q in tqdm(batch, desc="Generating Answers"):
            final_content = "Failed to generate answer."
            try:
                response = agent.run(query=q["question"])
                # Agent run returns a single dict with trajectory and final message
                final_content = response.get("generation", "Failed to generate answer.")
            except Exception as e:
                final_content = f"Error: {str(e)}"
                
            batch_results.append({
                "question": q["question"],
                "expected_answer": q["expected_answer"],
                "actual_answer": final_content,
                "category": q.get("category", "unknown"),
                "sub_type": q.get("sub_type", "unknown")
            })

        # 2. Grade Predictions for the batch
        for r in tqdm(batch_results, desc="Grading RAG Groundedness"):
            prompt = f"""You are an expert evaluator assessing a Retrieval-Augmented Generation (RAG) legal AI.
            
Question: {r['question']}
Expected Answer: {r['expected_answer']}
Actual Answer: {r['actual_answer']}

RULES FOR SCORING RAG GROUNDEDNESS & REFUSALS:
1. FOCUS ON GROUNDEDNESS: Check if the Actual Answer semantically captures the factual conclusion of the Expected Answer. DO NOT require literal word-for-word matching.
2. APPROPRIATE DECLINES (CRITICAL): If the question is poorly formed, out-of-scope, or unanswerable according to the Expected Answer, the AI SHOULD decline to answer. If the Actual Answer correctly states that it cannot answer or that the info is missing, you MUST SCORE IT AS 1.
3. Provide a score of 1 if the answer is grounded/correct or appropriately refused. Score 0 if it hallucinated, answered an unanswerable question wrongly, or got the facts wrong.

You MUST output EXACTLY a JSON object in this format (no markdown code blocks, just raw JSON):
{{"score": 1, "reason": "Brief explanation"}}
"""
            try:
                msgs = [{"role": "user", "content": prompt}]
                kwargs = {
                    "model": llm.model,
                    "messages": msgs,
                    "temperature": 0.0,
                    "response_format": {"type": "json_object"}
                }
                response = llm.client.chat.completions.create(**kwargs)
                content = response.choices[0].message.content.strip()
                grade = json.loads(content)
            except Exception as e:
                try:
                    clean = content.replace("```json", "").replace("```", "").strip()
                    grade = json.loads(clean)
                except:
                    grade = {"score": 0, "reason": f"Evaluation parsing failed: {e}"}
                
            r["score"] = grade.get("score", 0)
            r["reason"] = grade.get("reason", "")
            graded_results.append(r)
            
        # Save progress after every batch
        with open(graded_file, "w", encoding="utf-8") as f:
            json.dump(graded_results, f, indent=2)
            
        # Print live updated metrics
        print_metrics(graded_results, current_batch, total_batches)

if __name__ == "__main__":
    run_eval()
