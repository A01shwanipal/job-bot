"""Remote-job public APIs. RemoteOK asks for attribution/link-back; Remotive asks for few requests/day."""
import logging

from ..models import Job
from ..utils import clean_html, get_json, iso, parse_dt

log = logging.getLogger(__name__)


def fetch_remoteok(settings, profile, companies) -> list[Job]:
    data = get_json("https://remoteok.com/api")
    out = []
    for j in data:
        if not isinstance(j, dict) or not j.get("position"):
            continue  # first element is a legal notice
        tags = " ".join(j.get("tags") or [])
        loc = j.get("location") or "Worldwide"
        out.append(Job("remoteok", j["position"], j.get("company", ""), j.get("url", ""), f"Remote - {loc}",
                       clean_html(j.get("description", "")) + " " + tags, iso(parse_dt(j.get("date"))),
                       str(j.get("id", ""))))
    return out


def fetch_remotive(settings, profile, companies) -> list[Job]:
    out = []
    for term in ("java", "backend"):
        data = get_json("https://remotive.com/api/remote-jobs", params={"search": term})
        for j in data.get("jobs", []):
            out.append(Job("remotive", j.get("title", ""), j.get("company_name", ""), j.get("url", ""),
                           f"Remote - {j.get('candidate_required_location') or 'Worldwide'}",
                           clean_html(j.get("description", "")), iso(parse_dt(j.get("publication_date"))),
                           str(j.get("id", ""))))
    return out
