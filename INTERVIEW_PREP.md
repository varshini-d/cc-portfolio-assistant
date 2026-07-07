# Interview Prep — Consumer Lending Portfolio Assistant

Your cheat sheet for talking about this project. Read it before any interview
where you plan to bring it up. Practice the 30-second pitch and the utilization
example out loud until they're automatic.

---

## 30-second pitch (lead with this)

> "I built a text-to-SQL assistant over a real Lending Club consumer-lending
> portfolio — about 2.3 million loans. You ask a business question in plain
> English, like 'charge-off rate by vintage for subprime loans,' and it
> generates the SQL, runs it, and gives you the numbers plus a plain-English
> summary. The interesting part isn't that an LLM writes SQL — it's making the
> SQL *trustworthy*. I used retrieval-augmented generation to ground the model
> in the real schema and our credit-risk metric definitions, added a
> self-correction loop, and built an evaluation harness that proves retrieval
> lifted accuracy by 10 points on a 20-question benchmark."

## Why this project fits credit-risk DS roles

It speaks the domain's language: charge-off rate, delinquency, vintage,
utilization, risk tiers, grades. It's not "I can call an LLM API" — it's "I
understand that in lending, the *definition* of a metric is the whole ballgame,
and I engineered a system to enforce correct definitions." That's rare and
exactly what a risk team wants.

---

## The architecture (be able to draw this)

```
English question
     │
     ▼
[1] Retrieve relevant examples  ←── FAISS vector search over the knowledge base
     │                              (semantic search finds the closest Q→SQL pairs)
     ▼
[2] Claude generates SQL        ←── schema + glossary + SQL rules in a CACHED system block
     │                              + the retrieved examples (dynamic)
     ▼
[3] Execute SQL on DuckDB
     │
     ├── error? ──► [4] feed the error back to Claude, retry once (self-correction)
     │
     ▼
[5] Claude summarizes the result in plain English
```

**Key design split:** static content (schema, glossary, rules) goes in the
**cached** system prompt; dynamic content (retrieved examples + the question)
stays outside the cache. Static → cached. Dynamic → not. That split is the whole
caching idea.

## The numbers (memorize these)

- **Data:** real Lending Club accepted loans, 2007–2018, ~2.26M rows → cleaned,
  reproducible 250k-row sample in DuckDB.
- **Real risk gradient (sanity that the data is real):** charge-off rate is
  6% prime → 15% near-prime → 29% subprime. Monotonic, believable.
- **Accuracy:** 100% with RAG vs 90% without → **+10 points from retrieval**, on
  a 20-question result-match benchmark.
- **Caching:** ~2,035 static tokens cached and reused every call
  (`cache_read=2035`); only ~100–200 dynamic tokens re-sent. Cached tokens bill
  at ~10% of fresh input.

---

## The one story to always tell (the "utilization / definition" story)

> "The queries RAG fixes aren't the simple ones — counts and sums pass with or
> without retrieval. It's the domain-judgment queries. For example, 'charge-off
> rate by vintage for subprime loans': without a retrieved example the model
> sometimes picks the wrong grouping or the wrong risk-tier definition. The
> retrieved example pins exactly what 'subprime' means and the output shape. In
> lending, those are precisely the queries you can't afford to get wrong — a
> wrong metric definition produces a plausible number that someone might make a
> credit decision on."

This shows you understand *where* the value is, not just "RAG made it better."

---

## Likely questions & strong answers

**Q: Why RAG instead of putting everything in the prompt?**
> "The static schema and glossary *do* go in the prompt every time — that part's
> fixed. RAG is for the *examples*, which grow over time. At hundreds of examples
> you can't fit them all in context; retrieving the 3 most relevant is cheaper
> and more accurate than dumping all of them. RAG is the pattern that scales."

**Q: How do you know the SQL is correct?**
> "Two layers. The self-correction loop catches *executable* errors — bad syntax,
> wrong column. But executable isn't correct, so I also built an eval that
> compares the query's *results* against hand-written gold SQL across 20
> questions. That's how I measured the RAG lift instead of just assuming it."

**Q: What were the failure cases?**
> "Without retrieval, the grouped/filtered credit-risk queries failed — like
> charge-off rate by vintage for a specific risk tier, or by home ownership. The
> model would misgroup or misdefine the tier. Those are the exact queries the
> retrieved examples fix."

**Q: How does the caching work and what does it save?**
> "The static schema + glossary + SQL rules are ~2,035 tokens and identical every
> call, so I mark that block cacheable. After the first call it's read from cache
> at ~10% of the input cost, and only the ~100–200 tokens of retrieved examples
> plus the question are fresh. I verified it with the API usage fields —
> `cache_read` shows 2,035 on every call after the first. Note there's a
> threshold: Sonnet won't cache a prefix under 2,048 tokens, which I hit and had
> to design the static block to clear."

**Q: Why Lending Club and not real credit card data?**
> "Real card-portfolio data is proprietary and regulated — no bank publishes it.
> Lending Club is the closest public, recognizable consumer-credit dataset, and
> it actually matches my background in personal-loan portfolios. It has real
> charge-offs, grades, vintages, and utilization — the metrics that matter."

**Q: How would you productionize this?**
> "Read-only DB role and SQL allow-listing so the model can't run destructive
> queries; result caching for repeated questions; a versioned, growing example
> library where an analyst can correct a bad answer and have it become a new
> few-shot example; and a confidence/escalation path so low-confidence queries go
> to a human instead of being answered."

**Q: What are the limitations? (answer honestly — it reads as maturity)**
> "It's a single table, so no join reasoning yet. The benchmark is 20 questions —
> enough to show the RAG lift, not to certify production accuracy. And it's a
> historical snapshot, not a live feed. I know each of these and how I'd address
> them, which I think matters more than pretending they aren't there."

---

## Red flags to avoid

- ❌ Claiming caching savings without the mechanism — know the 2,048-token
  threshold and the ~10% cached-read cost.
- ❌ Overselling "100% accuracy" — always say "on a 20-question benchmark" and
  note it's small.
- ❌ Implying the data is real-time — it's 2007–2018 historical.
- ❌ Saying it's credit *card* data — it's consumer *loans*; lean into that being
  closer to your actual experience.
