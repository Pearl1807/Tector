@echo off
title Tector
cd /d "%~dp0"
rem Runs the detector on this computer (fast, works offline). Add --space Miration/Tector to use the online Space instead.
".venv\Scripts\python.exe" agent\watcher.py %*
pause
