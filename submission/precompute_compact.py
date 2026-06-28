#!/usr/bin/env python3
"""
Precompute compact candidate features for browser-side re-ranking.

Outputs: candidates_compact.json.gz
Each candidate is distilled to the minimum fields needed to re-score
against any arbitrary JD in the browser.

Run:
    python precompute_compact.py \
        --candidates /path/to/candidates.jsonl \
        --out ./candidates_compact.json.gz
"""

import argparse
import gzip
import json
import sys
from datetime import date
from pathlib import Path

REFERENCE_DATE = date(2025, 6, 27)

PROFICIENCY_WEIGHT = {
    "beginner": 0.3,
    "intermediate": 0.6,
    "advanced": 0.85,
    "expert": 1.0,
}

SERVICES_COMPANIES = {
    "tcs", "tata consultancy", "infosys", "wipro", "accenture",
    "cognizant", "capgemini", "hcl", "tech mahindra", "mphasis",
    "hexaware", "niit", "mastech", "syntel", "l&t infotech", "mindtree",
}

PRODUCT_COMPANY_SIGNALS = {
    "amazon", "google", "microsoft", "meta", "apple", "netflix",
    "flipkart", "swiggy", "zomato", "ola", "paytm", "razorpay",
    "cred", "meesho", "nykaa", "freshworks", "zoho", "cleartax",
    "phonepe", "sharechat", "moj", "dream11", "udaan", "thoughtworks",
}

# Generic AI/ML title keywords for pre-computing career AI ratio
AI_TITLE_KEYWORDS = {
    "ai", "ml", "machine learning", "deep learning", "nlp", "data scient",
    "applied scientist", "research engineer", "search engineer",
    "recommendation", "ranking engineer", "computer vision",
}

AI_DESC_KEYWORDS = {
    "machine learning", "deep learning", "model", "embedding", "retrieval",
    "nlp", "neural", "training", "vector", "ranking", "recommendation",
    "classification", "fine-tun", "transformer", "llm", "generative",
}


def compute_behavioral_score(signals: dict) -> float:
    """Pre-compute behavioral score — does NOT depend on JD."""
    open_to_work = 1.0 if signals.get("open_to_work_flag", False) else 0.3

    last_active_str = signals.get("last_active_date", "")
    recency = 0.5
    if last_active_str:
        try:
            last_active = date.fromisoformat(last_active_str)
            days_inactive = (REFERENCE_DATE - last_active).days
            if days_inactive <= 7:
                recency = 1.0
            elif days_inactive <= 30:
                recency = 0.85
            elif days_inactive <= 90:
                recency = 0.65
            elif days_inactive <= 180:
                recency = 0.4
            else:
                recency = 0.15
        except (ValueError, TypeError):
            recency = 0.5

    response_rate = signals.get("recruiter_response_rate", 0.5)

    notice = signals.get("notice_period_days", 60)
    if notice <= 15:
        notice_score = 1.0
    elif notice <= 30:
        notice_score = 0.9
    elif notice <= 60:
        notice_score = 0.65
    elif notice <= 90:
        notice_score = 0.4
    else:
        notice_score = 0.2

    completeness = signals.get("profile_completeness_score", 50) / 100.0

    github = signals.get("github_activity_score", -1)
    if github == -1:
        github_score = 0.3
    else:
        github_score = 0.3 + 0.7 * (github / 100.0)

    interview_rate = signals.get("interview_completion_rate", 0.7)
    saved = min(1.0, signals.get("saved_by_recruiters_30d", 0) / 10.0)

    return (
        0.20 * open_to_work +
        0.20 * recency +
        0.20 * response_rate +
        0.15 * notice_score +
        0.10 * completeness +
        0.08 * github_score +
        0.05 * interview_rate +
        0.02 * saved
    )


