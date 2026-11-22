# Job Bot - free, personal job search & application assistant

Python + SQLite + Streamlit + Playwright. No paid API anywhere. Matching is rule-based, messages are templates built only from `config/profile.yaml`.

## Architecture

```
 sources (public APIs)          jobbot/pipeline.py                         outputs
 ┌───────────────────┐   ┌──────────────────────────────────────┐   ┌───────────────────────┐
 │ Greenhouse/Lever/ │   │ 1 collect  (retry, per-source errors)│   │ SQLite  data/jobs.db  │
 │ Ashby career APIs │──▶│ 2 freshness filter (<= 3 days)       │──▶│ Streamlit dashboard   │
 │ Adzuna (free key) │   │ 3 dedupe (title+company / URL)       │   │ daily summary (file,  │
 │ RemoteOK/Remotive │   │ 4 score 0-100 + hard filters         │   │   e-mail, Telegram)   │
 └───────────────────┘   │ 5 top 50 -> message from your profile│   └───────────────────────┘
 LinkedIn/Indeed/Naukri  │ 6 (optional) assisted apply          │
 = deep links only       └──────────────────────────────────────┘
```

```
job-bot/
  config/        settings.yaml  profile.yaml  companies.yaml
  jobbot/        config db utils models matcher messages pipeline applier summary notify mailcheck searchlinks
  jobbot/sources ats.py (Greenhouse, Lever, Ashby)  adzuna.py  remote.py
  dashboard/     app.py                 scripts/  *.bat, register_task.ps1
  n8n/           jobbot-daily.json      .github/workflows/daily.yml (optional)
  resume/        put resume.pdf here    tests/    test_bot.py
```

## Honest limits (read this)

* **LinkedIn, Indeed, Naukri, Wellfound are not scraped or auto-applied.** Their terms forbid it, they detect bots, and accounts get banned. The bot gives you pre-filtered links (last 24h, entry-level) in the daily summary and dashboard; you open them. For these, the bot still prepares the message.
* **Auto-apply covers only Greenhouse, Lever and Ashby forms** (public company application pages). Expect many forms to need you: custom questions, consent checkboxes and CAPTCHA are never auto-handled. In those cases it fills what it can and stops. Default is `auto_submit: false` - you review and click Submit.
* Scheduled unattended runs can only submit when everything is filled and there is no CAPTCHA; otherwise the job goes to "Needs my action".
* Company lists are manual: you add Greenhouse/Lever/Ashby board tokens in `config/companies.yaml`. The three examples may be wrong/changed; bad tokens are skipped with a warning.
* Adzuna returns short description snippets, so skill scoring is weaker for those jobs. Free-tier call limits change; check Adzuna's page. Remotive asks for very few requests per day, and RemoteOK asks for a link back to them if you republish.
* Remote jobs are often region-restricted; the bot drops obvious US/EU-only ones but cannot catch all.
* Dedupe key is title + company, so the same title at the same company in two cities counts once.
* Windows Task Scheduler only runs when the PC is on (the script uses "run when available" to catch up). GitHub Actions can run while your PC is off but is search-only, needs a **private** repo, and cron can be delayed by many minutes. n8n self-hosted also needs your PC/server on.
* Score weights are my heuristic, not a guarantee of fit. Skim shortlisted jobs before applying.

## Setup on Windows

1. Install Python 3.10+ (tick "Add to PATH"). Open the `job-bot` folder.
2. Double-click `scripts\setup.bat` (creates `.venv`, installs packages and Chromium, copies `.env`).
3. Edit `.env`: `PROFILE_EMAIL`, `PROFILE_PHONE`, `GITHUB_URL`. Optional: Adzuna, Gmail app password, Telegram.
4. Copy your resume to `resume\resume.pdf`.
5. Open `config\profile.yaml`, compare each line to your resume, then set `verified: true`.
6. Test: `.venv\Scripts\activate` then `python -m jobbot check` and `python -m jobbot run --no-notify`.
7. Dashboard: `scripts\dashboard.bat`.

## Configure

| What | Where |
|---|---|
| Resume | `resume\resume.pdf` (path in `profile.yaml: resume_path`) |
| Skills, projects, headline, exclusions | `config\profile.yaml` (only true statements) |
| Locations | `profile.yaml: preferred_locations` (scoring) and `settings.yaml: manual_search.locations`, `search.adzuna_locations` |
| Roles | `profile.yaml: target_roles`, `settings.yaml: manual_search.roles`, `search.adzuna_queries` |
| Max jobs, age, min score, max years | `settings.yaml: search` |
| Sources on/off | `settings.yaml: sources` |
| Company boards | `config\companies.yaml` |
| E-mail / Telegram | `settings.yaml: notifications` + `.env` |

## Daily 9:00 AM IST

**Task Scheduler (recommended):** set Windows time zone to India Standard Time, then in PowerShell:
`powershell -ExecutionPolicy Bypass -File scripts\register_task.ps1`
It runs `scripts\run_daily.bat` (search, score, summary, inbox check). Logs: `logs\jobbot.log`, `logs\task.log`.

**n8n (self-hosted):** import `n8n\jobbot-daily.json`, change the path in "Run JobBot". Newer n8n versions disable the Execute Command node by default; enable it only if you accept that.

**GitHub Actions (optional):** private repo only, add secrets, remove nothing else. The workflow commits `data/jobs.db` back to the repo.

## Daily use

```
python -m jobbot run                # what the schedule does
python -m jobbot apply              # visible browser, fills shortlisted Greenhouse/Lever/Ashby forms, you submit
python -m jobbot apply --auto       # also clicks Submit if all fields filled and no CAPTCHA (use with care)
python -m jobbot mail               # scan inbox for interview / rejection mails (keyword based, verify)
python -m jobbot mark 12 interview  # manual status change (or use the dashboard)
python -m pytest tests              # self-tests
```

Statuses: `shortlisted`, `needs_action`, `applied`, `interview`, `rejected`, `backlog` (matched but beyond the 50/day cap), `low_match`, `ignored`.

## Safety rules implemented

No hardcoded secrets (everything in `.env`). Applying is blocked until `verified: true` and a resume exists. Never solves or bypasses CAPTCHA, never hides automation, never ticks legal consents, daily cap, random delays, one application per company per 30 days, duplicates never re-inserted, every status change logged in `events`.
