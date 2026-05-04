# Iteration 3 — Indexing & Evaluation auf UK Legal Korpus

## Was hier liegt

| Datei | Zweck |
|---|---|
| `prompts/extract_attributes.md` | UK-Legal-spezifischer System-Prompt für `AttributeExtractor` |
| `prompts/query_parser.md` | UK-Legal-spezifischer System-Prompt für `QueryParser` |
| `index_uk.py` | Wrapper: indexiert `OD/documents/` via API |
| `evaluate_uk.py` | Wrapper: evaluiert `OD/dataset/eval_set.csv` + scored + Summary |
| `compare_results.py` | Side-by-Side UK vs Node.js Score-Vergleich |

## Voraussetzung — `.env` anpassen

Bevor du den Server neu startest, in `version-aware-RAG/.env` zwei Variablen
auf **absolute Pfade** setzen:

```env
VERSIONRAG_EXTRACT_PROMPT=/Users/kajaluxanmathitharan/Documents/Projects/ZHAW/SEM8/BA/OD/indexing/prompts/extract_attributes.md
VERSIONRAG_QUERY_PROMPT=/Users/kajaluxanmathitharan/Documents/Projects/ZHAW/SEM8/BA/OD/indexing/prompts/query_parser.md
```

(Vorher waren beide leer → Default-Prompts → Node.js-Verhalten. Jetzt zeigen
sie auf die UK-Prompts.)

## Runbook (Make-Targets)

```bash
# Alles im Repo-Root version-aware-RAG/ ausführen
cd /Users/kajaluxanmathitharan/Documents/Projects/ZHAW/SEM8/BA/version-aware-RAG

# 1. Server neu starten, damit er die neuen Env-Vars aufnimmt
# Falls bereits läuft: stoppen mit Ctrl-C, dann:
make start

# 2-4. UK-Korpus indexieren + evaluieren + vergleichen (in zweitem Terminal)
cd /Users/kajaluxanmathitharan/Documents/Projects/ZHAW/SEM8/BA/version-aware-RAG
make uk-all
```

`make uk-all` ist Kurzform für:
```bash
make uk-index      # python3 OD/indexing/index_uk.py
make uk-evaluate   # python3 OD/indexing/evaluate_uk.py
make uk-compare    # python3 OD/indexing/compare_results.py
```

Du kannst die Targets auch einzeln laufen lassen.

## Output-Files (in `version-aware-RAG/data/results/`)

| Datei | Inhalt |
|---|---|
| `evaluation_answers_uk.csv` | LLM-Antworten je Frage |
| `evaluation_scored_uk.csv` | + Score-Spalte (LLM-as-judge) |
| `evaluation_summary_uk.txt` | **Final-Deliverable** für Thesis |

## Zurück zu Node.js

Beide Env-Vars in `.env` wieder leer setzen, Server neu starten, Node.js-Korpus
neu indexieren (`make eval-all`).

## Nach der Thesis aufräumen

Diese Iteration ist BA-thesis-spezifisch. Zum Entfernen:
1. Im `version-aware-RAG/Makefile` den Block `# UK Legal Iteration … --- end UK Legal block ---` löschen (und die vier `uk-*` Namen aus `.PHONY`)
2. Den ganzen Ordner `OD/indexing/` löschen
3. Beide `VERSIONRAG_*_PROMPT` Variablen in `.env` und `.env.example` löschen (oder die Patches in `attribute_extractor.py`/`query_parser.py` zurücksetzen — siehe Plan-Datei `Rollback`-Sektion)

## Zur Plan-Datei

Vollständige Begründung + Patches in
`/Users/kajaluxanmathitharan/.claude/plans/https-huggingface-co-datasets-ncbi-pubme-declarative-horizon.md`
(Iteration 3 Sektion).
