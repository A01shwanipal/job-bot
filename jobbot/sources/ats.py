"""Public career-board APIs of Greenhouse, Lever and Ashby (no login, no scraping)."""
import logging

from ..models import Job
from ..utils import clean_html, get_json, iso, parse_dt

log = logging.getLogger(__name__)


def fetch_greenhouse(settings, profile, companies) -> list[Job]:
    out = []
    for token in companies.get("greenhouse") or []:
        try:
            data = get_json(f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs", params={"content": "true"})
        except Exception as e:
            log.warning("greenhouse/%s skipped: %s", token, e)
            continue
        for j in data.get("jobs", []):
            out.append(Job("greenhouse", j.get("title", ""), j.get("company_name") or token, j.get("absolute_url", ""),
                           (j.get("location") or {}).get("name", ""), clean_html(j.get("content", "")),
                           iso(parse_dt(j.get("first_published") or j.get("updated_at"))), str(j.get("id", ""))))
    return out


def fetch_lever(settings, profile, companies) -> list[Job]:
    out = []
    for slug in companies.get("lever") or []:
        try:
            data = get_json(f"https://api.lever.co/v0/postings/{slug}", params={"mode": "json"})
        except Exception as e:
            log.warning("lever/%s skipped: %s", slug, e)
            continue
        for j in data:
            cat = j.get("categories") or {}
            out.append(Job("lever", j.get("text", ""), slug, j.get("hostedUrl", ""), cat.get("location", "") or "",
                           j.get("descriptionPlain", ""), iso(parse_dt(j.get("createdAt"))), str(j.get("id", ""))))
    return out


def fetch_ashby(settings, profile, companies) -> list[Job]:
    out = []
    for name in companies.get("ashby") or []:
        try:
            data = get_json(f"https://api.ashbyhq.com/posting-api/job-board/{name}")
        except Exception as e:
            log.warning("ashby/%s skipped: %s", name, e)
            continue
        for j in data.get("jobs", []):
            loc = j.get("location", "") or ""
            if j.get("isRemote") and "remote" not in loc.lower():
                loc = f"Remote - {loc}".strip(" -")
            out.append(Job("ashby", j.get("title", ""), name, j.get("jobUrl", ""), loc,
                           j.get("descriptionPlain", "") or clean_html(j.get("descriptionHtml", "")),
                           iso(parse_dt(j.get("publishedAt"))), str(j.get("id", ""))))
    return out
