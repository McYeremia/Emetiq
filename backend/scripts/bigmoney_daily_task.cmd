@echo off
REM Pembungkus Task Scheduler untuk pipeline harian Big Money.
REM
REM Jalan dari mesin lokal, BUKAN dari cloud: IDX membalas HTTP 403 ke IP
REM datacenter (terbukti pada runner GitHub Actions maupun Hugging Face Spaces),
REM sementara IP rumah lolos. Selama itu masih berlaku, satu-satunya tempat
REM pipeline ini bisa hidup adalah mesin ini.
REM
REM Daftarkan dengan scripts\register_bigmoney_task.ps1
REM Log: %LOCALAPPDATA%\Emetiq\logs\bigmoney-YYYY-MM-DD.log

setlocal
set "BACKEND=%~dp0.."
set "LOGDIR=%LOCALAPPDATA%\Emetiq\logs"
if not exist "%LOGDIR%" mkdir "%LOGDIR%"

for /f %%d in ('powershell -NoProfile -Command "Get-Date -Format yyyy-MM-dd"') do set "TODAY=%%d"
set "LOG=%LOGDIR%\bigmoney-%TODAY%.log"

cd /d "%BACKEND%"
echo ---------- mulai %DATE% %TIME% ---------->> "%LOG%"
"%BACKEND%\venv\Scripts\python.exe" scripts\bigmoney_daily.py>> "%LOG%" 2>&1
set "RC=%ERRORLEVEL%"
echo ---------- selesai, exit %RC% ---------->> "%LOG%"

exit /b %RC%
