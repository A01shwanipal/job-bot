"""Assisted application filler (Playwright).

Scope: only company career forms hosted on Greenhouse, Lever and Ashby - their public application forms.
LinkedIn / Indeed / Naukri are NOT automated (their terms forbid it and they actively ban accounts).

Safety rules baked in:
 * refuses to run until profile.yaml has `verified: true` and the resume file exists
 * a visible CAPTCHA widget, a required field it cannot fill, or auto_submit=false -> a HUMAN submits
 * never solves/bypasses CAPTCHA, never hides automation, never ticks legal-consent boxes
 * one application per company per N days, daily cap, random delays
"""
import logging
import random
import re
import sys
import time

from . import config, db

log = logging.getLogger(__name__)

SUPPORTED = ("greenhouse.io", "lever.co", "ashbyhq.com")


def ats_of(url: str) -> str | None:
    for s in SUPPORTED:
        if s in (url or ""):
            return s.split(".")[0]
    return None


FIELD_JS = """() => Array.from(document.querySelectorAll('input, textarea, select')).map((el, i) => {
  const r = el.getBoundingClientRect();
  const visible = !!(r.width || r.height) && getComputedStyle(el).visibility !== 'hidden';
  let label = '';
  if (el.id) { const l = document.querySelector('label[for="' + CSS.escape(el.id) + '"]'); if (l) label = l.innerText; }
  if (!label) { const l = el.closest('label'); if (l) label = l.innerText; }
  if (!label) label = el.getAttribute('aria-label') || '';
  if (!label && el.getAttribute('aria-labelledby')) {
    const l = document.getElementById(el.getAttribute('aria-labelledby')); if (l) label = l.innerText; }
  return {i, tag: el.tagName.toLowerCase(), type: (el.type || '').toLowerCase(), name: el.name || '', id: el.id || '',
          placeholder: el.placeholder || '', label: (label || '').trim(), visible,
          required: !!(el.required || el.getAttribute('aria-required') === 'true'),
          value: el.value || '', checked: !!el.checked, files: el.files ? el.files.length : 0};
})"""

CAPTCHA_SEL = ("iframe[src*='recaptcha'], iframe[src*='hcaptcha'], iframe[src*='turnstile'], "
               ".g-recaptcha, .h-captcha, .cf-turnstile")


def _hint(d: dict) -> str:
    return " ".join([d["label"], d["name"], d["id"], d["placeholder"]]).lower()


def _value_for(d: dict, v: dict) -> str | None:
    if d["type"] in ("hidden", "submit", "button", "checkbox", "radio", "password", "file", "search"):
        return None
    h = _hint(d)
    if d["tag"] == "textarea":
        if re.search(r"cover letter|message|additional information|anything else|introduce|about yourself", h):
            return v["message"]
        return None
    rules = [
        (r"linkedin", v["linkedin"]), (r"github", v["github"]),
        (r"portfolio|website|personal (site|url)|other url", v["portfolio"]),
        (r"first.?name|given.?name|fname", v["first_name"]),
        (r"last.?name|surname|family.?name|lname", v["last_name"]),
        (r"full.?name|your name|^name\b", v["full_name"]),
        (r"e-?mail", v["email"]), (r"phone|mobile|contact number", v["phone"]),
        (r"current location|\bcity\b|location", v["city"]),
    ]
    for pat, val in rules:
        if val and re.search(pat, h):
            return val
    return None


def _values(job: dict, profile: dict) -> dict:
    per, links = profile["personal"], profile["links"]
    return {"first_name": per["first_name"], "last_name": per["last_name"], "full_name": per["full_name"],
            "email": per["email"], "phone": per["phone"], "city": per.get("city", ""),
            "linkedin": links.get("linkedin", ""), "github": links.get("github", ""),
            "portfolio": links.get("portfolio", ""), "message": job.get("message", "")}


def _fill(page, values: dict, resume: str) -> int:
    fields = page.evaluate(FIELD_JS)
    loc = page.locator("input, textarea, select")
    file_inputs = [d for d in fields if d["type"] == "file"]
    filled = 0
    for d in fields:
        try:
            if d["type"] == "file":
                h = _hint(d)
                if re.search(r"cover", h):
                    continue
                if re.search(r"resume|cv", h) or len(file_inputs) == 1:
                    if d["files"] == 0:
                        loc.nth(d["i"]).set_input_files(resume)
                        filled += 1
                continue
            if not d["visible"] or d["value"]:
                continue
            val = _value_for(d, values)
            if val:
                loc.nth(d["i"]).fill(val, timeout=3000)
                filled += 1
        except Exception as e:  # one odd field must not kill the run
            log.debug("could not fill %s: %s", _hint(d), e)
    return filled


