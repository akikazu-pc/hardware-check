@echo off
setlocal
python "%~dp0update-network-rescue.py"
set "UPDATE_EXIT=%ERRORLEVEL%"
echo.
pause
exit /b %UPDATE_EXIT%
