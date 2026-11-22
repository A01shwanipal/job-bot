import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from jobbot import config, db, pipeline
from jobbot.matcher import parse_experience, score_job
from jobbot.models import Job

S, P = config.load_settings(), config.load_profile()
P["personal"]["email"], P["personal"]["phone"] = "a@b.com", "9999999999"


def mk(title, loc="Noida, India", desc="Java Spring Boot REST APIs MySQL. 0-1 years experience.", age_h=10, company="Acme", url=None):
    posted = (datetime.now(timezone.utc) - timedelta(hours=age_h)).isoformat()
    return Job("test", title, company, url or f"https://jobs.lever.co/acme/{title.replace(' ', '')}", loc, desc, posted)


def test_good_fresher_job_scores_high():
    r = score_job(mk("Java Developer"), P, S)
    assert r.eligible and r.total >= 80


def test_senior_and_experience_rejected():
    assert not score_job(mk("Senior Java Developer"), P, S).eligible
    assert not score_job(mk("Java Developer", desc="Java Spring Boot. 5+ years of experience required"), P, S).eligible


def test_location_and_stack_filters():
    assert not score_job(mk("Java Developer", loc="Bengaluru"), P, S).eligible
    assert not score_job(mk("Python Developer", desc="Python Django"), P, S).eligible
    assert not score_job(mk("Java Developer", loc="Remote - USA"), P, S).eligible
    assert score_job(mk("Backend Developer", loc="Remote - Worldwide"), P, S).eligible


def test_parse_experience():
    assert parse_experience("2-4 years of experience in Java")[0] == 2
    assert parse_experience("freshers welcome")[1] is True


@pytest.fixture
def tmpdb(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "t.db")
    monkeypatch.setattr(config, "SUMMARY_DIR", tmp_path / "sum")
    db.init()


def test_pipeline_dedupes_and_tracks(tmpdb):
    jobs = [mk("Java Developer", url="https://example.com/jobs/1"), mk("Java Developer", url="https://other.site/x"),  # same title+company
            mk("Spring Boot Developer", company="Beta", url="https://boards.greenhouse.io/beta/jobs/1"),
            mk("Senior Java Developer", company="Gamma"), mk("Java Developer", age_h=24 * 20, company="Old")]
    r1 = pipeline.run(S, P, {}, jobs=jobs, apply=False, do_notify=False)
    assert r1["shortlisted"] == 2 and r1["duplicates"] == 1
    r2 = pipeline.run(S, P, {}, jobs=jobs, apply=False, do_notify=False)
    assert r2["new"] == 0 and r2["duplicates"] >= 3          # nothing is re-added on the next day
    st = db.stats()
    assert st["by_status"].get("shortlisted") == 1            # greenhouse one waits for assisted apply
    assert st["by_status"].get("needs_action") == 1           # non-ATS portal -> manual apply
    assert "Dear Acme Hiring Team" in db.list_jobs(["needs_action"])[0]["message"]
