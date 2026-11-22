"""Adzuna job-search API (free key, India endpoint). Descriptions are short snippets."""
import logging
import time

from ..config import env
from ..models import Job
from ..utils import get_json, iso, parse_dt

log = logging.getLogger(__name__)


def fetch(settings, profile, companies) -> list[Job]:
    app_id, app_key = env("ADZUNA_APP_ID"), env("ADZUNA_APP_KEY")
    if not app_id or not app_key:
        log.warning("adzuna enabled but ADZUNA_APP_ID / ADZUNA_APP_KEY missing in .env - skipped")
        return []
    s = settings["search"]
    out = []
    for q in s.get("adzuna_queries", [])[:4]:
        for where in s.get("adzuna_locations", [])[:5]:
            try:
                data = get_json("https://api.adzuna.com/v1/api/jobs/in/search/1", params={
                    "app_id": app_id, "app_key": app_key, "what": q, "where": where,
                    "max_days_old": s.get("max_age_days", 3), "results_per_page": 20,
                    "sort_by": "date", "content-type": "application/json"})
            except Exception as e:
                log.warning("adzuna '%s' in %s failed: %s", q, where, e)
                continue
            for j in data.get("results", []):
                out.append(Job("adzuna", j.get("title", ""), (j.get("company") or {}).get("display_name", ""),
                               j.get("redirect_url", ""), (j.get("location") or {}).get("display_name", ""),
                               j.get("description", ""), iso(parse_dt(j.get("created"))), str(j.get("id", ""))))
            time.sleep(1)  # polite
    return out
