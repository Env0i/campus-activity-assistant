@echo off
rem Dev-only launcher: starts an offline mobile UI preview server on 127.0.0.1.
rem Accepts optional args such as: --state unknown --port 8792
chcp 65001 >nul
cd /d "%~dp0"
python dev_phone_preview.py %*
if errorlevel 1 pause
