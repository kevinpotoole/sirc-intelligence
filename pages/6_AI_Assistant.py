import json
import math
import os
import re
from collections import Counter

import streamlit as st

from utils.styles import header, section, SIRC_CSS, SIRC_NAVY, SIRC_GOLD

st.set_page_config(page_title="AI Managing Broker Assistant | SIRC", layout="wide")
header("AI Managing Broker Assistant", "Ask anything about regulations, policies & compliance")

KNOWLEDGE_BASE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "data", "docs", "knowledge_base.json"
)

SYSTEM_PROMPT = """You are an expert AI assistant for a Managing Broker at Sotheby's International Realty Canada (SIRC).

You have deep knowledge of:
- BC real estate regulations and the Real Estate Services Act (BCFSA)
- FINTRAC compliance requirements for real estate
- GVR (Greater Vancouver REALTORS) rules, bylaws and code of conduct
- REALTOR Code of Ethics
- Competition Act requirements for real estate professionals
- SIRC brand standards and internal policies
- Professional standards and misconduct guidelines

Your role is to assist the Managing Broker with:
- Answering regulatory and compliance questions
- Explaining policies and procedures
- Providing guidance on agent conduct issues
- Advising on FINTRAC obligations
- Clarifying brand standards and usage

Always be clear, professional, and precise. When answering, cite the specific document and section where the information comes from. If you are unsure or the information is not in the provided documents, say so clearly and recommend consulting a lawyer or the relevant regulatory body.

IMPORTANT: You are providing information and guidance, not legal advice. Always note when a question requires formal legal or regulatory consultation."""


@st.cache_data(show_spinner=False)
def load_knowledge_base():
    if not os.path.exists(KNOWLEDGE_BASE_PATH):
        return []
    with open(KNOWLEDGE_BASE_PATH) as f:
        return json.load(f)


def tokenize(text: str) -> list[str]:
    return re.findall(r'\b[a-z]{2,}\b', text.lower())


def bm25_score(query_tokens: list, chunk_text: str, avg_dl: float, k1=1.5, b=0.75) -> float:
    doc_tokens = tokenize(chunk_text)
    dl = len(doc_tokens)
    tf = Counter(doc_tokens)
    score = 0.0
    for token in set(query_tokens):
        if token in tf:
            f = tf[token]
            score += (f * (k1 + 1)) / (f + k1 * (1 - b + b * dl / avg_dl))
    return score


def find_relevant_chunks(query: str, chunks: list, top_k: int = 8) -> list:
    if not chunks:
        return []
    query_tokens = tokenize(query)
    avg_dl = sum(len(tokenize(c["text"])) for c in chunks) / len(chunks)
    scored = [(bm25_score(query_tokens, c["text"], avg_dl), c) for c in chunks]
    scored.sort(key=lambda x: x[0], reverse=True)
    return [c for _, c in scored[:top_k] if _ > 0]


def ask_claude(question: str, context_chunks: list, api_key: str, history: list) -> str:
    import anthropic
    client = anthropic.Anthropic(api_key=api_key)

    context = "\n\n".join(
        f"[Source: {c['source']}]\n{c['text']}" for c in context_chunks
    )

    messages = []
    for msg in history[-6:]:  # Keep last 6 turns for context
        messages.append({"role": msg["role"], "content": msg["content"]})

    messages.append({
        "role": "user",
        "content": f"""Based on the following regulatory documents, please answer this question:

QUESTION: {question}

RELEVANT DOCUMENT EXCERPTS:
{context}

Please provide a clear, practical answer and cite which document(s) you're drawing from."""
    })

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1500,
        system=SYSTEM_PROMPT,
        messages=messages,
    )
    return response.content[0].text


# ── Get API key ────────────────────────────────────────────────────────────
try:
    anthropic_key = st.secrets["anthropic"]["api_key"]
except Exception:
    anthropic_key = None

# ── Load knowledge base ────────────────────────────────────────────────────
chunks = load_knowledge_base()
sources = sorted(set(c["source"] for c in chunks)) if chunks else []

