"""Step 2 - the RAG knowledge base for the Lending Club consumer-lending portfolio.

These docs DESCRIBE the data so the LLM can map English -> correct SQL.
Four doc types: schema, metric, example, enum.

SCHEMA_TEXT + GLOSSARY_TEXT are the STATIC content that goes in the cached
system prompt. The `example` docs are retrieved dynamically (RAG) per query.

The schema/glossary here are deliberately thorough: a real credit-risk analyst
needs precise metric definitions, and the richer static block also pushes the
cached prompt past the model's 2048-token caching threshold (see assistant.py).
"""

KB_DOCS = [
    # ---- schema (1 doc; always included statically) ----
    {"doc_type": "schema", "text": """Table: accounts -- one row per consumer loan (Lending Club, 2007-2018).
Columns:
- loan_id (BIGINT): unique loan id
- issue_d (VARCHAR): origination month as 'Mon-YYYY', e.g. 'Dec-2015'
- issue_year (INT): origination year, e.g. 2015
- vintage (VARCHAR): origination quarter cohort, e.g. '2015Q4'
- term_months (INT): loan term in months, either 36 or 60
- grade (VARCHAR): Lending Club credit grade, 'A' (best) through 'G' (worst)
- sub_grade (VARCHAR): finer grade, e.g. 'B3', 'C5'
- risk_tier (VARCHAR): grouped grade -> 'prime' (A,B), 'near-prime' (C,D), 'subprime' (E,F,G)
- purpose (VARCHAR): stated loan purpose, e.g. 'debt_consolidation','credit_card'
- home_ownership (VARCHAR): 'MORTGAGE','RENT','OWN','ANY','OTHER','NONE'
- loan_amnt (DOUBLE): original loan amount in USD
- int_rate (DOUBLE): interest rate as a percent number, e.g. 13.99 means 13.99%
- installment (DOUBLE): fixed monthly payment in USD
- annual_inc (DOUBLE): borrower self-reported annual income in USD
- dti (DOUBLE): debt-to-income ratio as a percent number
- fico_low (DOUBLE): lower bound of the borrower's FICO band at origination
- utilization (DOUBLE): revolving-credit utilization as a percent number (revol_util)
- outstanding_principal (DOUBLE): remaining unpaid principal in USD (0 once closed)
- total_pymnt (DOUBLE): total payments received to date in USD
- addr_state (VARCHAR): borrower US state, 2-letter code, e.g. 'CA'
- loan_status (VARCHAR): current status (see enum)
- charge_off_flag (INT): 1 if the loan charged off, else 0
- is_delinquent (INT): 1 if currently late or in default, else 0"""},

    # ---- metric glossary (static) ----
    {"doc_type": "metric", "text": "Charge-off rate = SUM(charge_off_flag)*1.0/COUNT(*) (equivalently AVG(charge_off_flag)). This is the primary credit-loss metric: the share of loans the lender has written off as uncollectible. Filter or GROUP BY risk_tier, grade, vintage, purpose, term_months, home_ownership, or addr_state as asked. Always multiply by 1.0 (or use AVG) so the ratio is computed in floating point, not integer division."},
    {"doc_type": "metric", "text": "Delinquency rate (currently delinquent) = AVG(is_delinquent) = share of loans currently late (16-30 or 31-120 days) or in Default. This is a point-in-time stress signal and is distinct from charge-off rate, which measures realized, already-booked loss. Do not conflate the two: a loan can be delinquent without (yet) being charged off."},
    {"doc_type": "metric", "text": "Default rate = COUNT(CASE WHEN loan_status='Default' THEN 1 END)*1.0/COUNT(*). Note 'Default' is a rare, specific status distinct from 'Charged Off'; for loss questions use charge-off rate unless the user explicitly says 'default'."},
    {"doc_type": "metric", "text": "Fully-paid rate = COUNT(CASE WHEN loan_status='Fully Paid' THEN 1 END)*1.0/COUNT(*). Among closed loans this is the complement of the charge-off rate. 'Current' loans are still open and are neither fully paid nor charged off."},
    {"doc_type": "metric", "text": "Average interest rate = AVG(int_rate); rates are stored as PERCENT NUMBERS (13.99 means 13.99%, NOT 0.1399). Do not divide by 100 unless the user asks for a fraction. Weighted-average rate by exposure = SUM(int_rate*loan_amnt)/SUM(loan_amnt)."},
    {"doc_type": "metric", "text": "Average loan size = AVG(loan_amnt). Total originated principal = SUM(loan_amnt). Average monthly payment = AVG(installment)."},
    {"doc_type": "metric", "text": "Average utilization = AVG(utilization); revolving-credit utilization is stored as a percent number (e.g. 45.2 = 45.2%). It can be NULL for some borrowers; AVG ignores NULLs automatically, but COUNT(utilization) counts only non-null rows."},
    {"doc_type": "metric", "text": "Average DTI = AVG(dti) (debt-to-income, a percent number). Average FICO at origination = AVG(fico_low). Higher FICO and lower DTI indicate lower risk."},
    {"doc_type": "metric", "text": "Total outstanding principal = SUM(outstanding_principal); this is the live exposure still owed and is 0 for closed (fully paid or charged off) loans. Total payments collected = SUM(total_pymnt)."},
    {"doc_type": "metric", "text": "Vintage analysis: GROUP BY the `vintage` column (origination quarter, e.g. '2015Q4') to compare cohorts over time, or GROUP BY issue_year for annual cohorts. Always ORDER BY the cohort column ascending so the trend reads left-to-right."},
    {"doc_type": "metric", "text": "Active (open, performing) loan = outstanding_principal > 0 AND charge_off_flag = 0. Closed loan = outstanding_principal = 0. 'Open' is roughly loan_status = 'Current'."},
    {"doc_type": "metric", "text": "Loss severity proxy: for charged-off loans, the unrecovered amount approximates loan_amnt - total_pymnt. Recovery rate ideas should be framed cautiously since this snapshot has no separate recovery column beyond total_pymnt."},

    # ---- enum catalog (static) ----
    {"doc_type": "enum", "text": "grade values: A,B,C,D,E,F,G (A = best credit quality, G = worst). sub_grade refines each grade with 1-5, e.g. A1 (best) .. A5, then B1.. through G5 (worst). Lower interest rates go with better grades."},
    {"doc_type": "enum", "text": "risk_tier values: 'prime' (grades A,B), 'near-prime' (grades C,D), 'subprime' (grades E,F,G). When a user says 'prime' or 'subprime', filter on risk_tier; when they name a specific letter, filter on grade."},
    {"doc_type": "enum", "text": "term_months values: 36 or 60 (there are only two terms). Longer 60-month terms generally carry higher rates and higher charge-off rates."},
    {"doc_type": "enum", "text": "purpose values: debt_consolidation, credit_card, home_improvement, major_purchase, medical, small_business, car, vacation, moving, house, wedding, renewable_energy, educational, other. Match the exact lowercase string with underscores."},
    {"doc_type": "enum", "text": "loan_status values: 'Fully Paid', 'Current', 'Charged Off', 'Late (31-120 days)', 'Late (16-30 days)', 'In Grace Period', 'Default'. Match the exact string including capitalization and the day ranges in parentheses."},
    {"doc_type": "enum", "text": "home_ownership values: MORTGAGE, RENT, OWN, ANY, OTHER, NONE (uppercase). vintage format: 'YYYYQn' ranging 2007Q2..2018Q4. addr_state: 2-letter US state codes, e.g. CA, NY, TX, FL."},

    # ---- SQL generation rules (static) ----
    {"doc_type": "rules", "text": """SQL GENERATION RULES (DuckDB dialect):
- Query ONLY the `accounts` table. Never invent columns or join other tables.
- For any rate/share/proportion, compute in floating point: use SUM(flag)*1.0/COUNT(*) or AVG(flag), never integer division.
- Rates stored as percent numbers (int_rate, utilization, dti) are already in percent units; do not rescale unless asked.
- Use CASE WHEN ... THEN 1 END inside COUNT/SUM for conditional counts.
- When grouping, SELECT the grouping column(s) first, then the metric, and add an ORDER BY (the metric DESC for rankings, or the cohort/grade ASC for trends).
- Filter string columns with exact values from the enum lists; respect capitalization and underscores.
- Treat NULLs explicitly when they affect a denominator; AVG and SUM skip NULLs but COUNT(*) does not.
- Prefer readable aliases (e.g. AS charge_off_rate). Return a single SELECT statement."""},

    # ---- few-shot examples (retrieved dynamically via RAG) ----
    {"doc_type": "example", "text": """Q: What's the charge-off rate by risk tier?
SQL: SELECT risk_tier, SUM(charge_off_flag)*1.0/COUNT(*) AS charge_off_rate
     FROM accounts GROUP BY risk_tier ORDER BY charge_off_rate DESC;"""},
    {"doc_type": "example", "text": """Q: Charge-off rate by vintage for subprime loans?
SQL: SELECT vintage, SUM(charge_off_flag)*1.0/COUNT(*) AS charge_off_rate
     FROM accounts WHERE risk_tier='subprime' GROUP BY vintage ORDER BY vintage;"""},
    {"doc_type": "example", "text": """Q: Average interest rate by grade?
SQL: SELECT grade, AVG(int_rate) AS avg_int_rate
     FROM accounts GROUP BY grade ORDER BY grade;"""},
    {"doc_type": "example", "text": """Q: Charge-off rate for credit card loans?
SQL: SELECT SUM(charge_off_flag)*1.0/COUNT(*) AS charge_off_rate
     FROM accounts WHERE purpose='credit_card';"""},
    {"doc_type": "example", "text": """Q: Average revolving utilization by risk tier?
SQL: SELECT risk_tier, AVG(utilization) AS avg_utilization
     FROM accounts GROUP BY risk_tier ORDER BY avg_utilization DESC;"""},
    {"doc_type": "example", "text": """Q: How many loans were issued per purpose?
SQL: SELECT purpose, COUNT(*) AS loan_count
     FROM accounts GROUP BY purpose ORDER BY loan_count DESC;"""},
    {"doc_type": "example", "text": """Q: Total outstanding principal by risk tier?
SQL: SELECT risk_tier, SUM(outstanding_principal) AS outstanding
     FROM accounts GROUP BY risk_tier ORDER BY outstanding DESC;"""},
    {"doc_type": "example", "text": """Q: Charge-off rate for 60-month term loans?
SQL: SELECT SUM(charge_off_flag)*1.0/COUNT(*) AS charge_off_rate
     FROM accounts WHERE term_months=60;"""},
    {"doc_type": "example", "text": """Q: Currently-delinquent rate by grade?
SQL: SELECT grade, AVG(is_delinquent) AS delinquency_rate
     FROM accounts GROUP BY grade ORDER BY grade;"""},
    {"doc_type": "example", "text": """Q: Average loan amount by term?
SQL: SELECT term_months, AVG(loan_amnt) AS avg_loan_amnt
     FROM accounts GROUP BY term_months ORDER BY term_months;"""},
]

# Static slices used to build the cached system prompt.
SCHEMA_TEXT = next(d["text"] for d in KB_DOCS if d["doc_type"] == "schema")
GLOSSARY_TEXT = "\n".join(d["text"] for d in KB_DOCS if d["doc_type"] in ("metric", "enum"))
RULES_TEXT = "\n".join(d["text"] for d in KB_DOCS if d["doc_type"] == "rules")
