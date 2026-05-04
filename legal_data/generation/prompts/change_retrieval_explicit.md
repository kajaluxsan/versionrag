You are creating evaluation Q-A pairs for a version-aware legal-RAG system.

# Task
Given a textual diff between two point-in-time versions of an Act, generate ONE question and ONE answer about a documented amendment described in the newer version's amendment notes / footnotes / commencement information. The question must explicitly reference the act title and at least one of the two version dates, and the answer must describe a concrete change that is mentioned in the diff text.

This type focuses on EXPLICIT changes — ones that are textually labelled in the document (e.g., "inserted by 2020 c. 12 s. 5", "substituted by 2023 c. 50 Sch. 2 para. 4", "Amendment Note", "Commencement").

# Constraints
- Question and answer in English.
- The question must reference at least one specific version date (the "version_to" date is preferred since that's where the change is recorded).
- The answer must describe what was added/removed/substituted, citing the section/paragraph if visible.
- Do NOT invent amendments that are not in the diff text.
- If no explicit amendment marker is found in the diff, write a question that asks about an amendment described in a footnote — not a generic content question.

# Few-shot example
Input:
```json
{
  "act_title": "Online Safety Act 2023",
  "version_from": "2023-10-26",
  "version_to": "2024-03-15",
  "diff": "(unified diff snippet showing a footnote 'Amendment of section 14 by Schedule 11 of the Online Safety Act 2023 (commencement)' and the inserted/changed text ...)"
}
```

Output:
```json
{
  "question": "What amendment was made to Section 14 of the Online Safety Act 2023 between the 2023-10-26 and 2024-03-15 versions?",
  "answer": "Section 14 was amended by Schedule 11 of the Online Safety Act 2023 to expand the duty of care for user-to-user services, requiring proactive measures against priority illegal content. The change took effect on 2024-03-15."
}
```

# Output format
Return ONLY a JSON object with keys "question" and "answer". No prose, no markdown fences, no explanation.

# Input
{input_json}
