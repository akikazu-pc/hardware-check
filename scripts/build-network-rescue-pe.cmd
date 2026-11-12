@echo off
setlocal
set "REPO=%~dp0.."
set "PE_VSWHERE=%ProgramFiles(x86)%\Microsoft Visual Studio\Installer\vswhere.exe"
if not exist "%PE_VSWHERE%" (
    echo Visual Studio Build Tools with MSVC and the Windows SDK are required.
    exit /b 1
)
for /f "usebackq delims=" %%I in (`"%PE_VSWHERE%" -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath`) do set "PE_VS=%%I"
if not defined PE_VS exit /b 1
call "%PE_VS%\VC\Auxiliary\Build\vcvars64.bat"
if errorlevel 1 exit /b 1
set "PE_OUT=%REPO%\artifacts\network-rescue-pe"
if not exist "%PE_OUT%" mkdir "%PE_OUT%"
cl /nologo /std:c++17 /EHsc /W4 /WX /O2 /MT /utf-8 /D_WIN32_WINNT=0x0A00 /DNTDDI_VERSION=0x0A000002 /Fo"%PE_OUT%\PeNetworkRescue.obj" /Fe"%PE_OUT%\PeNetworkRescue.exe" "%REPO%\src\AkikazuNetworkRescue.PE\PeNetworkRescue.cpp" setupapi.lib version.lib advapi32.lib
exit /b %errorlevel%
