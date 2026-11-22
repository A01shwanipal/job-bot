"""Daily workflow: search -> filter -> dedupe -> score -> shortlist -> message -> (apply) -> summary."""
import logging

from . import applier, config, db, summary
from .matcher import is_fresh, score_job
from .messages import build_message
from .notify import notify
from .sources import REGISTRY

log = logging.getLogger(__name__)


def collect(settings: dict, profile: dict, companies: dict):
    jobs, errors = [], []
    for name, fn in REGISTRY.items():
        if not settings["sources"].get(name, False):
            continue
        try:
            got = fn(settings, profile, companies)
            log.info("source %-10s -> %d postings", name, len(got))
            jobs += got
        except Exception as e:
            log.exception("source %s failed", name)
            errors.append(f"{name}: {e}")
    return jobs, errors


def run(settings: dict, profile: dict, companies: dict, jobs: list | None = None,
        apply: bool | None = None, do_notify: bool = True) -> dict:
    db.init()
    errors: list[str] = []
    if jobs is None:
        jobs, errors = collect(settings, profile, companies)
    s = settings["search"]
    cap, min_score = int(s.get("max_jobs_per_day", 50)), int(s.get("min_score", 55))

    fresh = [j for j in jobs if j.title and j.url and is_fresh(j, int(s.get("max_age_days", 3)))]
    seen: set[str] = set()
    scored, dups = [], 0
    for j in fresh:
        fp, uk = db.keys_for(j)
        if fp in seen or uk in seen or db.exists(fp, uk):
            dups += 1
            continue
        seen.update((fp, uk))
        scored.append((j, score_job(j, profile, settings)))

    matched = sorted([x for x in scored if x[1].eligible and x[1].total >= min_score],
                     key=lambda x: x[1].total, reverse=True)
    top, backlog = matched[:cap], matched[cap:]
    top_ids = {id(x[0]) for x in top}
    back_ids = {id(x[0]) for x in backlog}

    shortlisted = 0
    for j, res in scored:
        bd = dict(res.breakdown, reasons=res.reasons)
        if id(j) in top_ids:
            jid = db.insert_job(j, res.total, bd, "shortlisted")
            job_row = db.get_job(jid)
            msg = build_message(job_row, profile)
            with db.conn() as c:
                c.execute("UPDATE jobs SET message=? WHERE id=?", (msg, jid))
            if applier.ats_of(j.url) is None:
                db.set_status(jid, "needs_action", "manual apply (portal not automatable) - message is ready")
            shortlisted += 1
        elif id(j) in back_ids:
            db.insert_job(j, res.total, bd, "backlog")
        else:
            db.insert_job(j, res.total, bd, "low_match", detail="; ".join(res.reasons))

    result = {"applied": 0}
    do_apply = settings["apply"].get("enabled", False) if apply is None else apply
    if do_apply:
        result = applier.run_apply(settings, profile, interactive=False)

    run_info = {"found": len(jobs), "fresh": len(fresh), "new": len(scored), "duplicates": dups,
                "shortlisted": shortlisted, "applied": result.get("applied", 0),
                "needs_action": db.stats()["needs_action"], "errors": errors}
    db.log_run(**run_info)
    text = summary.build(run_info, settings)
    log.info("\n%s", text)
    if do_notify:
        notify(settings, text)
    return run_info
