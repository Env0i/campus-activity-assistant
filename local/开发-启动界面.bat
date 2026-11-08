@echo off
rem Dev-only launcher: starts the GUI straight from the source tree.
rem Packaging uses the templates in local/launchers/ (paths written for the package root), not this file.
chcp 65001 >nul
cd /d "%~dp0"
python app.py
rem Keep the console open when startup fails (python missing, import error, ...).
if errorlevel 1 pause
