import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import streamlit as st

from jobbot import config, db
from jobbot.searchlinks import build_links

st.set_page_config(page_title="Job Bot", layout="wide")
db.init()
settings = config.load_settings()

st.title("Job Application Dashboard")
s = db.stats()
c = st.columns(6)
for col, (label, val) in zip(c, [("Jobs found", s["total"]), ("Matching profile", s["matching"]),
                                 ("Applied", s["applied"]), ("Need my action", s["needs_action"]),
                                 ("Rejected", s["rejected"]), ("Interviews", s["interview"])]):
    col.metric(label, val)

tab_jobs, tab_action, tab_hist, tab_links, tab_runs = st.tabs(
    ["Jobs", "Needs my action", "History", "Manual search links", "Daily runs"])

with tab_jobs:
    rows = db.list_jobs()
    df = pd.DataFrame(rows)
    if df.empty:
        st.info("No jobs yet. Run:  python -m jobbot run")
    else:
        f1, f2, f3 = st.columns([2, 1, 2])
        statuses = f1.multiselect("Status", db.STATUSES, default=[x for x in db.STATUSES if x != "low_match"])
        min_score = f2.slider("Min score", 0, 100, 0)
        q = f3.text_input("Search title / company")
        view = df[df.status.isin(statuses) & (df.score >= min_score)]
        if q:
            view = view[view.title.str.contains(q, case=False, na=False) | view.company.str.contains(q, case=False, na=False)]
        st.dataframe(view[["id", "score", "title", "company", "location", "status", "posted_at", "source", "url"]],
                     width="stretch", hide_index=True,
                     column_config={"url": st.column_config.LinkColumn("Link")})

        st.subheader("Job details")
        if not view.empty:
            pick = st.selectbox("Select a job", view.id.tolist(),
                                format_func=lambda i: f"#{i} - {view[view.id == i].iloc[0].title} @ {view[view.id == i].iloc[0].company}")
            j = db.get_job(int(pick))
            st.markdown(f"**{j['title']}** at **{j['company']}** - {j['location'] or 'n/a'} - score **{j['score']}**")
            st.link_button("Open job page", j["url"])
            st.text_area("Prepared application message", j["message"] or "", height=260, key=f"m{pick}")
            with st.expander("Score breakdown / description"):
                st.code(j["breakdown"])
                st.write((j["description"] or "")[:3000])
            nc, sc = st.columns([3, 1])
            note = nc.text_input("Note", j["notes"] or "", key=f"n{pick}")
            new_status = sc.selectbox("Status", db.STATUSES, index=db.STATUSES.index(j["status"]), key=f"s{pick}")
            if st.button("Save"):
                db.set_note(j["id"], note)
                if new_status != j["status"]:
                    db.set_status(j["id"], new_status, note)
                st.rerun()

with tab_action:
    todo = db.list_jobs(["needs_action"])
    if not todo:
        st.success("Nothing waiting for you.")
    for j in todo:
        st.markdown(f"**#{j['id']} {j['title']}** @ {j['company']} - score {j['score']}  \n{j['notes'] or ''}  \n[Open]({j['url']})")

with tab_hist:
    ev = pd.DataFrame(db.events())
    if not ev.empty:
        st.dataframe(
            ev,
            width="stretch",
            hide_index=True,
            column_config={"url": st.column_config.LinkColumn("Link")},
        )
    else:
        st.info("No history yet.")

with tab_links:
    st.caption("These portals forbid automated access, so you open them yourself. Filters: last 24h / entry level where supported.")
    for name, url in build_links(settings):
        st.markdown(f"- [{name}]({url})")

with tab_runs:
    rr = pd.DataFrame(db.runs())
    if not rr.empty:
        st.dataframe(rr, width="stretch", hide_index=True)
    else:
        st.info("No runs yet.")