def _missing_required(page) -> list[str]:
    out = []
    for d in page.evaluate(FIELD_JS):
        if not d["required"] or d["type"] in ("hidden", "radio", "submit", "button"):
            continue
        if d["type"] == "file":
            empty = d["files"] == 0
        elif d["type"] == "checkbox":
            empty = not d["checked"] and d["visible"]
        else:
            empty = d["visible"] and not d["value"]
        if empty:
            out.append((d["label"] or d["name"] or d["id"] or d["type"]).split("\n")[0][:60])
    return out


def _form_url(url: str) -> str:
    u = url.rstrip("/")
    if "jobs.lever.co" in u and not u.endswith("/apply"):
        return u + "/apply"
    if "ashbyhq.com" in u and not u.endswith("/application"):
        return u + "/application"
    return url


def _apply_one(page, job: dict, profile: dict, auto_submit: bool, interactive: bool) -> tuple[str, str]:
    page.goto(_form_url(job["url"]), wait_until="domcontentloaded", timeout=45000)
    page.wait_for_timeout(2500)
    values = _values(job, profile)
    filled = _fill(page, values, profile["resume_abs"])
    if not filled:  # maybe an "Apply" button must be clicked first
        try:
            page.get_by_role("link", name=re.compile(r"^\s*apply", re.I)).first.click(timeout=3000)
            page.wait_for_timeout(2500)
            filled = _fill(page, values, profile["resume_abs"])
        except Exception:
            pass
    if not filled:
        return "needs_action", "could not find an application form - apply manually"

    missing = _missing_required(page)
    captcha = page.locator(CAPTCHA_SEL).count() > 0
    reasons = []
    if captcha:
        reasons.append("CAPTCHA present (solve it yourself)")
    if missing:
        reasons.append("required fields not filled: " + ", ".join(missing[:6]))
    if not auto_submit:
        reasons.append("auto_submit is off")

    if reasons:
        reason = "; ".join(reasons)
        if interactive:
            print(f"\n>>> {job['title']} @ {job['company']}\n    {reason}")
            print("    Review the form in the browser, finish any missing parts, and click Submit yourself.")
            ans = input("    [y] I submitted it   [n] not submitted   [s] skip > ").strip().lower()
            if ans == "y":
                return "applied", "submitted manually after assisted fill"
            if ans == "s":
                return "skipped", ""
            return "needs_action", reason
        return "needs_action", reason

    btn = page.locator("button[type=submit], input[type=submit]").first
    if btn.count() == 0:
        btn = page.get_by_role("button", name=re.compile(r"submit", re.I)).first
    btn.click(timeout=5000)
    page.wait_for_timeout(6000)
    body = page.inner_text("body").lower()
    if re.search(r"thank you for (applying|your application)|application (has been )?(submitted|received)|"
                 r"successfully submitted", body):
        return "applied", "submitted automatically"
    return "needs_action", "clicked Submit but could not confirm success - check the site / your e-mail"


def run_apply(settings: dict, profile: dict, limit: int | None = None, auto_submit: bool | None = None,
              headless: bool | None = None, interactive: bool | None = None) -> dict:
    a = settings["apply"]
    result = {"applied": 0, "needs_action": 0, "skipped": 0, "blocked": []}
    problems = config.profile_problems(profile, for_apply=True)
    if problems:
        log.error("Apply blocked: %s", "; ".join(problems))
        result["blocked"] = problems
        return result
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        log.error("Playwright not installed: pip install playwright && playwright install chromium")
        result["blocked"] = ["playwright missing"]
        return result

    auto = a.get("auto_submit", False) if auto_submit is None else auto_submit
    headless = a.get("headless", True) if headless is None else headless
    interactive = (not headless and sys.stdin.isatty()) if interactive is None else interactive
    cap = max(0, (limit or a.get("max_per_day", 10)) - db.count_applied_today())
    jobs = [j for j in db.list_jobs(["shortlisted"]) if ats_of(j["url"])]
    log.info("Apply: %d candidate jobs, cap %d, auto_submit=%s, headless=%s", len(jobs), cap, auto, headless)

    done = 0
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        ctx = browser.new_context()
        for j in jobs:
            if done >= cap:
                break
            if db.applied_recently(j["company"], int(a.get("one_application_per_company_days", 30))):
                db.set_status(j["id"], "ignored", "already applied to this company recently")
                continue
            page = ctx.new_page()
            try:
                status, detail = _apply_one(page, j, profile, auto, interactive)
            except Exception as e:
                log.exception("apply failed for job %s", j["id"])
                status, detail = "needs_action", f"automation error: {e}"
            finally:
                page.close()
            if status == "skipped":
                result["skipped"] += 1
                continue
            db.set_status(j["id"], status, detail)
            result[status] = result.get(status, 0) + 1
            done += 1
            log.info("job %s (%s @ %s): %s - %s", j["id"], j["title"], j["company"], status, detail)
            time.sleep(random.uniform(*a.get("delay_seconds", [25, 60])))
        browser.close()
    return result
