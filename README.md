# Consumer Lending Portfolio Analytics Assistant — Text-to-SQL with RAG

A natural-language analytics assistant over a **real consumer-lending portfolio**
(Lending Club, 2007–2018, ~2.26M loans). You ask a business question
("charge-off rate by vintage for subprime loans"); the system retrieves schema +
metric context (RAG), generates DuckDB SQL with Claude, executes it, and returns
the numbers plus a plain-English summary.

**Stack:** Python · Claude API (`claude-sonnet-4-6`) · FAISS · sentence-transformers · DuckDB · Streamlit

## Architecture

```
question
   |
   v
retrieve few-shot examples (FAISS over the KB)        <-- RAG, dynamic
   |
   v
Claude generates SQL                                  <-- static schema/glossary/rules cached
   |
   v
execute on DuckDB --(error?)--> retry once with the error fed back   <-- self-correction
   |
   v
Claude summarizes the result in plain English
```

## Knowledge base vs data

- **Data (queried):** a cleaned `accounts` table in DuckDB, derived from the real
  Lending Club accepted-loans file (`build_data.py`). One row per loan, ~20
  columns: grade, risk tier, vintage, purpose, term, interest rate, utilization,
  FICO, DTI, outstanding principal, loan status, charge-off flag, etc.
- **Knowledge base (retrieved):** schema, a credit-risk metric glossary
  (charge-off rate, delinquency rate, utilization, vintage, weighted-average
  rate), enums (grade A–G, risk tiers, loan statuses), SQL-generation rules, and
  question→SQL examples (`knowledge_base.py`). This is what makes the SQL correct.

### Getting the data

The raw Lending Club CSV is ~1.6 GB and **not** committed. Two ways to run:

1. **With the raw file (recommended for the real numbers):** download
   `accepted_2007_to_2018Q4.csv` from Kaggle
   ([wordsforthewise/lending-club](https://www.kaggle.com/datasets/wordsforthewise/lending-club)),
   unzip it, and drop it anywhere under `data/raw/`. `build_data.py` finds it,
   cleans it, takes a reproducible 250k-row sample, and writes both
   `portfolio.db` and a small `data/portfolio.parquet`.
2. **Without the raw file (e.g. on a host):** the committed
   `data/portfolio.parquet` (~8.5 MB) is loaded directly. No download needed.

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate            # Windows  (use: source .venv/bin/activate on macOS/Linux)
pip install -r requirements.txt
copy .env.example .env            # then paste your ANTHROPIC_API_KEY

python build_data.py              # create portfolio.db (from CSV or committed parquet)
python index.py                   # build the FAISS index over the KB
python assistant.py               # smoke test one question
streamlit run app.py              # launch the UI
```

## Upgrades included

1. **Few-shot retrieval ablation** (`eval.py`) — measures result-match accuracy
   WITH vs WITHOUT retrieved examples on a 20-question benchmark, so you can
   quantify what RAG buys you. Run `python eval.py`.
2. **Prompt caching** — the static instructions + schema + glossary + SQL rules
   go in a cached `system` block (`cache_control: {"type": "ephemeral"}`); only
   the retrieved examples + question vary per call. The static block is ~2,035
   tokens, which clears Sonnet 4.6's caching threshold, so every call after the
   first reads it from cache (`generate_sql(..., verbose=True)` prints
   `cache_read` to verify). Cached tokens bill at ~10% of fresh input tokens.

## Measured results (your numbers — re-run `eval.py` to reproduce)

- **Result-match accuracy:** 100% with RAG vs 90% without, on a 20-question
  benchmark → **+10 points from few-shot retrieval**.
- The queries RAG fixes are the domain-specific ones (e.g. charge-off rate by
  vintage for a given risk tier) — simple aggregates pass either way.
- **Prompt caching:** ~2,035 static tokens cached and reused per query
  (`cache_read=2035`), so only ~100–200 dynamic tokens are re-sent per call.

## Resume bullets

- Built a text-to-SQL analytics assistant over a real ~2.26M-loan Lending Club
  consumer-credit portfolio, using RAG over a schema + credit-risk metric
  glossary to ground query generation in the real schema; returned executable
  DuckDB SQL plus a plain-English summary.
- Added a self-correction retry loop that feeds SQL execution errors back to the
  model; quantified RAG value via a few-shot ablation (100% vs 90% result-match
  accuracy, +10 pts) on a 20-question benchmark.
- Cut per-query input cost by caching the ~2,035-token static schema/glossary/rules
  block (cached tokens bill at ~10% of fresh), keeping only retrieved examples +
  the question dynamic.

## Deploying

The committed `data/portfolio.parquet` makes the app hostable without the raw
CSV. On Streamlit Community Cloud, point it at `app.py` and set
`ANTHROPIC_API_KEY` as a secret. Note: every visitor query spends API credit —
add a budget cap, or let visitors supply their own key, before sharing publicly.
