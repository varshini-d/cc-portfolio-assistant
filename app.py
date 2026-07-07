"""Step 8 — Streamlit UI.  Run:  streamlit run app.py"""
import streamlit as st

from assistant import ask

st.set_page_config(page_title="Consumer Lending Portfolio Assistant", page_icon="💳")
st.title("Consumer Lending Portfolio Analytics Assistant")
st.caption("Text-to-SQL with RAG over a real Lending Club portfolio (2007–2018) "
           "+ a credit-risk metric glossary")

examples = [
    "What's the charge-off rate by risk tier?",
    "Charge-off rate by vintage for subprime loans",
    "Average interest rate by grade",
    "Charge-off rate for credit card loans",
    "Average revolving utilization by risk tier",
    "Currently-delinquent rate by grade",
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
