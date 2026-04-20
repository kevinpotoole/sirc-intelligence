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

# Minimum BM25 score to consider a chunk relevant. Below this threshold we
# tell the user the topic isn't covered rather than risk a hallucinated answer.
MIN_RELEVANCE_SCORE = 3.0

SYSTEM_PROMPT = """You are an expert AI assistant for a Managing Broker at Sotheby's International Realty Canada (SIRC).

STRICT GROUNDING RULE: You must answer ONLY using information explicitly present in the document excerpts provided in the user's message. Do NOT draw on any general knowledge, training data, or external sources. If the answer is not in the provided excerpts, say clearly: "I cannot find a reliable answer to this question in my current knowledge base." Then, if you know of one or two specific reputable sources that would cover it (e.g., a BCFSA guideline, FINTRAC bulletin, or CREA policy document), name them by title and suggest the user consider adding them — but do not state what those sources say.

You have deep knowledge of (from loaded documents):
- BC real estate regulations and the Real Estate Services Act (BCFSA)
- FINTRAC compliance requirements for real estate
- GVR (Greater Vancouver REALTORS) rules, bylaws and code of conduct
- REALTOR Code of Ethics
- Competition Act requirements for real estate professionals
- SIRC brand standards and internal policies
- Professional standards and misconduct guidelines

When answering from the provided excerpts:
- Cite the exact document and section you are drawing from
- Use direct quotes where helpful
- If excerpts give partial information, say what is covered and what is not
- Never infer, extrapolate, or fill gaps with general knowledge

Always note: you provide information and guidance only — not legal advice. Recommend formal consultation for legal or regulatory matters."""


def _kb_mtime() -> float:
    try:
        return os.path.getmtime(KNOWLEDGE_BASE_PATH)
    except OSError:
        return 0.0


@st.cache_data(show_spinner=False)
def load_knowledge_base(mtime: float):  # mtime busts cache when file changes
    if not os.path.exists(KNOWLEDGE_BASE_PATH):
        return []
    with open(KNOWLEDGE_BASE_PATH) as f:
        return json.load(f)


def tokenize(text: str) -> list:
    return re.findall(r'\b[a-z]{2,}\b', text.lower())


def find_relevant_chunks(query: str, chunks: list, top_k: int = 8):
    if not chunks:
        return [], 0.0
    query_tokens = tokenize(query)
    N = len(chunks)
    doc_tokens = [tokenize(c["text"]) for c in chunks]
    avg_dl = sum(len(d) for d in doc_tokens) / N

    # Document frequency for IDF
    df: Counter = Counter()
    for d in doc_tokens:
        for t in set(d):
            df[t] += 1

    k1, b = 1.5, 0.75
    scores = []
    for i, d in enumerate(doc_tokens):
        dl = len(d)
        tf = Counter(d)
        score = 0.0
        for token in set(query_tokens):
            f = tf.get(token, 0)
            if f == 0:
                continue
            idf = math.log((N - df[token] + 0.5) / (df[token] + 0.5) + 1)
            score += idf * (f * (k1 + 1)) / (f + k1 * (1 - b + b * dl / avg_dl))
        scores.append((score, i))

    scores.sort(reverse=True)
    top_score = scores[0][0] if scores else 0.0
    relevant = [chunks[i] for s, i in scores[:top_k] if s > 0]
    return relevant, top_score


def ask_claude(question: str, context_chunks: list, api_key: str) -> str:
    import anthropic
    client = anthropic.Anthropic(api_key=api_key)

    context = "\n\n".join(
        f"[Source: {c['source']}]\n{c['text']}" for c in context_chunks
    )

    messages = [{
        "role": "user",
        "content": f"""Answer the following question using ONLY the document excerpts below. Do not use any knowledge outside these excerpts.

QUESTION: {question}

DOCUMENT EXCERPTS:
{context}

Cite the specific document(s) you draw from. If the answer is not in these excerpts, say so and suggest which reputable source might cover it."""
    }]

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
chunks = load_knowledge_base(_kb_mtime())
sources = sorted(set(c["source"] for c in chunks)) if chunks else []
bcfsa_count = sum(1 for s in sources if s.startswith("BCFSA"))
drive_count = len(sources) - bcfsa_count

