"""Step 9 + Upgrade 1 — accuracy benchmark with few-shot ablation.

Compares result-match accuracy WITH vs WITHOUT retrieved few-shot examples.
Run:  python eval.py

The numbers this prints are what you put on your resume -- replace any
illustrative figures with whatever you actually measure here.
"""
from assistant import ask, run_sql

# (question, gold SQL) pairs over the real Lending Club schema.
TESTS = [
    ("What's the charge-off rate by risk tier?",
     "SELECT risk_tier, SUM(charge_off_flag)*1.0/COUNT(*) FROM accounts GROUP BY risk_tier"),
    ("What is the overall charge-off rate?",
     "SELECT SUM(charge_off_flag)*1.0/COUNT(*) FROM accounts"),
    ("Average interest rate by grade",
     "SELECT grade, AVG(int_rate) FROM accounts GROUP BY grade"),
    ("Charge-off rate for credit card loans",
     "SELECT SUM(charge_off_flag)*1.0/COUNT(*) FROM accounts WHERE purpose='credit_card'"),
    ("Charge-off rate by vintage for subprime loans",
     "SELECT vintage, SUM(charge_off_flag)*1.0/COUNT(*) FROM accounts WHERE risk_tier='subprime' GROUP BY vintage"),
    ("Average revolving utilization by risk tier",
     "SELECT risk_tier, AVG(utilization) FROM accounts GROUP BY risk_tier"),
    ("How many loans were issued per purpose?",
     "SELECT purpose, COUNT(*) FROM accounts GROUP BY purpose"),
    ("Total outstanding principal by risk tier",
     "SELECT risk_tier, SUM(outstanding_principal) FROM accounts GROUP BY risk_tier"),
    ("Charge-off rate for 60-month term loans",
     "SELECT SUM(charge_off_flag)*1.0/COUNT(*) FROM accounts WHERE term_months=60"),
    ("Currently-delinquent rate by grade",
     "SELECT grade, AVG(is_delinquent) FROM accounts GROUP BY grade"),
    ("Average loan amount by term",
     "SELECT term_months, AVG(loan_amnt) FROM accounts GROUP BY term_months"),
    ("How many loans are there in total?",
     "SELECT COUNT(*) FROM accounts"),
    ("Total number of charged-off loans",
     "SELECT SUM(charge_off_flag) FROM accounts"),
    ("Average FICO by risk tier",
     "SELECT risk_tier, AVG(fico_low) FROM accounts GROUP BY risk_tier"),
    ("Average DTI for subprime loans",
     "SELECT AVG(dti) FROM accounts WHERE risk_tier='subprime'"),
    ("Total originated principal across the portfolio",
     "SELECT SUM(loan_amnt) FROM accounts"),
    ("Number of loans by grade",
     "SELECT grade, COUNT(*) FROM accounts GROUP BY grade"),
    ("Average interest rate for 36-month loans",
     "SELECT AVG(int_rate) FROM accounts WHERE term_months=36"),
    ("Charge-off rate by home ownership",
     "SELECT home_ownership, SUM(charge_off_flag)*1.0/COUNT(*) FROM accounts GROUP BY home_ownership"),
    ("Number of loans in the subprime tier",
     "SELECT COUNT(*) FROM accounts WHERE risk_tier='subprime'"),
]


def _matches(pred, gold):
    if pred is None or gold is None:
        return False
    try:
        return sorted(pred.round(4).values.tolist()) == sorted(gold.round(4).values.tolist())
    except Exception:
        return False


def score(use_examples):
    ok = 0
    for question, gold_sql in TESTS:
        gold, _ = run_sql(gold_sql)
        out = ask(question, use_examples=use_examples)
        hit = _matches(out["result"], gold)
        ok += hit
        print(f"  {'PASS' if hit else 'FAIL'}  {question}")
    return ok / len(TESTS)


if __name__ == "__main__":
    print("== WITH few-shot examples ==")
    with_ex = score(True)
    print("\n== WITHOUT few-shot examples ==")
    without_ex = score(False)
    print("\n--------------------------------")
    print(f"With few-shot examples:    {with_ex:.0%}")
    print(f"Without few-shot examples: {without_ex:.0%}")
    print(f"Lift from RAG retrieval:   +{(with_ex - without_ex) * 100:.0f} pts")
