"""Rule-based relevance scoring (0-100). No AI API needed.

Points: title 35 + skills 30 + experience 15 + location 10 + freshness 10.
A job is "eligible" only if it passes the hard filters (title, seniority, experience, location, core skill).
"""
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone

from .utils import parse_dt

TIER1 = re.compile(r"(?<![a-z])(java|spring(\s?boot)?)(?![a-z])")
TIER2 = re.compile(r"back[\s-]?end|full[\s-]?stack")
TIER3 = re.compile(r"software (engineer|developer)|(?<![a-z])sde(?![a-z])|application developer|"
                   r"web developer|programmer|trainee|graduate engineer")
RESTRICTED = re.compile(r"(?<![a-z])(us|usa|u\.s\.|united states|canada|uk|united kingdom|europe|emea|eu|germany|"
                        r"france|latam|brazil|australia|mexico|north america|singapore|uae|dubai)(?![a-z])")
FRESHER = re.compile(r"fresher|entry[\s-]level|new grad|graduate|0\s*(?:-|to|–)\s*[12]\s*(?:years?|yrs?)|(?<!\d)0\s*years")
EXP_A = re.compile(r"(\d{1,2})\s*(?:\+|plus)?\s*(?:(?:-|–|to)\s*(\d{1,2})\s*)?(?:years?|yrs?)\b[^.\n]{0,30}?(?:experience|exp\b)")
EXP_B = re.compile(r"experience[^.\n]{0,30}?(\d{1,2})\s*\+?\s*(?:years?|yrs?)")
CORE_BACKEND = ("java", "spring boot")
CORE_FULLSTACK = ("java", "spring boot", "react", "javascript")


@dataclass
class ScoreResult:
    total: int
    eligible: bool
    breakdown: dict = field(default_factory=dict)
    reasons: list = field(default_factory=list)


def has_word(text: str, term: str) -> bool:
    return re.search(r"(?<![a-z0-9])" + re.escape(term.lower()) + r"(?![a-z0-9])", text) is not None


def matched_skills(text: str, profile: dict) -> list[tuple[str, float]]:
    text = text.lower()
    out = []
    for s in profile["skills"]:
        if any(has_word(text, a) for a in s["aliases"]):
            out.append((s["name"], float(s["weight"])))
    return out


def parse_experience(text: str) -> tuple[int | None, bool]:
    """Returns (minimum years required or None, mentions fresher/entry-level)."""
    t = text.lower()
    fresher = FRESHER.search(t) is not None
    m = EXP_A.search(t)
    if m:
        return int(m.group(1)), fresher
    m = EXP_B.search(t)
    if m:
        return int(m.group(1)), fresher
    return None, fresher


def _location(job_loc: str, title: str, profile: dict) -> tuple[float, bool, str]:
    loc = (job_loc or "").lower()
    if any(has_word(loc, p) for p in profile["preferred_locations"]):
        return 10, True, "preferred location"
    if "remote" in loc or "remote" in title or "work from home" in loc:
        if RESTRICTED.search(loc) and "india" not in loc:
            return 0, False, f"remote but restricted ({job_loc})"
        return 8, True, "remote"
    if not loc:
        return 4, True, "location not stated"
    if "india" in loc:
        return 4, True, "India (city not preferred)"
    return 0, False, f"location outside preference ({job_loc})"


def score_job(job, profile: dict, settings: dict, now: datetime | None = None) -> ScoreResult:
    s = settings["search"]
    now = now or datetime.now(timezone.utc)
    title = job.title.lower()
    text = f"{job.title} {job.description}".lower()
    reasons, bd, ok = [], {}, True

    for kw in profile.get("exclude_title_keywords", []):
        if has_word(title, kw):
            return ScoreResult(0, False, {"excluded": kw}, [f"title contains '{kw}'"])

    # title (35)
    if TIER1.search(title):
        t = 35
    elif TIER2.search(title):
        t = 28
    elif TIER3.search(title):
        t = 18
    else:
        t, ok = 0, False
        reasons.append("title not relevant")
    bd["title"] = t

    # skills (30)
    skills = matched_skills(text, profile)
    ref = float(s.get("skill_reference_weight", 8))
    bd["skills"] = round(min(1.0, sum(w for _, w in skills) / ref) * 30, 1)
    names = {n.lower() for n, _ in skills}
    core = CORE_FULLSTACK if TIER2.search(title) and "full" in title else CORE_BACKEND
    if not names & set(core):
        ok = False
        reasons.append("none of my core skills mentioned")

    # experience (15)
    min_years, fresher = parse_experience(text)
    maxy = int(s.get("max_required_years", 2))
    if min_years is not None and min_years > maxy:
        ok, e = False, 0
        reasons.append(f"requires {min_years}+ years")
    elif fresher:
        e = 15
    elif min_years is None:
        e = 10
    elif min_years <= 1:
        e = 14
    else:
        e = 7
    bd["experience"] = e

    # location (10)
    l, loc_ok, why = _location(job.location, title, profile)
    bd["location"] = l
    if not loc_ok:
        ok = False
        reasons.append(why)

    # freshness (10)
    posted = parse_dt(job.posted_at)
    if posted is None:
        f = 3
    else:
        age = (now - posted).total_seconds() / 86400
        f = 10 if age <= 1 else 7 if age <= 3 else 4 if age <= 7 else 1
    bd["freshness"] = f

    total = int(round(sum(bd.values())))
    bd["matched_skills"] = [n for n, _ in skills]
    return ScoreResult(total, ok, bd, reasons)


def is_fresh(job, max_age_days: int, now: datetime | None = None) -> bool:
    posted = parse_dt(job.posted_at)
    if posted is None:
        return True
    return ((now or datetime.now(timezone.utc)) - posted).total_seconds() <= max_age_days * 86400
