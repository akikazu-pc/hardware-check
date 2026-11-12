@echo off
setlocal
"%SystemRoot%\System32\reg.exe" query "HKLM\SYSTEM\CurrentControlSet\Control\MiniNT" >nul 2>&1
if not errorlevel 1 goto pe
ver >nul
start "" "%~dp0AkikazuHardwareCheck.exe" --portable-rescue
exit /b %errorlevel%

:pe
if /i "%~1"=="--cli" goto cli
"%~dp0PeNetworkRescue.exe" --ui
exit /b %errorlevel%

:cli
"%~dp0PeNetworkRescue.exe"
exit /b %errorlevel%
