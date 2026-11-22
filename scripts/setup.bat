@echo off
cd /d "%~dp0\.."
python -m venv .venv || (echo Python 3.10+ is required & exit /b 1)
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt
playwright install chromium
if not exist .env copy .env.example .env
python -m jobbot init
echo.
echo Setup done. Next: edit .env, config\profile.yaml, put resume\resume.pdf, then run scripts\run_daily.bat
