from fastapi import FastAPI
from fastapi.responses import HTMLResponse

app = FastAPI(title="Job Bot")

@app.get("/", response_class=HTMLResponse)
def dashboard():
    return """<!doctype html>
<html>
<head>
  <meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Job Bot</title>
  <style>
    body{font-family:system-ui,-apple-system,sans-serif;margin:0;background:#f5f7fb;color:#172033}
    main{max-width:880px;margin:40px auto;padding:24px}.card{background:white;border-radius:16px;padding:24px;box-shadow:0 8px 24px #1d2d5012}
    h1{margin-top:0}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px;margin:20px 0}
    .stat{padding:16px;border-radius:12px;background:#edf3ff}.links a{display:block;margin:10px 0;color:#3554c4}
  </style>
</head>
<body><main><div class="card">
  <h1>Job Bot Dashboard</h1><p>Cloud deployment is live. Search and applying require the local environment's database and secrets.</p>
  <div class="grid">
    <div class="stat"><b>Status</b><br>Online</div>
    <div class="stat"><b>Database</b><br>Local only</div>
    <div class="stat"><b>Auto apply</b><br>Disabled</div>
  </div>
  <h2>Manual job search</h2><div class="links">
    <a href="https://www.linkedin.com/jobs/search/?keywords=Java+Developer&location=Noida&f_TPR=r86400&f_E=1%2C2">LinkedIn — Java Developer, Noida</a>
    <a href="https://in.indeed.com/jobs?q=Java+Developer&l=Noida&fromage=1">Indeed — Java Developer, Noida</a>
    <a href="https://www.naukri.com/java-developer-jobs-in-noida?experience=0">Naukri — Java Developer, Noida</a>
  </div>
</div></main></body>
</html>"""

@app.get("/api/health")
def health():
    return {"ok": True, "service": "job-bot"}
