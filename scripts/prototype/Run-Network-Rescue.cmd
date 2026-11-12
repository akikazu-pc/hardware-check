@echo off
setlocal
if /i "%~1"=="--cli" goto cli
"%~dp0NetworkRescue.exe" --gui
exit /b %errorlevel%

:cli
"%~dp0PeNetworkRescue.exe"
exit /b %errorlevel%
