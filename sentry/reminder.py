# sentry/reminder.py
import datetime
import time
import logging
from typing import Dict, Any, List

logger = logging.getLogger("OfficeSentry.Reminder")

class ReminderScheduler:
    """
    办公日常协同与健康节律提醒器：
    - 支持每日定时提醒（如 17:50 下班前工时填报提醒）
    - 支持周期性久坐喝水与肩颈舒展提醒
    - 支持自定义工作日/工作时间段静音
    """
    def __init__(self, config: Dict[str, Any], notifier_hub):
        self.config = config.get("reminders", {})
        self.notifier = notifier_hub
        self.last_worklog_date = ""
        self.last_water_time = time.time()

    def tick(self):
        """主循环每次迭代调用一次"""
        if not self.config.get("enabled", True):
            return

        now = datetime.datetime.now()
        today_str = now.strftime("%Y-%m-%d")
        current_time_str = now.strftime("%H:%M")
        weekday = now.isoweekday() # 1-7 (周一到周日)

        # 仅在工作日生效 (周一到周五)
        workdays_only = self.config.get("workdays_only", True)
        if workdays_only and weekday > 5:
            return

        # 1. 工时与日报提醒 (如 17:50)
        worklog_cfg = self.config.get("worklog_reminder", {})
        if worklog_cfg.get("enabled", True):
            target_time = worklog_cfg.get("time", "17:50")
            if current_time_str == target_time and self.last_worklog_date != today_str:
                self.last_worklog_date = today_str
                title = worklog_cfg.get("title", "⏰ 每日工时与日报提醒")
                message = worklog_cfg.get(
                    "message",
                    "今日工作接近尾声，请记得抽空填报工时与工作日志，避免遗漏哦！"
                )
                logger.info(f"触发工时提醒: {title}")
                self.notifier.send_reminder(title, message, to_webhook=worklog_cfg.get("notify_webhook", False))

        # 2. 久坐/喝水休息提醒 (如每隔 60 分钟)
        water_cfg = self.config.get("health_break", {})
        if water_cfg.get("enabled", True):
            interval_min = water_cfg.get("interval_minutes", 60)
            work_start = water_cfg.get("start_hour", 9)
            work_end = water_cfg.get("end_hour", 18)

            if work_start <= now.hour < work_end:
                if time.time() - self.last_water_time >= interval_min * 60:
                    self.last_water_time = time.time()
                    title = water_cfg.get("title", "💧 喝水与舒展提醒")
                    message = water_cfg.get(
                        "message",
                        "连续工作已有一段时间，站起来活动下肩颈、喝杯温水远眺一下吧！"
                    )
                    logger.info(f"触发健康提醒: {title}")
                    self.notifier.send_reminder(title, message, to_webhook=False)
