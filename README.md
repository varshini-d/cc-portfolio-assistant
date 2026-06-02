# Credit Card Portfolio Analytics Assistant — Text-to-SQL with RAG

A natural-language analytics assistant over a credit card portfolio. You ask a
business question ("90+ DPD rate for 2023Q1 originations by product"); the system
retrieves schema + metric context (RAG), generates DuckDB SQL with Claude,
executes it, and returns the numbers plus a plain-English summary.

**Stack:** Python · Claude API (`claude-sonnet-4-6`) · FAISS · sentence-transformers · DuckDB · Streamlit

## Architecture

```
question
   |
   v
retrieve few-shot examples (FAISS over the KB)        <-- RAG, dynamic
   |
   v
Claude generates SQL                                  <-- static schema/glossary cached
   |
   v
execute on DuckDB --(error?)--> retry once with the error fed back   <-- self-correction
   |
   v
Claude summarizes the result in plain English
```

## Knowledge base vs data

- **Data (queried):** a synthetic `accounts` table in DuckDB (`build_data.py`).
- **Knowledge base (retrieved):** schema, a credit-risk metric glossary
  (90+ DPD, utilization, charge-off rate, vintage), enums, and question->SQL
  examples (`knowledge_base.py`). This is what makes the SQL correct.

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate            # Windows  (use: source .venv/bin/activate on macOS/Linux)
pip install -r requirements.txt
copy .env.example .env            # then paste your ANTHROPIC_API_KEY

python build_data.py              # create portfolio.db
python index.py                   # build the FAISS index over the KB
python assistant.py               # smoke test one question
streamlit run app.py              # launch the UI
```

## Upgrades included

1. **Few-shot retrieval ablation** (`eval.py`) — measures result-match accuracy
   WITH vs WITHOUT retrieved examples, so you can quantify what RAG buys you.
   Run `python eval.py`; put the real numbers on your resume.
2. **Prompt caching** — the static instructions + schema + glossary go in a
   cached `system` block (`cache_control: {"type": "ephemeral"}`); only the
   retrieved examples + question vary per call.

   > **Sonnet 4.6 caveat:** the cached prefix must be **>= 2048 tokens** or it
   > silently won't cache (`cache_creation_input_tokens` stays 0). This KB is
   > small, so caching may not trigger until the static block grows past that
   > threshold. `generate_sql(..., verbose=True)` prints the usage fields
   > (`input`, `cache_create`, `cache_read`) so you can verify. To force a real
   > cache hit, expand the static schema/glossary, or accept that caching is a
   > no-op at this KB size and note the threshold as the reason.

## Resume bullets (replace metrics with your measured numbers)

- Built a text-to-SQL analytics assistant over a credit card portfolio, using
  RAG over a schema + metric glossary to ground query generation in the real
  schema; returned executable SQL plus a plain-English summary.
- Added a self-correction retry loop that feeds SQL execution errors back to the
  model, raising result-match accuracy from XX% to YY% on a NN-question benchmark.
- Quantified RAG value via a few-shot ablation (+ZZ pts with retrieved examples)
  and cached the static schema/glossary context to cut per-query input cost.
