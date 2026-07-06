# ClarityAI

Plain-language contract and fine-print risk analysis, powered by Google DeepMind's Gemma models via Fireworks AI on AMD infrastructure.

Built for the **AMD Developer Hackathon: ACT II** — Unicorn Track.

## The problem

Nobody reads the contract, the lease, the terms of service, or the offer letter before signing. The clauses that matter most — auto-renewal, liability waivers, hidden fees, non-competes — are buried in dense legal language most people can't parse in the time they have.

## The solution

Paste or upload any document. ClarityAI reads it with Gemma and returns:

- An overall risk score (0-100)
- A plain-language summary of what you're actually agreeing to
- The specific clauses worth worrying about, each flagged low / medium / high risk with a one-sentence explanation

## Tech stack

- **UI + app:** [Streamlit](https://streamlit.io/) (Python)
- **Model:** Gemma, served via [Fireworks AI](https://fireworks.ai/) on AMD Developer Cloud
- **Packaging:** Docker

## Setup

1. Clone this repo and `cd` into it.
2. Copy `.env.example` to `.env` and fill in your Fireworks AI API key:
   ```
   cp .env.example .env
   ```
3. Get a key by signing up for the [AMD AI Developer Program](https://www.amd.com/en/developer/resources/ai-developer-program.html), which includes Fireworks AI API credits.

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Run with Docker

```bash
docker build -t clarityai .
docker run -p 8501:8501 --env-file .env clarityai
```

Then open http://localhost:8501

## Notes

- `FIREWORKS_MODEL` in `.env` defaults to a Gemma model on Fireworks; update it to match whichever Gemma model ID is available on launch day.
- Supports pasted text or `.txt` / `.pdf` upload.
