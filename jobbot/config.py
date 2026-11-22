"""Loads settings.yaml, profile.yaml, companies.yaml and .env."""
import os
from pathlib import Path

import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

DB_PATH = ROOT / "data" / "jobs.db"
LOG_DIR = ROOT / "logs"
SUMMARY_DIR = ROOT / "data" / "summaries"


def _load(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def load_settings() -> dict:
    return _load(ROOT / "config" / "settings.yaml")


def load_companies() -> dict:
    return _load(ROOT / "config" / "companies.yaml")


def load_profile() -> dict:
    p = _load(ROOT / "config" / "profile.yaml")
    per = p.setdefault("personal", {})
    links = p.setdefault("links", {})
    per["email"] = env("PROFILE_EMAIL", per.get("email", ""))
    per["phone"] = env("PROFILE_PHONE", per.get("phone", ""))
    links["github"] = env("GITHUB_URL", links.get("github", ""))
    p["resume_abs"] = str(ROOT / p.get("resume_path", "resume/resume.pdf"))
    return p


def profile_problems(p: dict, for_apply: bool = False) -> list[str]:
    """Things that must be fixed before the bot may fill forms with your data."""
    out = []
    per, links = p["personal"], p["links"]
    if not per.get("email"):
        out.append("PROFILE_EMAIL is empty in .env")
    if not per.get("phone"):
        out.append("PROFILE_PHONE is empty in .env")
    if not links.get("github") or "YOUR-USERNAME" in links["github"]:
        out.append("GITHUB_URL is not set in .env")
    if for_apply:
        if not p.get("verified"):
            out.append("set 'verified: true' in config/profile.yaml after checking every field against your resume")
        if not Path(p["resume_abs"]).exists():
            out.append(f"resume file not found: {p['resume_abs']}")
    return out
