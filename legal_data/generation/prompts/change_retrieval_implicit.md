You are creating evaluation Q-A pairs for a version-aware legal-RAG system.

# Task
Given pairwise textual diffs between **consecutive** point-in-time versions of an Act, generate ONE question and ONE answer about an IMPLICIT change — a change in the legal text itself (added/removed provision, modified definition) that is NOT necessarily labelled with an amendment-marker footnote. The question must ask "in which version was X added/removed/changed". The answer must specify the EXACT version date in which the change first becomes observable.

# Constraints
- Question and answer in English.
- Pick a substantive change (≥ 1 sentence of new or removed material) that you can localize to **exactly one** transition in the `transitions` list — i.e. it appears in the `to` version of that transition but not in the `from` version, and it does not also first occur at any other transition.
- The answer must name the `to` date of that single transition. **Never default to the latest version unless the change actually first appears at the very last transition.**
- The question must phrase the change in terms of WHEN something was added/removed/altered (do NOT mention "section X was substituted by 2020 c. 12" — that style is for the explicit type).
- Do NOT invent provisions that are not in the diffs.
- Skip trivial changes (whitespace, citation reformatting, footnote-marker renumbering, S.I. number-only updates).

# Few-shot example
Input:
```json
{
  "act_title": "Data Protection Act 2018",
  "version_dates": ["2018-05-23", "2020-01-31", "2021-05-04", "2024-03-15"],
  "transitions": [
    {"from": "2018-05-23", "to": "2020-01-31", "diff": "(unified diff snippet showing only minor citation reformatting)"},
    {"from": "2020-01-31", "to": "2021-05-04", "diff": "(unified diff showing the addition of a provision under Section 61 requiring controllers to maintain records of processing activities)"},
    {"from": "2021-05-04", "to": "2024-03-15", "diff": "(unified diff with no further changes in Section 61)"}
  ]
}
```

Output:
```json
{
  "question": "In which version of the Data Protection Act 2018 was the obligation for data controllers to maintain records of processing activities first introduced?",
  "answer": "The obligation for data controllers to maintain records of processing activities first appears in the 2021-05-04 version of the Data Protection Act 2018, in Section 61."
}
```

# Output format
Return ONLY a JSON object with keys "question" and "answer". No prose, no markdown fences, no explanation.

# Input
{input_json}
