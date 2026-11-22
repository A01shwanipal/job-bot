import argparse
import sys

from . import applier, config, db, logging_setup, mailcheck, pipeline, summary


def main() -> int:
    ap = argparse.ArgumentParser(prog="jobbot", description="Personal job search & application assistant")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init", help="create database and validate profile")
    sub.add_parser("check", help="validate profile / resume / .env")
    r = sub.add_parser("run", help="daily workflow (search, score, prepare, summary)")
    r.add_argument("--apply", dest="apply", action="store_true", default=None, help="also try assisted applying")
    r.add_argument("--no-apply", dest="apply", action="store_false")
    r.add_argument("--no-notify", action="store_true")
    a = sub.add_parser("apply", help="open a visible browser and fill shortlisted applications (you review/submit)")
    a.add_argument("--limit", type=int)
    a.add_argument("--auto", action="store_true", help="auto-click Submit when everything is filled and no CAPTCHA")
    a.add_argument("--headless", action="store_true")
    sub.add_parser("mail", help="scan inbox for interview/rejection mails")
    sub.add_parser("summary", help="print today's summary")
    m = sub.add_parser("mark", help="set a job's status manually")
    m.add_argument("job_id", type=int)
    m.add_argument("status", choices=db.STATUSES)
    m.add_argument("--note", default="")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    logging_setup.setup(args.verbose)
    settings, profile, companies = config.load_settings(), config.load_profile(), config.load_companies()
    db.init()

    if args.cmd in ("init", "check"):
        probs = config.profile_problems(profile, for_apply=True)
        print("Database ready:", config.DB_PATH)
        print("Profile OK for applying." if not probs else "To fix before applying:\n - " + "\n - ".join(probs))
    elif args.cmd == "run":
        pipeline.run(settings, profile, companies, apply=args.apply, do_notify=not args.no_notify)
    elif args.cmd == "apply":
        res = applier.run_apply(settings, profile, limit=args.limit, auto_submit=args.auto or None,
                                headless=True if args.headless else False)
        print(res)
    elif args.cmd == "mail":
        print("status changes:", mailcheck.run())
    elif args.cmd == "summary":
        print(summary.build({}, settings))
    elif args.cmd == "mark":
        db.set_status(args.job_id, args.status, args.note)
    return 0


if __name__ == "__main__":
    sys.exit(main())
