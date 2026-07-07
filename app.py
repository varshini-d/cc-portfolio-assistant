"""Streamlit UI.  Run locally:  streamlit run app.py

On a fresh deploy (Streamlit Community Cloud) the generated artifacts
(portfolio.db, kb.index, kb_meta.pkl) don't exist because they're gitignored.
bootstrap() rebuilds them once from the committed data/portfolio.parquet and the
knowledge base, then imports the assistant. A password gate (APP_PASSWORD in
Streamlit secrets) keeps the owner-funded API key from being drained by randoms.
"""
import os

import streamlit as st

st.set_page_config(page_title="Consumer Lending Portfolio Assistant", page_icon="💳")


@st.cache_resource(show_spinner="Preparing data + index (first load only)...")
def bootstrap():
    """Ensure portfolio.db + FAISS index exist, then return the assistant's ask()."""
    if not os.path.exists("portfolio.db"):
        import build_data
        build_data.main()                      # loads committed parquet (no raw CSV on host)
    if not (os.path.exists("kb.index") and os.path.exists("kb_meta.pkl")):
        from index import build_index
        build_index()
    from assistant import ask                   # imported here: reads the artifacts above
    return ask


def check_password():
    """Simple gate. Returns True once the correct APP_PASSWORD is entered."""
    if st.session_state.get("auth_ok"):
        return True

    def _submit():
        st.session_state["auth_ok"] = (
            st.session_state.get("pw", "") == st.secrets.get("APP_PASSWORD", "")
        )

    st.title("Consumer Lending Portfolio Analytics Assistant")
    st.text_input("Enter password to access the demo", type="password",
                  key="pw", on_change=_submit)
    if st.session_state.get("auth_ok") is False:
        st.error("Incorrect password.")
    st.caption("This is a private portfolio demo. Ask the author for access.")
    return False


if not check_password():
    st.stop()

ask = bootstrap()

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
