"""Step 1 — build a synthetic credit card portfolio in DuckDB.

This is the data the assistant QUERIES. It is NOT the knowledge base.
Run once:  python build_data.py
"""
import duckdb
import numpy as np
import pandas as pd

np.random.seed(42)
N = 20_000

vintages = [f"{y}Q{q}" for y in (2022, 2023, 2024) for q in (1, 2, 3, 4)]
products = ["cashback", "travel", "store_card", "secured"]
segments = ["prime", "near-prime", "subprime"]

df = pd.DataFrame({
    "account_id": range(1, N + 1),
    "vintage": np.random.choice(vintages, N),
    "product_type": np.random.choice(products, N, p=[0.40, 0.30, 0.20, 0.10]),
    "segment": np.random.choice(segments, N, p=[0.50, 0.30, 0.20]),
    "credit_limit": np.random.choice([1000, 2500, 5000, 10000, 15000], N),
})

# Delinquency probability rises as credit quality falls.
delinq_p = df["segment"].map({"prime": 0.03, "near-prime": 0.10, "subprime": 0.25}).values
df["dpd"] = np.where(
    np.random.rand(N) < delinq_p,
    np.random.choice([30, 60, 90, 120], N),
    0,
)
df["current_balance"] = (df["credit_limit"] * np.random.beta(2, 5, N)).round(2)
df["charge_off_flag"] = ((df["dpd"] >= 120) & (np.random.rand(N) < 0.6)).astype(int)

con = duckdb.connect("portfolio.db")
con.execute("DROP TABLE IF EXISTS accounts")
con.execute("CREATE TABLE accounts AS SELECT * FROM df")
rows, dpd90 = con.execute(
    "SELECT COUNT(*), AVG(CASE WHEN dpd>=90 THEN 1.0 ELSE 0 END) FROM accounts"
).fetchone()
con.close()

print(f"OK  portfolio.db created: {rows} accounts, 90+ DPD rate = {dpd90:.1%}")
