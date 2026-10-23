@echo off
chcp 65001 >nul
title 停止 OfficeSentry

echo ================================================================
echo    正在安全停止 OfficeSentry 守护服务与监听端口...
echo ================================================================
echo.

set FOUND=0
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :9527 ^| findstr LISTENING') do (
    taskkill /F /PID %%a >nul 2>&1
    set FOUND=1
)

if %FOUND% equ 1 (
    echo [+] OfficeSentry 后台进程已安全关闭。
) else (
    echo [i] 未检测到正在运行的 OfficeSentry 服务 (端口 9527 未被占用)。
)

echo.
pause
