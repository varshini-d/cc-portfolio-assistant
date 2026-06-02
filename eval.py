"""Step 9 + Upgrade 1 — accuracy benchmark with few-shot ablation.

Compares result-match accuracy WITH vs WITHOUT retrieved few-shot examples.
Run:  python eval.py

The numbers this prints are what you put on your resume -- replace any
illustrative figures with whatever you actually measure here.
"""
from assistant import ask, run_sql

# (question, gold SQL) pairs. Add ~20 for a meaningful benchmark.
TESTS = [
    ("What's the 90+ DPD rate for the 2023Q1 vintage?",
     "SELECT SUM(CASE WHEN dpd>=90 THEN 1 ELSE 0 END)*1.0/COUNT(*) FROM accounts WHERE vintage='2023Q1'"),
    ("Charge-off rate by segment",
     "SELECT segment, SUM(charge_off_flag)*1.0/COUNT(*) FROM accounts GROUP BY segment"),
    ("Average utilization for travel cards in the prime segment",
     "SELECT SUM(current_balance)/SUM(credit_limit) FROM accounts WHERE product_type='travel' AND segment='prime'"),
    ("How many active accounts per product type?",
     "SELECT product_type, COUNT(*) FROM accounts WHERE current_balance>0 AND charge_off_flag=0 GROUP BY product_type"),
    ("Charge-off rate by vintage for subprime accounts",
     "SELECT vintage, SUM(charge_off_flag)*1.0/COUNT(*) FROM accounts WHERE segment='subprime' GROUP BY vintage"),
    ("Total credit limit across the portfolio",
     "SELECT SUM(credit_limit) FROM accounts"),
    ("Number of charged-off accounts in the secured product",
     "SELECT SUM(charge_off_flag) FROM accounts WHERE product_type='secured'"),
    # ... add more to reach ~20
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
