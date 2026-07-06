import json
import os

import streamlit as st
from dotenv import load_dotenv
from openai import OpenAI
from pypdf import PdfReader

load_dotenv()

FIREWORKS_API_KEY = os.getenv("FIREWORKS_API_KEY", "")
FIREWORKS_MODEL = os.getenv("FIREWORKS_MODEL", "accounts/fireworks/models/gemma2-9b-it")
FIREWORKS_BASE_URL = "https://api.fireworks.ai/inference/v1"

SYSTEM_PROMPT = """You are ClarityAI, an assistant that reads contracts, terms of service, \
leases, and offer letters and explains them in plain language for people with no legal \
background.

Given a document, respond with ONLY a JSON object (no markdown, no commentary) in this exact \
shape:

{
  "overall_risk_score": <integer 0-100, 0 = totally safe, 100 = extremely risky>,
  "summary": "<2-3 sentence plain-language summary of what this document means for the person signing it>",
  "clauses": [
    {
      "excerpt": "<short quote or paraphrase of the clause>",
      "risk_level": "<low|medium|high>",
      "explanation": "<one sentence, plain language, why this matters to them>"
    }
  ]
}

Include 3-8 of the most important clauses, prioritizing anything risky, unusual, or costly. \
If the document is genuinely low-risk and standard, say so honestly and keep the clause list short."""


def extract_text(uploaded_file) -> str:
    if uploaded_file.name.lower().endswith(".pdf"):
        reader = PdfReader(uploaded_file)
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    return uploaded_file.read().decode("utf-8", errors="ignore")


def analyze_document(text: str) -> dict:
    client = OpenAI(api_key=FIREWORKS_API_KEY, base_url=FIREWORKS_BASE_URL)
    response = client.chat.completions.create(
        model=FIREWORKS_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": text[:15000]},
        ],
        temperature=0.2,
        response_format={"type": "json_object"},
    )
    return json.loads(response.choices[0].message.content)


def risk_color(level: str) -> str:
    return {"low": "#2e7d32", "medium": "#e6a700", "high": "#c62828"}.get(level.lower(), "#888")


st.set_page_config(page_title="ClarityAI", page_icon="📄", layout="centered")

st.title("📄 ClarityAI")
st.caption("Paste a contract, ToS, lease, or offer letter — get a plain-language risk breakdown, powered by Gemma on Fireworks AI.")

if not FIREWORKS_API_KEY:
    st.warning("FIREWORKS_API_KEY is not set. Add it to your .env file before analyzing a document.")

tab_paste, tab_upload = st.tabs(["Paste text", "Upload file"])

document_text = ""
with tab_paste:
    document_text = st.text_area("Paste the document text here", height=250, placeholder="I hereby agree that...")
with tab_upload:
    uploaded = st.file_uploader("Upload a .txt or .pdf file", type=["txt", "pdf"])
    if uploaded is not None:
        document_text = extract_text(uploaded)
        st.success(f"Loaded {len(document_text)} characters from {uploaded.name}")

analyze_clicked = st.button("Analyze document", type="primary", disabled=not document_text.strip())

if analyze_clicked:
    with st.spinner("Reading the fine print..."):
        try:
            result = analyze_document(document_text)
        except Exception as exc:
            st.error(f"Analysis failed: {exc}")
            result = None

    if result:
        score = result.get("overall_risk_score", 0)
        st.subheader("Overall risk")
        st.progress(min(max(score, 0), 100) / 100)
        st.metric("Risk score", f"{score}/100")

        st.subheader("Summary")
        st.write(result.get("summary", "No summary provided."))

        st.subheader("Flagged clauses")
        for clause in result.get("clauses", []):
            level = clause.get("risk_level", "low")
            color = risk_color(level)
            st.markdown(
                f"""<div style="border-left: 4px solid {color}; padding: 8px 12px; margin-bottom: 10px; background: rgba(128,128,128,0.06);">
                <b style="color:{color}; text-transform:uppercase;">{level}</b><br/>
                <i>{clause.get('excerpt', '')}</i><br/>
                {clause.get('explanation', '')}
                </div>""",
                unsafe_allow_html=True,
            )