# ── Sidebar ────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(SIRC_CSS, unsafe_allow_html=True)
    st.markdown("### Knowledge Base")
    st.markdown(f"<small style='color:#C9A96E'>{len(chunks)} document sections loaded</small>", unsafe_allow_html=True)
    st.markdown("**Documents:**")
    for src in sources:
        st.markdown(f"<small>• {src}</small>", unsafe_allow_html=True)
    st.markdown("---")
    if st.button("🗑️  Clear Conversation"):
        st.session_state.messages = []
        st.rerun()

# ── API key warning ────────────────────────────────────────────────────────
if not anthropic_key:
    st.warning("""
**Anthropic API key not configured.**

To activate the AI assistant:
1. Get a free API key at **console.anthropic.com**
2. In Streamlit → Settings → Secrets, add:
```toml
[anthropic]
api_key = "sk-ant-..."
```
3. Save and reboot the app.
    """)
    st.stop()

if not chunks:
    st.error("Knowledge base not found. Please run `sync_docs.py` to build it.")
    st.stop()

# ── Chat interface ─────────────────────────────────────────────────────────
st.markdown(f"""
<div style="background:{SIRC_NAVY};padding:1rem 1.5rem;border-radius:4px;margin-bottom:1.5rem">
<p style="color:#C9A96E;font-size:0.75rem;letter-spacing:0.1em;text-transform:uppercase;margin:0 0 0.3rem 0">
Your AI Managing Broker Assistant
</p>
<p style="color:#F7F3EE;font-size:0.85rem;margin:0">
Ask me anything about BC real estate regulations, FINTRAC compliance, GVR bylaws, REALTOR Code,
BCFSA rules, SIRC brand standards, agent conduct, or any policy question you face as a Managing Broker.
</p>
</div>
""", unsafe_allow_html=True)

# Suggested questions
section("Suggested Questions")
suggestions = [
    "What are my FINTRAC obligations when onboarding a new client?",
    "What constitutes misconduct under the GVR rules?",
    "What are the BCFSA requirements for managing broker supervision?",
    "What does the Competition Act say about commission discussions?",
    "What are the SIRC brand standards for social media posts?",
    "When is a wire transfer verification required?",
]
cols = st.columns(3)
for i, suggestion in enumerate(suggestions):
    if cols[i % 3].button(suggestion, key=f"suggest_{i}"):
        st.session_state.setdefault("messages", [])
        st.session_state["pending_question"] = suggestion

# ── Message history ────────────────────────────────────────────────────────
if "messages" not in st.session_state:
    st.session_state.messages = []

section("Conversation")

for msg in st.session_state.messages:
    with st.chat_message(msg["role"], avatar="🏛️" if msg["role"] == "assistant" else "👤"):
        st.markdown(msg["content"])
        if msg.get("sources"):
            with st.expander("📄 Sources consulted"):
                for src in msg["sources"]:
                    st.markdown(f"- {src}")

# Handle suggested question click
pending = st.session_state.pop("pending_question", None)

# Chat input
user_input = st.chat_input("Ask a regulatory or compliance question…") or pending

if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user", avatar="👤"):
        st.markdown(user_input)

    with st.chat_message("assistant", avatar="🏛️"):
        with st.spinner("Searching documents and preparing answer…"):
            relevant = find_relevant_chunks(user_input, chunks, top_k=8)
            used_sources = sorted(set(c["source"] for c in relevant))
            try:
                answer = ask_claude(user_input, relevant, anthropic_key, st.session_state.messages[:-1])
            except Exception as e:
                answer = f"Sorry, I encountered an error: {e}. Please check your Anthropic API key in Streamlit secrets."

        st.markdown(answer)
        if used_sources:
            with st.expander("📄 Sources consulted"):
                for src in used_sources:
                    st.markdown(f"- {src}")

    st.session_state.messages.append({
        "role": "assistant",
        "content": answer,
        "sources": used_sources,
    })

# ── Footer ─────────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown(
    "<p style='color:#8B7355;font-size:0.7rem;text-align:center'>"
    "This assistant provides information and guidance only — not legal advice. "
    "Consult a lawyer or the relevant regulatory body for formal legal matters."
    "</p>",
    unsafe_allow_html=True,
)
