@echo off
title Tector
cd /d "%~dp0"
".venv\Scripts\python.exe" agent\watcher.py --space Miration/Tector %*
pause
