"""Deep links for portals that forbid scraping/automation (LinkedIn, Indeed, Naukri, Wellfound).
The bot never opens or scrapes them - YOU click the links; they are pre-filtered to the last 24h / entry level."""
from urllib.parse import quote_plus


def _slug(s: str) -> str:
    return "-".join(s.lower().split())


def build_links(settings: dict) -> list[tuple[str, str]]:
    m = settings.get("manual_search", {})
    out = []
    for role in m.get("roles", []):
        for loc in m.get("locations", []):
            q, l = quote_plus(role), quote_plus(loc)
            out.append((f"LinkedIn - {role} - {loc}",
                        f"https://www.linkedin.com/jobs/search/?keywords={q}&location={l}&f_TPR=r86400&f_E=1%2C2"))
            out.append((f"Indeed - {role} - {loc}", f"https://in.indeed.com/jobs?q={q}&l={l}&fromage=1"))
            out.append((f"Naukri - {role} - {loc}",
                        f"https://www.naukri.com/{_slug(role)}-jobs-in-{_slug(loc)}?experience=0"))
    out.append(("Wellfound (startups)", "https://wellfound.com/jobs"))
    return out
