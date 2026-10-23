@echo off
chcp 65001 >nul
title OfficeSentry 办公协同哨兵

echo ================================================================
echo    OfficeSentry 办公协同哨兵 (巡检报警与日常工作助手)
echo ================================================================
echo.
echo 常用功能提示:
echo   - 傻瓜式网页配置: 双击【配置助手.bat】或运行 python main.py --ui
echo   - 立即做一次体检: 运行 python main.py --once
echo   - 联调所有通知通道: 运行 python main.py --test-notify
echo.
echo 正在启动常驻后台巡检... (退出直接关闭窗口或按 Ctrl + C)
echo ================================================================
echo.

python main.py

pause
