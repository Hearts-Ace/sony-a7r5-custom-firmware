@echo off
cd /d "%~dp0"
py -3 launcher.py %*
if errorlevel 1 pause
