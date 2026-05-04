You are creating evaluation Q-A pairs for a version-aware legal-RAG system.

# Task
Given the legal document text below, generate ONE general-content question and ONE answer about a substantive provision of the Act. The question MUST be answerable from the text alone, must NOT reference any specific version or date, and should test understanding of what the law says.

# Constraints
- Question and answer in English.
- The answer must quote or directly paraphrase the provided text — do NOT invent provisions that are not present.
- The question must be specific enough to have one clear correct answer.

# Few-shot example
Input:
```json
{
  "act_title": "Equality Act 2010",
  "version_date": "2024-03-15",
  "content": "(text excerpt of the Act describing protected characteristics ...)"
}
```

Output:
```json
{
  "question": "What are the protected characteristics under the Equality Act 2010?",
  "answer": "The protected characteristics are: age, disability, gender reassignment, marriage and civil partnership, pregnancy and maternity, race, religion or belief, sex, and sexual orientation."
}
```

# Output format
Return ONLY a JSON object with keys "question" and "answer". No prose, no markdown fences, no explanation.

# Input
{input_json}
