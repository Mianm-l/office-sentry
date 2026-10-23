# main.py
import os
import sys
import time
import json
import argparse
import datetime
import logging
import threading

# 解决 Windows GBK 终端下 Unicode/Emoji 输出编码异常
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from colorama import init, Fore, Style
init(autoreset=True)

from notify import NotificationHub
from sentry import ProbeEngine, StateManager, ReminderScheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("OfficeSentry")

def load_config(config_path: str) -> dict:
    if not os.path.exists(config_path):
        print(Fore.RED + f"[X] 找不到配置文件: {config_path}")
        sys.exit(1)
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(Fore.RED + f"[X] 读取配置文件失败: {e}")
        sys.exit(1)

def print_banner():
    banner = f"""
{Fore.CYAN}================================================================
   OfficeSentry 办公协同哨兵 (巡检报警 & 工作节律助手)
   [双通道通知: Windows Toast 桌面弹窗 + 企微/飞书/钉钉 机器人]
================================================================{Style.RESET_ALL}
"""
    print(banner)

def run_once(config: dict, probe_engine: ProbeEngine):
    """单次立即体检模式"""
    targets = [t for t in config.get("targets", []) if t.get("enabled", True)]
    print(Fore.CYAN + f"[*] 开始单次巡检（共 {len(targets)} 个目标）...\n")

    print(f"{'状态':<8} | {'服务名称':<26} | {'协议':<6} | {'耗时(ms)':<10} | {'端点 / 错误详情'}")
    print("-" * 88)

    all_ok = True
    for item in targets:
        res = probe_engine.probe(item)
        if res.success:
            status_text = Fore.GREEN + "[OK] 正常" + Style.RESET_ALL
            detail = Fore.WHITE + res.endpoint
            latency_str = f"{res.latency_ms:6.1f} ms"
        else:
            all_ok = False
            status_text = Fore.RED + "[FAIL]异常" + Style.RESET_ALL
            detail = Fore.RED + f"{res.endpoint} -> {res.error_message}"
            latency_str = f"{res.latency_ms:6.1f} ms"

        name_display = item.get("name", "")[:24]
        print(f"{status_text:<17} | {name_display:<26} | {item.get('type', 'http'):<6} | {latency_str:<10} | {detail}")

    print("-" * 88)
    if all_ok:
        print(Fore.GREEN + "\n[+] 所有巡检目标运行状态良好！\n")
    else:
        print(Fore.RED + "\n[!] 检测到部分目标异常，请核对上方报错信息。\n")

def run_daemon(config_file: str, probe_engine: ProbeEngine, notifier: NotificationHub, state_mgr: StateManager, reminder_mgr: ReminderScheduler):
    """常驻后台循环巡检模式"""
    # 启动后台 ChatOps 机器人 Webhook 与 Web 服务监听 (端口 9527)
    try:
        from ui_server import run_server
        server_thread = threading.Thread(target=run_server, kwargs={"open_browser": False}, daemon=True)
        server_thread.start()
        print(Fore.CYAN + f"[*] 机器人 ChatOps 回调与配置服务已在后台就绪 (端口 9527)")
    except Exception as e:
        logger.warning(f"后台 Web 服务启动跳过: {e}")

    init_config = load_config(config_file)
    sys_cfg = init_config.get("system", {})
    interval = sys_cfg.get("scan_interval_seconds", 30)

    print(Fore.GREEN + f"[+] OfficeSentry 守护巡检已启动！")
    print(Fore.WHITE + f"    - 巡检轮询间隔: 每 {interval} 秒")
    print(Fore.WHITE + f"    - 失败告警阈值: 连续 {sys_cfg.get('fail_threshold', 2)} 次失败触发")
    print(Fore.WHITE + f"    - 告警冷却周期: {sys_cfg.get('cooldown_minutes', 15)} 分钟")
    print(Fore.YELLOW + f"    [提示: 支持群机器人在线查增改，按 Ctrl + C 可退出]\n")

    while True:
        try:
            # 动态热加载最新配置（机器人或网页端改动立即生效）
            config = load_config(config_file)
            targets = [t for t in config.get("targets", []) if t.get("enabled", True)]
            now_str = datetime.datetime.now().strftime("%H:%M:%S")

            for item in targets:
                res = probe_engine.probe(item)
                event, details = state_mgr.update(res)

                if event == "ALERT":
                    print(Fore.RED + f"[{now_str}] [!] 触发故障告警: {res.name} (连续失败 {details['consecutive_fails']} 次)")
                    notifier.send_alert(
                        target_name=res.name,
                        target_url=res.endpoint,
                        error_msg=details['error_message'],
                        consecutive_fails=details['consecutive_fails'],
                        latency_ms=details['latency_ms']
                    )
                elif event == "REPEAT_ALERT":
                    print(Fore.YELLOW + f"[{now_str}] [!] 持续故障续报: {res.name}")
                    notifier.send_alert(
                        target_name=res.name,
                        target_url=res.endpoint,
                        error_msg=details['error_message'],
                        consecutive_fails=details['consecutive_fails'],
                        latency_ms=details['latency_ms']
                    )
                elif event == "RECOVERY":
                    print(Fore.GREEN + f"[{now_str}] [+] 故障已恢复: {res.name} (历时 {details['downtime_duration']})")
                    notifier.send_recovery(
                        target_name=res.name,
                        target_url=res.endpoint,
                        downtime_duration=details['downtime_duration'],
                        latency_ms=details['latency_ms']
                    )

            # 执行日常协同与健康节律检查
            reminder_mgr.tick()

            time.sleep(interval)
        except KeyboardInterrupt:
            print(Fore.CYAN + "\n[*] OfficeSentry 已安全退出。祝工作愉快！")
            break
        except Exception as e:
            logger.error(f"主巡检循环异常: {e}")
            time.sleep(5)

def main():
    parser = argparse.ArgumentParser(description="OfficeSentry 办公协同哨兵")
    parser.add_argument("--config", "-c", default="config.json", help="配置文件路径 (默认: config.json)")
    parser.add_argument("--once", action="store_true", help="单次体检并输出终端报告后退出")
    parser.add_argument("--test-notify", action="store_true", help="测试桌面与所有已配置的群机器人通知通道")
    parser.add_argument("--ui", action="store_true", help="启动可视化傻瓜式配置后台网页")
    args = parser.parse_args()

    if args.ui:
        from ui_server import run_server
        run_server()
        return

    base_dir = os.path.dirname(os.path.abspath(__file__))
    config_file = args.config if os.path.isabs(args.config) else os.path.join(base_dir, args.config)

    config = load_config(config_file)
    print_banner()

    notifier = NotificationHub(config)
    probe_engine = ProbeEngine(default_timeout=config.get("system", {}).get("default_timeout_seconds", 5.0))
    state_mgr = StateManager(
        fail_threshold=config.get("system", {}).get("fail_threshold", 2),
        cooldown_minutes=config.get("system", {}).get("cooldown_minutes", 15)
    )
    reminder_mgr = ReminderScheduler(config, notifier)

    if args.test_notify:
        print(Fore.YELLOW + "[*] 正在执行通知通道全链路联调测试...\n")
        notifier.send_test_notification()
        print(Fore.GREEN + "\n测试完毕！请检查桌面右下角及工作群中是否已收到测试消息。")
        return

    if args.once:
        run_once(config, probe_engine)
        return

    # 默认进入守护进程
    run_daemon(config_file, probe_engine, notifier, state_mgr, reminder_mgr)

if __name__ == "__main__":
    main()
