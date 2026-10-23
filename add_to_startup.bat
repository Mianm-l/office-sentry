@echo off
chcp 65001 >nul
title 设置 OfficeSentry 开机自启

echo ================================================================
echo    OfficeSentry 开机自启设置
echo ================================================================
echo.

set SCRIPT_DIR=%~dp0
set VBS_TARGET=%SCRIPT_DIR%start_silent.vbs
set SHORTCUT_NAME=OfficeSentry.lnk
set STARTUP_DIR=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup

powershell -Command "$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut('%STARTUP_DIR%\%SHORTCUT_NAME%'); $s.TargetPath = '%VBS_TARGET%'; $s.WorkingDirectory = '%SCRIPT_DIR%'; $s.Save()"

if exist "%STARTUP_DIR%\%SHORTCUT_NAME%" (
    echo [+] 成功为 OfficeSentry 创建开机自启动快捷方式！
    echo [i] 以后每天电脑开机时，哨兵将在后台无感静默守护，不再需要手动启动。
    echo.
    echo 若需取消自启，直接在按 Win + R 输入 shell:startup，删除 OfficeSentry 快捷方式即可。
) else (
    echo [!] 设置自启失败，请手动将 start_silent.vbs 的快捷方式放入 shell:startup 目录。
)

echo.
pause
