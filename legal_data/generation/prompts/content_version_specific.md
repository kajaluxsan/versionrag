You are creating evaluation Q-A pairs for a version-aware legal-RAG system.

# Task
Given the legal document text from ONE specific point-in-time version of an Act, generate ONE question and ONE answer that test version-specific content. The question MUST explicitly reference the version date AND ask about content that is present in that version. The answer MUST also reference the version date.

# Constraints
- Question and answer in English.
- The question must mention the act title and the version date (e.g. "What did Section 7 of X say in the YYYY-MM-DD version?").
- The answer must paraphrase or quote text from the provided content, and explicitly reference the version date.
- Do NOT invent content that is not present in the text.

# Few-shot example
Input:
```json
{
  "act_title": "Equality Act 2010",
  "version_date": "2020-06-15",
  "content": "(text excerpt of Section 7 from the 2020-06-15 version describing gender reassignment ...)"
}
```

Output:
```json
{
  "question": "What did Section 7 of the Equality Act 2010 state in the 2020-06-15 version?",
  "answer": "In the 2020-06-15 version of the Equality Act 2010, Section 7 defined gender reassignment as a protected characteristic, applying to a person who is proposing to undergo, is undergoing or has undergone a process to reassign their sex."
}
```

# Output format
Return ONLY a JSON object with keys "question" and "answer". No prose, no markdown fences, no explanation.

# Input
{input_json}
