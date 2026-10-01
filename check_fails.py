import json
with open('eval/ambiguous_graded_results.json', 'r', encoding='utf-8') as f:
    results = json.load(f)
failures = [r for r in results if r.get('score') == 0]
for idx, r in enumerate(failures):
    print(f'\n--- Failure {idx+1} ---')
    print(f'Question: {r.get("question")}')
    print(f'Actual Answer: {r.get("actual_answer")}')
    print(f'Expected Answer: {r.get("expected_answer")}')
    print(f'Reason: {r.get("reason")}')
