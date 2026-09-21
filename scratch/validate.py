import json
import random
from collections import Counter

with open('c:/Users/ashis/OneDrive/Documents/GitHub/keggle/letsRAG/data/questions.json', 'r', encoding='utf-8') as f:
    questions = json.load(f)

errors = []
categories = Counter()
sub_types = Counter()
priority_count = 0

for i, q in enumerate(questions):
    cat = q.get('category')
    categories[cat] += 1
    if q.get('priority') is True:
        priority_count += 1
        
    if cat in ['cross-reference', 'stress-test']:
        if 'sub_type' not in q:
            errors.append(f'Q{i}: missing sub_type.')
        else:
            sub_types[q.get('sub_type')] += 1
            
    if cat in ['out-of-scope', 'ambiguous']:
        if q.get('expected_chunks') is not None:
            errors.append(f'Q{i} ({cat}): expected_chunks is not null.')

print('--- Overall Health Check ---')
print(f'Total Questions: {len(questions)}')
print(f'Priority Count: {priority_count} (Instructions said exactly 5)')
print(f'Categories: {dict(categories)}')
print(f'Validation Errors Found: {len(errors)}')
if errors:
    print('First few errors:', errors[:5])

sample = random.sample(questions, 20)
print('\n--- 5 Random Examples from the 20 drawn ---')
for i, q in enumerate(sample[:5]):
    print(f'\n[{q.get("category").upper()}] - Difficulty: {q.get("difficulty")}')
    print(f'Question: {q.get("question")}')
    print(f'Expected Answer: {str(q.get("expected_answer"))[:100]}...')