# ── Sidebar ────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(SIRC_CSS, unsafe_allow_html=True)
    st.markdown("### Knowledge Base")
    st.markdown(
        f"<small style='color:#C9A96E'>{len(chunks)} sections · {len(sources)} sources</small>",
        unsafe_allow_html=True,
    )
    st.markdown(f"<small>• {drive_count} regulatory documents (Drive)</small>", unsafe_allow_html=True)
    st.markdown(f"<small>• {bcfsa_count} BCFSA website pages</small>", unsafe_allow_html=True)
    with st.expander("View all sources"):
        for src in sources:
            st.markdown(f"<small>· {src}</small>", unsafe_allow_html=True)
    st.markdown("---")
    st.markdown(
        "<small style='color:#8B7355'>The assistant answers only from these sources. "
        "If a topic isn't covered, it will say so and suggest sources to add.</small>",
        unsafe_allow_html=True,
    )
    st.markdown("---")
    if st.button("🗑️  Clear Answer"):
        st.session_state.current_qa = None
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

# ── Intro banner ────────────────────────────────────────────────────────────
st.markdown(f"""
<div style="background:{SIRC_NAVY};padding:1rem 1.5rem;border-radius:4px;margin-bottom:1.5rem">
<p style="color:#C9A96E;font-size:0.75rem;letter-spacing:0.1em;text-transform:uppercase;margin:0 0 0.3rem 0">
Your AI Managing Broker Assistant
</p>
<p style="color:#F7F3EE;font-size:0.85rem;margin:0">
Ask me anything about BC real estate regulations, FINTRAC compliance, GVR bylaws, REALTOR Code,
BCFSA rules, SIRC brand standards, agent conduct, or any policy question you face as a Managing Broker.
Each answer is drawn only from the loaded knowledge base — no guessing.
</p>
</div>
""", unsafe_allow_html=True)

# ── Suggested questions ─────────────────────────────────────────────────────
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
        st.session_state["pending_question"] = suggestion

# ── Chat input ──────────────────────────────────────────────────────────────
section("Ask a Question")
pending = st.session_state.pop("pending_question", None)
user_input = st.chat_input("Ask a regulatory or compliance question…") or pending

if user_input:
    # Show the question
    with st.chat_message("user", avatar="👤"):
        st.markdown(user_input)

    with st.chat_message("assistant", avatar="🏛️"):
        with st.spinner("Searching documents and preparing answer…"):
            relevant, top_score = find_relevant_chunks(user_input, chunks, top_k=8)
            used_sources = sorted(set(c["source"] for c in relevant))

            if top_score < MIN_RELEVANCE_SCORE or not relevant:
                answer = (
                    "I was unable to find relevant information in my current knowledge base to answer this question reliably.\n\n"
                    "To avoid giving you inaccurate information, I will not speculate. Please consult the relevant regulatory body directly, "
                    "or let me know if you'd like me to suggest a specific document or source that should be added to the knowledge base."
                )
                used_sources = []
            else:
                try:
                    answer = ask_claude(user_input, relevant, anthropic_key)
                except Exception as e:
                    answer = f"Sorry, I encountered an error: {e}. Please check your Anthropic API key in Streamlit secrets."

        st.markdown(answer)
        if used_sources:
            with st.expander("📄 Sources consulted"):
                for src in used_sources:
                    st.markdown(f"- {src}")

    # Store only the most recent Q&A (replaces previous)
    st.session_state["current_qa"] = {
        "question": user_input,
        "answer": answer,
        "sources": used_sources,
    }

elif "current_qa" in st.session_state and st.session_state["current_qa"]:
    # Re-display the last answer (without re-running Claude)
    qa = st.session_state["current_qa"]
    with st.chat_message("user", avatar="👤"):
        st.markdown(qa["question"])
    with st.chat_message("assistant", avatar="🏛️"):
        st.markdown(qa["answer"])
        if qa.get("sources"):
            with st.expander("📄 Sources consulted"):
                for src in qa["sources"]:
                    st.markdown(f"- {src}")

# ── Footer ─────────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown(
    "<p style='color:#8B7355;font-size:0.7rem;text-align:center'>"
    "This assistant provides information and guidance only — not legal advice. "
    "Consult a lawyer or the relevant regulatory body for formal legal matters."
    "</p>",
    unsafe_allow_html=True,
)
