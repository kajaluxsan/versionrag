You are creating evaluation Q-A pairs for a version-aware legal-RAG system.

# Task
Given the act title and the list of indexed point-in-time versions, generate ONE meta-question about which versions of the Act are available, and ONE answer that lists those versions. The question must test the system's ability to enumerate versions, not the legal content.

# Constraints
- Question and answer in English.
- Question phrasing variants are acceptable: "Which versions of X are indexed?", "How many versions of X do you have?", "List all available versions of X.", etc.
- The answer must list ALL the dates from the input, in a clear format.
- Do NOT invent versions that are not in the input list.

# Few-shot example
Input:
```json
{
  "act_title": "Data Protection Act 2018",
  "version_dates": ["2018-05-23", "2021-05-04", "2022-11-01", "2023-06-26", "2024-03-15"]
}
```

Output:
```json
{
  "question": "Which point-in-time versions of the Data Protection Act 2018 are indexed?",
  "answer": "The indexed versions are: 2018-05-23, 2021-05-04, 2022-11-01, 2023-06-26, and 2024-03-15."
}
```

# Output format
Return ONLY a JSON object with keys "question" and "answer". No prose, no markdown fences, no explanation.

# Input
{input_json}
