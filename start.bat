@echo off
chcp 65001 >nul
title OfficeSentry 后台启动器

echo ================================================================
echo    OfficeSentry 办公协同哨兵 (后台静默启动)
echo ================================================================
echo.
echo 正在后台无感启动哨兵服务与机器人回调...
cscript //nologo start_silent.vbs

timeout /t 2 >nul
netstat -ano | findstr :9527 | findstr LISTENING >nul
if %errorlevel% equ 0 (
    echo.
    echo [+] 哨兵已成功在后台静默运行（无控制台黑框打扰）！
    echo [i] 常用操作：
    echo     - 打开配置后台: 双击【配置助手.bat】
    echo     - 停止后台服务: 双击【stop.bat】
    echo     - 设置开机自启: 双击【add_to_startup.bat】
    echo.
) else (
    echo.
    echo [!] 启动检测超时，请直接双击【run.bat】查看控制台详细日志。
    echo.
)

pause
