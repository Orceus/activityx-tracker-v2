@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

echo ========================================
echo    ActivityX Setup
echo ========================================
echo.

set "INSTALL_DIR=%USERPROFILE%\Documents\ActivityX"
set "SETUP_DIR=%~dp0"

echo Creating installation directory...
if not exist "!INSTALL_DIR!" mkdir "!INSTALL_DIR!"

echo Copying files...
copy /Y "!SETUP_DIR!activity_tracker.exe"            "!INSTALL_DIR!\" >nul
copy /Y "!SETUP_DIR!activity_tracker_controller.exe" "!INSTALL_DIR!\" >nul
copy /Y "!SETUP_DIR!config.py"                       "!INSTALL_DIR!\" >nul

if not exist "!INSTALL_DIR!\activity_tracker.exe" (
    echo ERROR: Failed to copy files. Try running as Administrator.
    pause
    exit /b 1
)

echo Creating startup shortcuts...
set "STARTUP=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"

powershell -ExecutionPolicy Bypass -Command "$ws = New-Object -ComObject WScript.Shell; $s1 = $ws.CreateShortcut('!STARTUP!\ActivityXTracker.lnk'); $s1.TargetPath = '!INSTALL_DIR!\activity_tracker.exe'; $s1.WorkingDirectory = '!INSTALL_DIR!'; $s1.Save(); $s2 = $ws.CreateShortcut('!STARTUP!\ActivityXController.lnk'); $s2.TargetPath = '!INSTALL_DIR!\activity_tracker_controller.exe'; $s2.WorkingDirectory = '!INSTALL_DIR!'; $s2.Save()" >nul 2>&1

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
