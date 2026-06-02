"""Step 8 — Streamlit UI.  Run:  streamlit run app.py"""
import streamlit as st

from assistant import ask

st.set_page_config(page_title="Credit Card Portfolio Assistant", page_icon="??")
st.title("Credit Card Portfolio Analytics Assistant")
st.caption("Text-to-SQL with RAG over schema + a credit-risk metric glossary")

examples = [
    "What's the 90+ DPD rate by segment?",
    "Charge-off rate by vintage for subprime accounts",
    "Average utilization for travel cards in the prime segment",
    "How many active accounts per product type?",
]
q = st.selectbox("Try an example, or type your own below:", [""] + examples)
q = st.text_input("Ask about the portfolio:", value=q or examples[0])

if st.button("Ask", type="primary"):
    with st.spinner("Generating SQL and querying..."):
        out = ask(q)
    st.markdown(f"**Answer:** {out['answer']}")
    st.code(out["sql"], language="sql")
    if out["result"] is not None:
        st.dataframe(out["result"], use_container_width=True)
    elif out["error"]:
        st.error(out["error"])
