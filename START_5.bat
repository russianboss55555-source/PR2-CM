@echo off
cd /d "%~dp0"
python "%~dp0demo\stage5.py"
set "stage_result=%errorlevel%"
if "%stage_result%"=="0" start "" "%~dp0out\image.svg"
pause
exit /b %stage_result%
