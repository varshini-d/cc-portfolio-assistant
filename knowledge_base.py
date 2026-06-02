"""Step 2 — the RAG knowledge base.

These docs DESCRIBE the data so the LLM can map English -> correct SQL.
Four doc types: schema, metric, example, enum.

SCHEMA_TEXT + GLOSSARY_TEXT are the STATIC content that goes in the cached
system prompt. The `example` docs are retrieved dynamically (RAG) per query.
"""

KB_DOCS = [
    # ---- schema (1 doc; always included statically) ----
    {"doc_type": "schema", "text": """Table: accounts -- one row per credit card account.
Columns:
- account_id (INT): unique account id
- vintage (VARCHAR): origination cohort, e.g. '2023Q1'
- product_type (VARCHAR): one of 'cashback','travel','store_card','secured'
- segment (VARCHAR): credit tier, one of 'prime','near-prime','subprime'
- credit_limit (DECIMAL): assigned credit limit
- current_balance (DECIMAL): outstanding balance
- dpd (INT): days past due, 0 = current
- charge_off_flag (INT): 1 if account charged off, else 0"""},

    # ---- metric glossary (static) ----
    {"doc_type": "metric", "text": "90+ DPD rate = COUNT(dpd >= 90) / COUNT(*). Filter or group by segment, vintage, or product_type as asked."},
    {"doc_type": "metric", "text": "Charge-off rate = SUM(charge_off_flag) / COUNT(*)."},
    {"doc_type": "metric", "text": "Utilization = current_balance / credit_limit. Portfolio utilization = SUM(current_balance) / SUM(credit_limit)."},
    {"doc_type": "metric", "text": "Vintage = the quarter an account was originated; group by the `vintage` column."},
    {"doc_type": "metric", "text": "Active account = current_balance > 0 AND charge_off_flag = 0."},

    # ---- enum catalog (static) ----
    {"doc_type": "enum", "text": "Valid vintage values: 2022Q1..2024Q4. product_type: cashback, travel, store_card, secured. segment: prime, near-prime, subprime."},

    # ---- few-shot examples (retrieved dynamically via RAG) ----
    {"doc_type": "example", "text": """Q: What's the 90+ DPD rate for the 2023Q1 vintage?
SQL: SELECT SUM(CASE WHEN dpd>=90 THEN 1 ELSE 0 END)*1.0/COUNT(*) AS dpd90_rate
     FROM accounts WHERE vintage='2023Q1';"""},
    {"doc_type": "example", "text": """Q: Charge-off rate by segment?
SQL: SELECT segment, SUM(charge_off_flag)*1.0/COUNT(*) AS charge_off_rate
     FROM accounts GROUP BY segment ORDER BY charge_off_rate DESC;"""},
    {"doc_type": "example", "text": """Q: Average utilization for travel cards in the prime segment?
SQL: SELECT SUM(current_balance)/SUM(credit_limit) AS utilization
     FROM accounts WHERE product_type='travel' AND segment='prime';"""},
    {"doc_type": "example", "text": """Q: How many active accounts per product type?
SQL: SELECT product_type, COUNT(*) AS active_accounts
     FROM accounts WHERE current_balance>0 AND charge_off_flag=0
     GROUP BY product_type ORDER BY active_accounts DESC;"""},
    {"doc_type": "example", "text": """Q: Charge-off rate by vintage for subprime accounts?
SQL: SELECT vintage, SUM(charge_off_flag)*1.0/COUNT(*) AS charge_off_rate
     FROM accounts WHERE segment='subprime' GROUP BY vintage ORDER BY vintage;"""},
]

# Static slices used to build the cached system prompt.
SCHEMA_TEXT = next(d["text"] for d in KB_DOCS if d["doc_type"] == "schema")
GLOSSARY_TEXT = "\n".join(d["text"] for d in KB_DOCS if d["doc_type"] in ("metric", "enum"))
