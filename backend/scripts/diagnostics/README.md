# Diagnostics

One-off probe scripts used while building and debugging the pipeline. They are kept
for reference and reproducibility, not as part of the application runtime.

| Script | Purpose |
|---|---|
| `diag_analyze_probe.py` | End-to-end `/analyze` probe against a live server |
| `diag_chat_probe.py` | Grounded-chat retrieval / threshold probe |
| `diag_extract_probe.py` | Extractor prompt + parsing probe |
| `diag_groq_probe.py` | Groq connectivity and model availability check |
| `diag_json_probe.py` | JSON-mode validation failure reproduction |
| `diag_models_probe.py` | Lists models exposed by the Groq account |
| `diag_probe.py`, `diag_probe2.py`, `diag_probe3.py` | Store/collection state probes |
| `diag_probe_clear.py` | Clears a Chroma collection for a clean re-index |

Run them from the `backend` directory, e.g.:

```bash
cd backend
python scripts/diagnostics/diag_groq_probe.py
```

They are not imported by the application and are excluded from the test suite.
