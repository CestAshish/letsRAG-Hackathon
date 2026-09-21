import json
import random

with open('c:/Users/ashis/OneDrive/Documents/GitHub/keggle/letsRAG/data/questions.json', 'r', encoding='utf-8') as f:
    all_qs = json.load(f)

# Group by category and sub_type
categorized = {
    'factual': [],
    'cross-reference': {},
    'stress-test': {},
    'out-of-scope': [],
    'ambiguous': []
}

for q in all_qs:
    cat = q['category']
    if cat in ['cross-reference', 'stress-test']:
        st = q['sub_type']
        if st not in categorized[cat]:
            categorized[cat][st] = []
        categorized[cat][st].append(q)
    else:
        categorized[cat].append(q)

selected = []

# 1. Select exactly 10 factual
chosen_factual = random.sample(categorized['factual'], 10)
selected.extend(chosen_factual)
for q in chosen_factual: categorized['factual'].remove(q)

# 2. Select exactly 3 out-of-scope
chosen_out = random.sample(categorized['out-of-scope'], 3)
selected.extend(chosen_out)
for q in chosen_out: categorized['out-of-scope'].remove(q)

# 3. Select exactly 2 ambiguous
chosen_ambiguous = random.sample(categorized['ambiguous'], 2)
selected.extend(chosen_ambiguous)
for q in chosen_ambiguous: categorized['ambiguous'].remove(q)

# 4. Cross-reference: need min 8, covering at least 5 sub-types
cr_subtypes = list(categorized['cross-reference'].keys())
cr_chosen = []
for st in cr_subtypes[:5]:
    if categorized['cross-reference'][st]:
        q = random.choice(categorized['cross-reference'][st])
        cr_chosen.append(q)
        categorized['cross-reference'][st].remove(q)
# We need at least 8, so pick remaining randomly
remaining_cr = [q for lst in categorized['cross-reference'].values() for q in lst]
cr_extra = random.sample(remaining_cr, max(0, 8 - len(cr_chosen)))
cr_chosen.extend(cr_extra)
for q in cr_extra:
    categorized['cross-reference'][q['sub_type']].remove(q)
selected.extend(cr_chosen)

# 5. Stress-test: need min 10, covering at least 8 sub-types
st_subtypes = list(categorized['stress-test'].keys())
st_chosen = []
for st in st_subtypes[:8]:
    if categorized['stress-test'][st]:
        q = random.choice(categorized['stress-test'][st])
        st_chosen.append(q)
        categorized['stress-test'][st].remove(q)
# We need at least 10, so pick remaining randomly
remaining_st = [q for lst in categorized['stress-test'].values() for q in lst]
st_extra = random.sample(remaining_st, max(0, 10 - len(st_chosen)))
st_chosen.extend(st_extra)
for q in st_extra:
    categorized['stress-test'][q['sub_type']].remove(q)
selected.extend(st_chosen)

# 6. Currently selected is 33 questions. We need 17 more to reach exactly 50.
remaining_all = categorized['factual'] + categorized['out-of-scope'] + categorized['ambiguous']
for lst in categorized['cross-reference'].values(): remaining_all.extend(lst)
for lst in categorized['stress-test'].values(): remaining_all.extend(lst)

extra_17 = random.sample(remaining_all, 17)
selected.extend(extra_17)
for q in extra_17:
    remaining_all.remove(q)

# 7. Set exactly 5 to priority = true, rest to false
random.shuffle(selected)
for i, q in enumerate(selected):
    q['priority'] = (i < 5)

for q in remaining_all:
    q['priority'] = False

# Save exactly 50 to questions.json for the assignment submission
with open('c:/Users/ashis/OneDrive/Documents/GitHub/keggle/letsRAG/data/questions.json', 'w', encoding='utf-8') as f:
    json.dump(selected, f, indent=2, ensure_ascii=False)

# Save the remaining 90 to extra_questions.json for your own testing
with open('c:/Users/ashis/OneDrive/Documents/GitHub/keggle/letsRAG/data/extra_questions.json', 'w', encoding='utf-8') as f:
    json.dump(remaining_all, f, indent=2, ensure_ascii=False)

print(f"Saved {len(selected)} assignment questions to questions.json")
print(f"Saved {len(remaining_all)} extra testing questions to extra_questions.json")
