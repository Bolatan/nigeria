import streamlit as st
from rag import ask

st.set_page_config(page_title="Nigerian Constitution, in plain English", page_icon="🇳🇬")
st.title("Nigerian Constitution, in plain English")
st.caption("Ask a question. Answers come only from the 1999 Constitution (as amended).")

if "chat" not in st.session_state:
    st.session_state.chat = []

for role, text, sources in st.session_state.chat:
    with st.chat_message(role):
        st.write(text)
        for s in sources:
            with st.expander(s["ref"]):
                st.write(s["text"])

if q := st.chat_input("e.g. Can the police detain me for more than 24 hours?"):
    with st.chat_message("user"):
        st.write(q)
    with st.chat_message("assistant"):
        with st.spinner("Reading the Constitution..."):
            r = ask(q)
        st.write(r["answer"])
        for s in r["sources"]:
            with st.expander(s["ref"]):
                st.write(s["text"])
    st.session_state.chat += [("user", q, []), ("assistant", r["answer"], r["sources"])]
