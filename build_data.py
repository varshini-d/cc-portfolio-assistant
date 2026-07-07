"""Step 1 - load + clean a REAL consumer-lending portfolio into DuckDB.

Source: Lending Club accepted loans 2007-2018 (~2.26M rows, 151 cols).
This is the data the assistant QUERIES. It is NOT the knowledge base.

Design:
  - LOCAL:  if the raw Lending Club CSV is present under data/raw/, we clean it,
            trim to the columns we care about, take a reproducible sample, and
            write BOTH portfolio.db (DuckDB) and data/portfolio.parquet.
  - DEPLOY: if the raw CSV is absent (e.g. on a host) but the committed
            data/portfolio.parquet exists, we just load that into portfolio.db.

So you commit only the small Parquet; the giant raw CSV stays on your machine.

Run once:  python build_data.py
"""
import glob
import os

import duckdb

SAMPLE_ROWS = 250_000          # rows kept in the queried table (None = keep all)
SEED = 42                      # reproducible sample
PARQUET = "data/portfolio.parquet"

# The cleaning SELECT. One row per loan. Honest, real columns only -- no faked DPD.
CLEAN_SQL = """
SELECT
    TRY_CAST(id AS BIGINT)                          AS loan_id,
    issue_d,                                                              -- 'Dec-2015'
    CAST(strftime(strptime(issue_d, '%b-%Y'), '%Y') AS INT)              AS issue_year,
    strftime(strptime(issue_d, '%b-%Y'), '%Y') || 'Q'
        || CAST(quarter(strptime(issue_d, '%b-%Y')) AS VARCHAR)         AS vintage,   -- '2015Q4'
    CAST(TRIM(REPLACE(term, 'months', '')) AS INT)                      AS term_months,
    grade,
    sub_grade,
    CASE
        WHEN grade IN ('A','B') THEN 'prime'
        WHEN grade IN ('C','D') THEN 'near-prime'
        ELSE 'subprime'
    END                                                                 AS risk_tier,
    purpose,
    home_ownership,
    loan_amnt,
    int_rate,
    installment,
    annual_inc,
    dti,
    fico_range_low                                                      AS fico_low,
    revol_util                                                          AS utilization,
    out_prncp                                                           AS outstanding_principal,
    total_pymnt,
    addr_state,
    loan_status,
    CASE WHEN loan_status LIKE '%Charged Off%' THEN 1 ELSE 0 END        AS charge_off_flag,
    CASE WHEN loan_status LIKE 'Late%' OR loan_status = 'Default'
         THEN 1 ELSE 0 END                                             AS is_delinquent
FROM raw
WHERE grade IS NOT NULL          -- drops the ~33 blank trailing rows
  AND issue_d IS NOT NULL
  AND loan_status NOT IN ('None')
"""


def find_raw_csv():
    """Find the largest *.csv under data/raw/ (handles the nested-folder unzip)."""
    candidates = glob.glob("data/raw/**/*.csv", recursive=True)
    candidates = [c for c in candidates if os.path.getsize(c) > 1_000_000]
    return max(candidates, key=os.path.getsize) if candidates else None


def build_from_csv(con, csv_path):
    print(f"Loading raw CSV: {csv_path}")
    con.execute(
        f"CREATE OR REPLACE VIEW raw AS SELECT * FROM "
        f"read_csv_auto('{csv_path}', sample_size=200000, types={{'id': 'VARCHAR'}})"
    )
    sample = (f"USING SAMPLE {SAMPLE_ROWS} ROWS (reservoir, {SEED})"
              if SAMPLE_ROWS else "")
    con.execute("DROP TABLE IF EXISTS accounts")
    con.execute(f"CREATE TABLE accounts AS {CLEAN_SQL} {sample}")
    os.makedirs("data", exist_ok=True)
    con.execute(f"COPY accounts TO '{PARQUET}' (FORMAT PARQUET)")
    print(f"Wrote committed sample -> {PARQUET}")


def build_from_parquet(con):
    print(f"Raw CSV not found; loading committed sample: {PARQUET}")
    con.execute("DROP TABLE IF EXISTS accounts")
    con.execute(f"CREATE TABLE accounts AS SELECT * FROM read_parquet('{PARQUET}')")


def main():
    con = duckdb.connect("portfolio.db")
    csv_path = find_raw_csv()
    if csv_path:
        build_from_csv(con, csv_path)
    elif os.path.exists(PARQUET):
        build_from_parquet(con)
    else:
        raise SystemExit(
            "No data found. Put the Lending Club CSV under data/raw/ "
            f"or provide {PARQUET}."
        )

    rows, co_rate, dq_rate = con.execute("""
        SELECT COUNT(*),
               AVG(charge_off_flag),
               AVG(is_delinquent)
        FROM accounts
    """).fetchone()
    vmin, vmax = con.execute(
        "SELECT MIN(issue_year), MAX(issue_year) FROM accounts"
    ).fetchone()
    con.close()

    print(f"OK  portfolio.db created: {rows:,} loans, "
          f"vintages {vmin}-{vmax}, "
          f"charge-off rate = {co_rate:.1%}, currently-delinquent = {dq_rate:.1%}")


if __name__ == "__main__":
    main()
