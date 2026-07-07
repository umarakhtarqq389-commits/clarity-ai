import json
import os

import streamlit as st
from dotenv import load_dotenv
from fpdf import FPDF
from openai import OpenAI
from pypdf import PdfReader

load_dotenv()

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "fireworks").lower()

FIREWORKS_API_KEY = os.getenv("FIREWORKS_API_KEY", "")
FIREWORKS_MODEL = os.getenv("FIREWORKS_MODEL", "accounts/fireworks/models/gpt-oss-120b")
FIREWORKS_BASE_URL = "https://api.fireworks.ai/inference/v1"

HF_TOKEN = os.getenv("HF_TOKEN", "")
HF_MODEL = os.getenv("HF_MODEL", "Qwen/Qwen2.5-7B-Instruct")

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
      "explanation": "<one sentence, plain language, why this matters to them>",
      "negotiation_tip": "<one sentence: a concrete, specific ask they could make to fix or soften this clause. Empty string if the clause is low risk and not worth pushing back on.>"
    }
  ]
}

Include 3-8 of the most important clauses, prioritizing anything risky, unusual, or costly. \
If the document is genuinely low-risk and standard, say so honestly and keep the clause list short."""

VERDICTS = [
    (20, "Looks Standard", "check_circle", "#2e7d32"),
    (50, "Read Carefully", "warning", "#e6a700"),
    (75, "Negotiate Before Signing", "construction", "#e65100"),
    (101, "Proceed With Caution", "report", "#c62828"),
]


def verdict_for_score(score: int):
    for threshold, label, icon, color in VERDICTS:
        if score < threshold:
            return label, icon, color
    return VERDICTS[-1][1], VERDICTS[-1][2], VERDICTS[-1][3]


ICON_PATHS = {
    "description": '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="16" y1="13" x2="8" y2="13"></line><line x1="16" y1="17" x2="8" y2="17"></line>',
    "check_circle": '<path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path><polyline points="22 4 12 14.01 9 11.01"></polyline>',
    "warning": '<path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path><line x1="12" y1="9" x2="12" y2="13"></line><line x1="12" y1="17" x2="12.01" y2="17"></line>',
    "construction": '<path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94z"></path>',
    "report": '<polygon points="7.86 2 16.14 2 22 7.86 22 16.14 16.14 22 7.86 22 2 16.14 2 7.86 7.86 2"></polygon><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line>',
    "forum": '<path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"></path>',
}


def material_icon(name: str, color: str = "currentColor", size: int = 20) -> str:
    inner = ICON_PATHS.get(name, "")
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 24 24" '
        f'fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" '
        f'style="vertical-align:middle;">{inner}</svg>'
    )


def _pdf_safe(text: str) -> str:
    replacements = {
        "—": "-", "–": "-", "‘": "'", "’": "'",
        "“": '"', "”": '"', "…": "...",
    }
    for src, dst in replacements.items():
        text = text.replace(src, dst)
    return text.encode("latin-1", errors="replace").decode("latin-1")


def build_report_pdf(result: dict) -> bytes:
    score = result.get("overall_risk_score", 0)
    label, _, verdict_color = verdict_for_score(score)
    rgb = tuple(int(verdict_color.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4))

    pdf = FPDF()
    pdf.add_page()

    def line(text: str, height: float) -> None:
        pdf.multi_cell(0, height, _pdf_safe(text), new_x="LMARGIN", new_y="NEXT")

    pdf.set_font("Helvetica", "B", 20)
    line("ClarityAI Risk Report", 12)

    pdf.set_font("Helvetica", "B", 14)
    pdf.set_text_color(*rgb)
    line(f"{label}  -  Risk score: {score}/100", 10)
    pdf.set_text_color(0, 0, 0)
    pdf.ln(2)

    pdf.set_font("Helvetica", "B", 13)
    line("Summary", 8)
    pdf.set_font("Helvetica", "", 11)
    line(result.get("summary", ""), 6)
    pdf.ln(3)

    pdf.set_font("Helvetica", "B", 13)
    line("Flagged clauses", 8)

    for clause in result.get("clauses", []):
        level = clause.get("risk_level", "").upper()
        level_rgb = tuple(int(risk_color(clause.get("risk_level", "low")).lstrip("#")[i:i + 2], 16) for i in (0, 2, 4))

        pdf.ln(2)
        pdf.set_font("Helvetica", "B", 11)
        pdf.set_text_color(*level_rgb)
        line(f"[{level}]", 6)
        pdf.set_text_color(0, 0, 0)

        pdf.set_font("Helvetica", "I", 10)
        line(clause.get("excerpt", ""), 5)

        pdf.set_font("Helvetica", "", 10)
        line(f"Why it matters: {clause.get('explanation', '')}", 5)

        tip = clause.get("negotiation_tip", "")
        if tip:
            pdf.set_font("Helvetica", "B", 10)
            line(f"Ask for: {tip}", 5)

    pdf.ln(4)
    pdf.set_font("Helvetica", "I", 8)
    line("Generated by ClarityAI - not legal advice.", 5)

    return bytes(pdf.output())


def extract_text(uploaded_file) -> str:
    if uploaded_file.name.lower().endswith(".pdf"):
        reader = PdfReader(uploaded_file)
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    return uploaded_file.read().decode("utf-8", errors="ignore")


def parse_json_response(content: str) -> dict:
    content = content.strip()
    if content.startswith("```"):
        content = content.strip("`")
        content = content.split("\n", 1)[1] if "\n" in content else content
        if content.lower().startswith("json"):
            content = content[4:]
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        from json_repair import repair_json

        return json.loads(repair_json(content))


def analyze_document(text: str) -> dict:
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": text[:15000]},
    ]

    if LLM_PROVIDER == "huggingface":
        from huggingface_hub import InferenceClient

        client = InferenceClient(token=HF_TOKEN)
        response = client.chat_completion(messages=messages, model=HF_MODEL, max_tokens=1500, temperature=0.2)
        content = response.choices[0].message.content
    else:
        client = OpenAI(api_key=FIREWORKS_API_KEY, base_url=FIREWORKS_BASE_URL)
        response = client.chat.completions.create(
            model=FIREWORKS_MODEL,
            messages=messages,
            temperature=0.2,
            max_tokens=4000,
            response_format={"type": "json_object"},
        )
        content = response.choices[0].message.content

    return parse_json_response(content)


def risk_color(level: str) -> str:
    return {"low": "#2e7d32", "medium": "#e6a700", "high": "#c62828"}.get(level.lower(), "#888")


st.set_page_config(page_title="ClarityAI", page_icon=":material/description:", layout="centered")

st.markdown(f'<h1>{material_icon("description", size=34)} ClarityAI</h1>', unsafe_allow_html=True)
st.caption("Paste a contract, ToS, lease, or offer letter — get a plain-language risk breakdown, powered by Gemma on Fireworks AI.")

if LLM_PROVIDER == "huggingface" and not HF_TOKEN:
    st.warning("HF_TOKEN is not set. Add it to your .env file before analyzing a document.")
elif LLM_PROVIDER != "huggingface" and not FIREWORKS_API_KEY:
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

analyze_clicked = st.button("Analyze document", type="primary", icon=":material/search:")

if analyze_clicked and not document_text.strip():
    st.warning("Please paste or upload a document first.")
elif analyze_clicked:
    with st.spinner("Reading the fine print..."):
        try:
            result = analyze_document(document_text)
        except Exception as exc:
            st.error(f"Analysis failed: {exc}")
            result = None

    if result:
        score = result.get("overall_risk_score", 0)
        label, verdict_icon, verdict_color = verdict_for_score(score)

        icon_html = material_icon(verdict_icon, color=verdict_color, size=28)
        banner_html = (
            f'<div style="border: 2px solid {verdict_color}; border-radius: 8px; padding: 14px 18px; margin-bottom: 16px; text-align: center;">'
            f'{icon_html} <span style="font-size: 1.3em; font-weight: 700; color: {verdict_color};">{label}</span>'
            f'</div>'
        )
        st.markdown(banner_html, unsafe_allow_html=True)

        st.subheader("Overall risk")
        st.progress(min(max(score, 0), 100) / 100)
        st.metric("Risk score", f"{score}/100")

        st.subheader("Summary")
        st.write(result.get("summary", "No summary provided."))

        st.subheader("Flagged clauses")
        for clause in result.get("clauses", []):
            level = clause.get("risk_level", "low")
            color = risk_color(level)
            tip = clause.get("negotiation_tip", "")
            tip_html = (
                f'<br/>{material_icon("forum", color=color, size=16)} <b>Ask for:</b> {tip}'
                if tip
                else ""
            )
            clause_html = (
                f'<div style="border-left: 4px solid {color}; padding: 8px 12px; margin-bottom: 10px; background: rgba(128,128,128,0.06);">'
                f'<b style="color:{color}; text-transform:uppercase;">{level}</b><br/>'
                f'<i>{clause.get("excerpt", "")}</i><br/>'
                f'{clause.get("explanation", "")}'
                f'{tip_html}'
                f'</div>'
            )
            st.markdown(clause_html, unsafe_allow_html=True)

        st.download_button(
            "Download full Risk Report (PDF)",
            data=build_report_pdf(result),
            file_name="clarityai_risk_report.pdf",
            mime="application/pdf",
            icon=":material/download:",
        )
