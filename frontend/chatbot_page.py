"""Module Chatbot — conversational Q&A grounded in the user's training modules."""
from __future__ import annotations

import streamlit as st

from backend.analytics.db import get_db
from backend.analytics.persistence import list_modules
from backend.chatbot.engine import ask, build_module_catalog
from backend.core.llm_client import LLMFactory
from frontend.nav import render_back_button
from frontend.styles import page_header_html


def render_chatbot_page() -> None:
    username = st.session_state.get("username", "")
    user_id = st.session_state.get("user_id", "")
    db_path = st.session_state.get("db_path", "")
    if not username or not user_id:
        st.session_state["page"] = "login"
        st.rerun()
        return

    dark = st.session_state.get("dark_mode", True)

    render_back_button("← Back to Module Library", "module_library", key="_back_chatbot")

    st.markdown(
        page_header_html(
            "Module Chatbot",
            "Ask questions about your training modules — answers are grounded in your uploaded content.",
            "💬", dark=dark,
        ),
        unsafe_allow_html=True,
    )

    conn = get_db(db_path)
    try:
        modules = list_modules(db=conn)
        module_ids = [m["module_id"] for m in modules]
        module_titles = {m["module_id"]: m["title"] for m in modules}
        module_catalog = build_module_catalog(modules, db=conn) if module_ids else ""
    finally:
        conn.close()

    if not module_ids:
        st.info("No training modules found. Upload a document first to start chatting.")
        return

    st.caption(f"📚 {len(modules)} module(s) loaded")

    if "chat_messages" not in st.session_state:
        st.session_state["chat_messages"] = []

    chat_container = st.container(height=500)
    with chat_container:
        for msg in st.session_state["chat_messages"]:
            with st.chat_message(msg["role"]):
                st.write(msg["content"])
                if msg.get("sources"):
                    _show_sources(msg["sources"], module_titles)

    if prompt := st.chat_input("Ask a question about your modules..."):
        st.session_state["chat_messages"].append({"role": "user", "content": prompt})

        with chat_container:
            with st.chat_message("user"):
                st.write(prompt)

            with st.chat_message("assistant"):
                with st.spinner("Searching modules..."):
                    provider = st.session_state.get("llm_provider", "anthropic")
                    model = st.session_state.get("llm_model", "claude-sonnet-4-6")
                    try:
                        llm = LLMFactory.create(provider=provider, model=model)
                    except Exception as exc:
                        st.error(f"Could not connect to LLM: {exc}")
                        return

                    response = ask(
                        question=prompt,
                        module_ids=module_ids,
                        llm=llm,
                        module_catalog=module_catalog,
                        history=st.session_state.get("chat_messages", []),
                    )

                st.write(response.answer)

                sources = []
                if response.is_relevant and response.sources:
                    for s in response.sources:
                        s["title"] = module_titles.get(s.get("module_id", ""), "Unknown")
                    sources = response.sources
                    _show_sources(sources, module_titles)

                st.session_state["chat_messages"].append({
                    "role": "assistant",
                    "content": response.answer,
                    "sources": sources,
                })

    if st.session_state.get("chat_messages"):
        if st.button("Clear conversation", key="_clear_chat"):
            st.session_state["chat_messages"] = []
            st.rerun()


def _show_sources(sources: list[dict], module_titles: dict) -> None:
    if not sources:
        return
    seen = set()
    names = []
    for s in sources:
        mid = s.get("module_id", "")
        if mid in seen:
            continue
        seen.add(mid)
        title = s.get("title") or module_titles.get(mid, "Unknown")
        names.append(title)
    if names:
        st.caption("Sources: " + " | ".join(names))
