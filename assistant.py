"""Steps 4-7 + both upgrades — the core retrieve -> generate SQL -> execute ->
self-correct -> summarize loop.

Design note (prompt caching vs RAG):
  Prompt caching needs a STATIC prefix; RAG retrieval is DYNAMIC per query.
  So we split the prompt:
    - cached system block  = instructions + schema + glossary + enums (static)
    - dynamic user message = retrieved few-shot examples + the question
  On Sonnet 4.6 the cached prefix must be >= 2048 tokens or it silently won't
  cache (cache_creation_input_tokens stays 0). This KB is small, so caching may
  not trigger until the static block grows past that threshold -- generate_sql()
  prints the usage fields so you can see exactly what happened.
"""
import os
import pickle
import re

import duckdb
import faiss
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer
from anthropic import Anthropic

from knowledge_base import SCHEMA_TEXT, GLOSSARY_TEXT

load_dotenv()
client = Anthropic()                       # reads ANTHROPIC_API_KEY from env
embedder = SentenceTransformer("all-MiniLM-L6-v2")
index = faiss.read_index("kb.index")
KB = pickle.load(open("kb_meta.pkl", "rb"))

MODEL = "claude-sonnet-4-6"                 # user-specified model

# Static content -> identical on every call -> cacheable.
STATIC_SYSTEM = f"""You write DuckDB SQL for a table called `accounts`.
Use ONLY the schema and metric definitions below. Never invent columns.
Return ONLY the SQL inside a ```sql code block.

SCHEMA:
{SCHEMA_TEXT}

METRICS & ENUMS:
{GLOSSARY_TEXT}"""


# ----- Step 4 (+ Upgrade 1 ablation flag): retrieval -----
def retrieve_examples(question, k=3, use_examples=True):
    """Return up to k retrieved few-shot example texts (dynamic RAG part)."""
    if not use_examples:
        return []
    q = embedder.encode([question], normalize_embeddings=True).astype("float32")
    _, idx = index.search(q, k * 2)
    examples = [KB[i]["text"] for i in idx[0] if KB[i]["doc_type"] == "example"]
    return examples[:k]


# ----- Step 5 (+ Upgrade 2 caching): generate SQL -----
def generate_sql(question, examples, error=None, verbose=False):
    fix = f"\n\nThe previous SQL failed with this error:\n{error}\nReturn corrected SQL." if error else ""
    ex_block = ("Relevant examples:\n" + "\n\n".join(examples) + "\n\n") if examples else ""
    resp = client.messages.create(
        model=MODEL,
        max_tokens=500,
        temperature=0,                     # deterministic SQL (allowed on Sonnet 4.6)
        system=[{
            "type": "text",
            "text": STATIC_SYSTEM,
            "cache_control": {"type": "ephemeral"},   # cache the static prefix
        }],
        messages=[{"role": "user", "content": f"{ex_block}QUESTION: {question}{fix}"}],
    )
    if verbose:
        u = resp.usage
        print(f"  [usage] input={u.input_tokens} "
              f"cache_create={u.cache_creation_input_tokens} "
              f"cache_read={u.cache_read_input_tokens}")
    text = resp.content[0].text
    m = re.search(r"```sql\s*(.*?)```", text, re.S)
    return (m.group(1) if m else text).strip().rstrip(";") + ";"


# ----- Step 6: execute -----
def run_sql(sql):
    con = duckdb.connect("portfolio.db", read_only=True)
    try:
        return con.execute(sql).fetchdf(), None
    except Exception as e:
        return None, str(e)
    finally:
        con.close()


# ----- Step 7: orchestrate with one self-correction retry -----
def ask(question, use_examples=True, verbose=False):
    examples = retrieve_examples(question, use_examples=use_examples)
    sql = generate_sql(question, examples, verbose=verbose)
    result, err = run_sql(sql)
    if err:                                # retry once, feeding the error back
        sql = generate_sql(question, examples, error=err, verbose=verbose)
        result, err = run_sql(sql)
    if err:
        return {"sql": sql, "result": None, "error": err,
                "answer": f"Query failed after retry: {err}"}

    summary = client.messages.create(
        model=MODEL,
        max_tokens=300,
        temperature=0,
        messages=[{"role": "user", "content":
            f"Question: {question}\nSQL result:\n{result.to_string(index=False)}\n\n"
            "Answer the question in 1-2 plain sentences, including the key numbers."}],
    ).content[0].text
    return {"sql": sql, "result": result, "error": None, "answer": summary}


if __name__ == "__main__":
    out = ask("What's the 90+ DPD rate by segment?", verbose=True)
    print("\nSQL:\n", out["sql"])
    print("\nAnswer:\n", out["answer"])
    if out["result"] is not None:
        print("\nResult:\n", out["result"].to_string(index=False))
