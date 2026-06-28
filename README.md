# Redrob AI Ranker — Intelligent Candidate Discovery

**Track 01 Submission: Redrob Hackathon — Intelligent Candidate Discovery & Ranking**

A multi-signal algorithmic ranking engine that scores and ranks 100,000 candidate profiles against any Job Description — with a live browser UI for dynamic re-ranking.

---

## What's in This Zip

```
/                                 ← Pre-built web app (Vercel deploys this)
├── index.html
├── assets/
├── candidates_compact.json.gz    ← 100K candidate index (5 MB)
└── vercel.json

submission/                       ← Hackathon deliverables
├── submission.csv                ← Top 100 ranked candidates ✅
├── ranked_output.xlsx            ← Enriched XLSX with scores ✅
├── rank.py                       ← Python ranking script
├── precompute_compact.py         ← Candidate index generator
├── requirements.txt
├── PPT_ANSWERS.md                ← Methodology Q&A
└── validate_submission.py        ← Official validator (unchanged)
```

---

## Deploy to Vercel (Live Demo)

1. Go to [vercel.com/new](https://vercel.com/new)
2. Click **"Deploy without Git"** and upload **this zip file directly**
3. Click **Deploy** — done ✅

No build step, no configuration. The live demo runs entirely in the browser.

---

## Reproduce the Ranking (Python)

### Prerequisites
- Python 3.11+
- `candidates.jsonl` from the challenge data

```bash
cd submission/

pip install openpyxl

python rank.py \
  --candidates /path/to/candidates.jsonl \
  --out ./submission.csv \
  --xlsx ./ranked_output.xlsx
```

**Runtime:** ~45 seconds · **Memory:** < 2 GB

Output matches `submission.csv` and `ranked_output.xlsx` exactly.

---

## Scoring Model

Five weighted signals — no LLM calls at ranking time:

| Signal | Weight | Rationale |
|--------|--------|-----------|
| Title & Career History | 35% | Ground-truth signal — catches keyword stuffers |
| Skill Quality Score | 25% | Proficiency × endorsements × years used |
| Behavioral Signals | 20% | Availability, recency, response rate, notice period |
| Experience Fit | 15% | Peaks at 5–9 years, tapers outside range |
| Location Fit | 5% | India / Pune / Noida per JD |

### Trap Prevention

- **Keyword stuffers:** Title weight (35%) hard-caps an "Accountant" with 10 AI skills at score 0.12 — cannot enter top 100
- **Honeypot detection:** Irrelevant title + 6+ JD skill matches → 75% score penalty
- **Pure services penalty:** Career at TCS/Infosys/Wipro → 30% title score reduction
- **Ghost candidates:** Inactive 6+ months → behavioral score tanks regardless of skills

---

## Tech Stack

- **Python 3.11** — core ranking logic, XLSX generation
- **React + Vite + Web Worker** — browser-side live re-ranking (no server needed)
- **Vercel** — static hosting
