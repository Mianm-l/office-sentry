# notify/notifier.py
import datetime
import logging
from typing import Dict, Any

from .toast import send_toast
from .wechat import send_wechat_markdown
from .feishu import send_feishu_card
from .dingtalk import send_dingtalk_markdown

logger = logging.getLogger("OfficeSentry.Notifier")

class NotificationHub:
    """
    双通道通知分发中枢：
    负责将告警、恢复通知与办公提醒，同时派发到本地桌面 Toast 与各群机器人 Webhook。
    """
    def __init__(self, config: Dict[str, Any]):
        self.config = config.get("notifications", {})
        self.toast_enabled = self.config.get("desktop_toast", {}).get("enabled", True)
        self.wechat_cfg = self.config.get("wechat_work", {})
        self.feishu_cfg = self.config.get("feishu", {})
        self.dingtalk_cfg = self.config.get("dingtalk", {})

    def send_alert(self, target_name: str, target_url: str, error_msg: str, consecutive_fails: int, latency_ms: float = 0):
        """
        触发服务异常报警（桌面 Toast + Webhook 机器人）
        """
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        title = f"⚠️ [服务异常] {target_name}"
        short_msg = f"已连续失败 {consecutive_fails} 次！\n原因: {error_msg}"

        # 1. 本地 Windows 桌面通知
        if self.toast_enabled:
            send_toast(title=title, message=short_msg)

        # 2. 企微 Markdown
        if self.wechat_cfg.get("enabled"):
            wechat_content = (
                f"### <font color=\"warning\">⚠️ 服务心跳告警：{target_name}</font>\n"
                f"> **监控目标**: `{target_url}`\n"
                f"> **告警级别**: 高（连续失败 {consecutive_fails} 次）\n"
                f"> **异常详情**: <font color=\"warning\">{error_msg}</font>\n"
                f"> **响应耗时**: {latency_ms:.1f}ms\n"
                f"> **告警时间**: {now_str}\n"
                f"\n请相关研发/运维人员及时排查！"
            )
            send_wechat_markdown(self.wechat_cfg.get("webhook_url", ""), wechat_content)

        # 3. 飞书卡片
        if self.feishu_cfg.get("enabled"):
            feishu_content = (
                f"**监控目标**: `{target_url}`\n"
                f"**连续失败**: {consecutive_fails} 次\n"
                f"**异常详情**: {error_msg}\n"
                f"**响应耗时**: {latency_ms:.1f}ms\n"
                f"**发生时间**: {now_str}"
            )
            send_feishu_card(
                self.feishu_cfg.get("webhook_url", ""),
                title=f"⚠️ 服务心跳异常 - {target_name}",
                content=feishu_content,
                level="error"
            )

        # 4. 钉钉 Markdown
        if self.dingtalk_cfg.get("enabled"):
            dingtalk_text = (
                f"### ⚠️ 服务心跳告警：{target_name}\n"
                f"- **监控目标**: `{target_url}`\n"
                f"- **连续失败**: {consecutive_fails} 次\n"
                f"- **异常详情**: {error_msg}\n"
                f"- **告警时间**: {now_str}\n"
            )
            send_dingtalk_markdown(
                self.dingtalk_cfg.get("webhook_url", ""),
                title=title,
                text=dingtalk_text,
                at_all=self.dingtalk_cfg.get("at_all", False)
            )

    def send_recovery(self, target_name: str, target_url: str, downtime_duration: str, latency_ms: float = 0):
        """
        触发服务恢复通告
        """
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        title = f"✅ [服务已恢复] {target_name}"
        short_msg = f"服务已重新恢复正常 (耗时 {latency_ms:.1f}ms)\n中断历时约: {downtime_duration}"

        # 1. 桌面通知
        if self.toast_enabled:
            send_toast(title=title, message=short_msg)

        # 2. 企微 Markdown
        if self.wechat_cfg.get("enabled"):
            wechat_content = (
                f"### <font color=\"info\">✅ 服务恢复通告：{target_name}</font>\n"
                f"> **监控目标**: `{target_url}`\n"
                f"> **状态**: <font color=\"info\">恢复正常 (200 OK)</font>\n"
                f"> **当前耗时**: {latency_ms:.1f}ms\n"
                f"> **故障历时**: {downtime_duration}\n"
                f"> **恢复时间**: {now_str}"
            )
            send_wechat_markdown(self.wechat_cfg.get("webhook_url", ""), wechat_content)

        # 3. 飞书卡片
        if self.feishu_cfg.get("enabled"):
            feishu_content = (
                f"**监控目标**: `{target_url}`\n"
                f"**状态**: 恢复正常\n"
                f"**当前延迟**: {latency_ms:.1f}ms\n"
                f"**故障历时**: {downtime_duration}\n"
                f"**恢复时间**: {now_str}"
            )
            send_feishu_card(
                self.feishu_cfg.get("webhook_url", ""),
                title=f"✅ 服务已恢复 - {target_name}",
                content=feishu_content,
                level="success"
            )

        # 4. 钉钉 Markdown
        if self.dingtalk_cfg.get("enabled"):
            dingtalk_text = (
                f"### ✅ 服务恢复通告：{target_name}\n"
                f"- **监控目标**: `{target_url}`\n"
                f"- **状态**: 恢复正常 ({latency_ms:.1f}ms)\n"
                f"- **故障历时**: {downtime_duration}\n"
                f"- **恢复时间**: {now_str}\n"
            )
            send_dingtalk_markdown(
                self.dingtalk_cfg.get("webhook_url", ""),
                title=title,
                text=dingtalk_text,
                at_all=False
            )

    def send_reminder(self, title: str, message: str, to_webhook: bool = False):
        """
        发送日常办公/协同节律提醒（如下班工时、喝水休息）
        """
        if self.toast_enabled:
            send_toast(title=title, message=message)

        if to_webhook:
            now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
            if self.wechat_cfg.get("enabled"):
                send_wechat_markdown(
                    self.wechat_cfg.get("webhook_url", ""),
                    f"### <font color=\"comment\">{title}</font>\n> {message}\n> *提醒时间: {now_str}*"
                )
            if self.feishu_cfg.get("enabled"):
                send_feishu_card(
                    self.feishu_cfg.get("webhook_url", ""),
                    title=title,
                    content=f"{message}\n\n*提醒时间: {now_str}*",
                    level="info"
                )
            if self.dingtalk_cfg.get("enabled"):
                send_dingtalk_markdown(
                    self.dingtalk_cfg.get("webhook_url", ""),
                    title=title,
                    text=f"### {title}\n- {message}\n- 时间: {now_str}"
                )

    def send_test_notification(self):
        """
        测试所有已开启的通知通道
        """
        title = "🔔 [OfficeSentry] 通知通道联调测试"
        msg = "如果你看到了这条消息，说明你的双通道通知（桌面 + Webhook）配置完全正常！"
        print(f"\n[1/4] 测试本地桌面 Toast 通知...")
        if self.toast_enabled:
            ok = send_toast(title, msg)
            print(f"      -> 桌面 Toast: {'成功' if ok else '失败'}")
        else:
            print("      -> 桌面 Toast 未启用")

        print(f"[2/4] 测试企业微信 Webhook...")
        if self.wechat_cfg.get("enabled"):
            ok = send_wechat_markdown(self.wechat_cfg.get("webhook_url", ""), f"### 🔔 {title}\n> {msg}")
            print(f"      -> 企业微信: {'成功' if ok else '失败'}")
        else:
            print("      -> 企业微信 Webhook 未启用或未配置")

        print(f"[3/4] 测试飞书 Webhook...")
        if self.feishu_cfg.get("enabled"):
            ok = send_feishu_card(self.feishu_cfg.get("webhook_url", ""), title, msg, level="info")
            print(f"      -> 飞书: {'成功' if ok else '失败'}")
        else:
            print("      -> 飞书 Webhook 未启用或未配置")

        print(f"[4/4] 测试钉钉 Webhook...")
        if self.dingtalk_cfg.get("enabled"):
            ok = send_dingtalk_markdown(self.dingtalk_cfg.get("webhook_url", ""), title, f"### {title}\n{msg}")
            print(f"      -> 钉钉: {'成功' if ok else '失败'}")
        else:
            print("      -> 钉钉 Webhook 未启用或未配置")
