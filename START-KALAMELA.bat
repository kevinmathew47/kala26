@echo off
title Kalamela 2026 - Attendance Tracker
cd /d "%~dp0"
echo Starting Kalamela 2026 attendance tracker...
start "" http://localhost:8000
python server.py --port 8000
pause