def skill_quality(skill: dict, assessments: dict) -> float:
    """Compute the quality-adjusted score for a skill."""
    proficiency = skill.get("proficiency", "intermediate")
    endorsements = skill.get("endorsements", 0)
    duration_months = skill.get("duration_months", 0)
    name = skill.get("name", "")

    pw = PROFICIENCY_WEIGHT.get(proficiency, 0.5)
    endorse_boost = min(0.15, endorsements / 500.0)
    duration_boost = min(0.1, duration_months / 600.0)

    assess_score = assessments.get(name, -1)
    if assess_score >= 0:
        pw = max(pw, assess_score / 100.0)

    return round(pw + endorse_boost + duration_boost, 4)


def extract_candidate(candidate: dict) -> dict:
    """Distill a candidate record to compact form."""
    profile = candidate.get("profile", {})
    career = candidate.get("career_history", [])
    signals = candidate.get("redrob_signals", {})
    skills_raw = candidate.get("skills", [])
    assessments = signals.get("skill_assessment_scores", {})

    # Pre-compute career metrics
    ai_role_months = 0
    total_career_months = 0
    product_company_experience = False
    pure_services_career = True
    recent_ai_role = False

    for i, job in enumerate(career):
        title_low = job.get("title", "").lower()
        company_low = job.get("company", "").lower()
        duration = job.get("duration_months", 0)
        desc_low = job.get("description", "").lower()
        is_current = job.get("is_current", False)

        total_career_months += duration

        is_services = any(svc in company_low for svc in SERVICES_COMPANIES)
        is_product = any(prod in company_low for prod in PRODUCT_COMPANY_SIGNALS)
        company_size = job.get("company_size", "")

        if not is_services:
            pure_services_career = False
        if (is_product or company_size in {"501-1000", "1001-5000", "5001-10000", "10001+"}) and not is_services:
            product_company_experience = True

        title_is_ai = any(kw in title_low for kw in AI_TITLE_KEYWORDS)
        desc_has_ml = any(kw in desc_low for kw in AI_DESC_KEYWORDS)

        if title_is_ai or desc_has_ml:
            ai_role_months += duration
            if is_current or i == 0:
                recent_ai_role = True

    ai_ratio = round(ai_role_months / max(total_career_months, 1), 4)

    # Compact skills: [name_lower, quality_score]
    compact_skills = []
    for s in skills_raw:
        name = s.get("name", "").lower().strip()
        if name:
            compact_skills.append([name, skill_quality(s, assessments)])

    behavioral_score = round(compute_behavioral_score(signals), 6)

    return {
        "i": candidate["candidate_id"],
        "t": profile.get("current_title", "").lower(),
        "y": profile.get("years_of_experience", 0),
        "sk": compact_skills,
        "b": behavioral_score,
        "loc": profile.get("location", "").lower(),
        "c": profile.get("country", "").lower(),
        "r": signals.get("willing_to_relocate", False),
        "ai": ai_ratio,
        "ps": pure_services_career and total_career_months > 24,
        "pr": product_company_experience,
        "rai": recent_ai_role,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidates", required=True)
    parser.add_argument("--out", default="./candidates_compact.json.gz")
    args = parser.parse_args()

    path = Path(args.candidates)
    if not path.exists():
        print(f"ERROR: {path} not found", file=sys.stderr)
        sys.exit(1)

    results = []
    count = 0
    errors = 0

    print("Processing candidates...", file=sys.stderr)
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                candidate = json.loads(line)
                results.append(extract_candidate(candidate))
                count += 1
                if count % 10000 == 0:
                    print(f"  {count}...", file=sys.stderr)
            except Exception as e:
                errors += 1

    print(f"Processed {count} candidates ({errors} errors)", file=sys.stderr)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    payload = json.dumps(results, separators=(",", ":"))
    with gzip.open(out_path, "wt", encoding="utf-8", compresslevel=9) as f:
        f.write(payload)

    compressed_size = out_path.stat().st_size
    print(f"Written: {out_path} ({compressed_size / 1024 / 1024:.1f} MB)", file=sys.stderr)


if __name__ == "__main__":
    main()
