@echo off
cd /d "%~dp0\.."
call .venv\Scripts\activate.bat
python -m jobbot run >> logs\task.log 2>&1
python -m jobbot mail >> logs\task.log 2>&1
