from datetime import datetime, timedelta, timezone

from . import config, db
from .applier import ats_of
from .searchlinks import build_links


def build(run: dict, settings: dict) -> str:
    st = db.stats()
    since = (datetime.now(timezone.utc) - timedelta(hours=26)).isoformat(timespec="seconds")
    today = [j for j in db.list_jobs() if j["found_at"] >= since and j["status"] not in ("low_match", "backlog")]
    action = db.list_jobs(["needs_action"])
    lines = [f"Job Bot daily summary - {datetime.now().strftime('%d %b %Y %H:%M')}", "",
             f"Found today: {run.get('found', 0)} | fresh: {run.get('fresh', 0)} | new: {run.get('new', 0)} | "
             f"duplicates skipped: {run.get('duplicates', 0)}",
             f"Shortlisted: {run.get('shortlisted', 0)} | applied this run: {run.get('applied', 0)} | "
             f"needing your action: {st['needs_action']}",
             f"All-time: {st['total']} jobs, {st['matching']} matching, {st['applied']} applied, "
             f"{st['interview']} interviews, {st['rejected']} rejected", ""]
    lines.append("TOP NEW MATCHES")
    for j in today[:15]:
        mark = "auto-assist" if ats_of(j["url"]) else "manual"
        lines.append(f"- [{j['score']}] {j['title']} @ {j['company']} ({j['location'] or 'n/a'}) [{mark}]\n  {j['url']}")
    if not today:
        lines.append("- none")
    lines += ["", "NEEDS YOUR ACTION"]
    for j in action[:20]:
        lines.append(f"- #{j['id']} {j['title']} @ {j['company']}: {j['notes'] or 'apply manually'}\n  {j['url']}")
    if not action:
        lines.append("- none")
    if run.get("errors"):
        lines += ["", "SOURCE ERRORS"] + [f"- {e}" for e in run["errors"]]
    lines += ["", "OPEN MANUALLY (last 24h, entry-level filters)"]
    lines += [f"- {name}: {url}" for name, url in build_links(settings)[:12]]
    text = "\n".join(lines)
    config.SUMMARY_DIR.mkdir(parents=True, exist_ok=True)
    (config.SUMMARY_DIR / f"{datetime.now().strftime('%Y-%m-%d')}.txt").write_text(text, encoding="utf-8")
    return text
