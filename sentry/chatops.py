# sentry/chatops.py
import re
import os
import json
import logging
from typing import Dict, Any, Tuple
from .monitor import ProbeEngine

logger = logging.getLogger("OfficeSentry.ChatOps")

class ChatOpsEngine:
    """
    机器人交互指令引擎：
    支持在企微/钉钉/飞书群内通过聊天文字进行巡检查询、动态增删改监控项与配置。
    """
    def __init__(self, config_path: str):
        self.config_path = config_path
        self.probe_engine = ProbeEngine()

    def _load_config(self) -> dict:
        if not os.path.exists(self.config_path):
            return {}
        with open(self.config_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _save_config(self, cfg: dict):
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)

    def handle_command(self, raw_text: str, sender_name: str = "") -> str:
        """
        处理传入的自然语言/快捷指令，返回 Markdown 格式的机器人应答文本。
        """
        if not raw_text:
            return "收到空指令，发送【帮助】查看可用指令。"

        # 清洗指令文本（去掉 @机器人的前缀）
        text = re.sub(r"@\S+\s*", "", raw_text).strip()
        parts = text.split()
        if not parts:
            return self.cmd_help()

        action = parts[0].lower()

        # 1. 帮助说明
        if action in ["帮助", "help", "?", "？", "指令", "菜单"]:
            return self.cmd_help()

        # 2. 状态体检
        if action in ["体检", "状态", "status", "check", "ping"]:
            return self.cmd_status()

        # 3. 监控列表查询
        if action in ["查询", "列表", "list", "ls", "监控"]:
            return self.cmd_list()

        # 4. 新增监控项: 添加 <名称> <URL/IP:Port> [超时秒数]
        if action in ["添加", "新增", "add", "+"]:
            if len(parts) < 3:
                return "❌ 格式错误！正确格式：\n`添加 服务名称 网址/IP:端口`\n示例：`添加 致远OA http://192.168.1.100:8080/seeyon`"
            name = parts[1]
            endpoint = parts[2]
            timeout = float(parts[3]) if len(parts) > 3 and parts[3].replace('.', '', 1).isdigit() else 5.0
            return self.cmd_add(name, endpoint, timeout)

        # 5. 删除监控项: 删除 <名称>
        if action in ["删除", "移除", "del", "rm", "-"]:
            if len(parts) < 2:
                return "❌ 格式错误！正确格式：\n`删除 服务名称`\n示例：`删除 致远OA`"
            return self.cmd_delete(parts[1])

        # 6. 启用/停用监控项
        if action in ["启用", "开启", "enable", "start"]:
            if len(parts) < 2:
                return "❌ 请指定要启用的服务名，如：`启用 致远OA`"
            return self.cmd_toggle(parts[1], True)

        if action in ["停用", "关闭", "禁用", "disable", "stop"]:
            if len(parts) < 2:
                return "❌ 请指定要停用的服务名，如：`停用 致远OA`"
            return self.cmd_toggle(parts[1], False)

        # 7. 修改工时提醒时间: 工时提醒 18:00
        if action in ["工时提醒", "下班提醒", "工时"]:
            if len(parts) < 2:
                return "❌ 请指定时间，例如：`工时提醒 18:00`"
            return self.cmd_set_worklog_time(parts[1])

        # 8. 修改喝水提醒间隔: 喝水 45
        if action in ["喝水", "喝水提醒"]:
            if len(parts) < 2 or not parts[1].isdigit():
                return "❌ 请输入间隔分钟数，例如：`喝水 45`"
            return self.cmd_set_health_interval(int(parts[1]))

        return f"❓ 未识别的指令: `{action}`\n发送【帮助】查看可用指令。"

    def cmd_help(self) -> str:
        return (
            "### 🛡️ OfficeSentry 机器人指令中心\n\n"
            "你可以直接在群里发送以下指令控制哨兵：\n\n"
            "**🔍 状态与查询**\n"
            "- `体检` 或 `状态`：立即对所有服务测速并汇报健康状态\n"
            "- `查询` 或 `列表`：查看当前已配置的监控服务清单\n\n"
            "**➕ 增删改监控项**\n"
            "- `添加 <服务名> <网址/端口>`：添加 HTTP/TCP 监控\n"
            "  *例：`添加 致远OA http://192.168.1.100:8080/seeyon`*\n"
            "  *例：`添加 生产MySQL 192.168.1.200:3306`*\n"
            "- `删除 <服务名>`：移除指定的监控服务\n"
            "- `启用 <服务名>` / `停用 <服务名>`：快捷开关某项监控\n\n"
            "**⏰ 工作节律设置**\n"
            "- `工时提醒 17:50`：调整每日下班日报/工时提醒时间\n"
            "- `喝水 60`：调整喝水舒展提醒间隔（分钟）\n\n"
            "*(指令不区分大小写，支持简写)*"
        )

    def cmd_status(self) -> str:
        cfg = self._load_config()
        targets = [t for t in cfg.get("targets", []) if t.get("enabled", True)]
        if not targets:
            return "当前没有任何已启用的监控目标，请先发送 `添加 <服务名> <URL>` 添加。"

        lines = ["### ⚡ 监控服务即时体检报告\n"]
        total = len(targets)
        ok_count = 0

        for item in targets:
            res = self.probe_engine.probe(item)
            if res.success:
                ok_count += 1
                lines.append(f"- ✅ **{res.name}**: 正常 ({res.latency_ms:.0f}ms)")
            else:
                lines.append(f"- ❌ **{res.name}**: 异常！`{res.error_message}`")

        lines.append(f"\n> **统计**: 共巡检 {total} 个目标，正常 {ok_count} 个，异常 {total - ok_count} 个。")
        return "\n".join(lines)

    def cmd_list(self) -> str:
        cfg = self._load_config()
        targets = cfg.get("targets", [])
        if not targets:
            return "当前尚未配置任何监控目标，请发送 `添加 服务名 URL` 开始配置。"

        lines = ["### 📋 当前监控服务清单\n"]
        for idx, t in enumerate(targets, 1):
            status_icon = "🟢" if t.get("enabled", True) else "⚪(已停用)"
            endpoint = f"{t.get('host')}:{t.get('port')}" if t.get("type") == "tcp" else t.get("url", "")
            lines.append(f"{idx}. {status_icon} **{t.get('name')}** (`{t.get('type', 'http')}`)\n   `{endpoint}`")

        # 附加工时提醒配置
        worklog_time = cfg.get("reminders", {}).get("worklog_reminder", {}).get("time", "未设置")
        water_min = cfg.get("reminders", {}).get("health_break", {}).get("interval_minutes", "未设置")
        lines.append(f"\n> ⏰ 下班工时提醒: `{worklog_time}` | 💧 喝水间隔: `{water_min}分钟`")
        return "\n".join(lines)

    def cmd_add(self, name: str, endpoint: str, timeout: float = 5.0) -> str:
        cfg = self._load_config()
        targets = cfg.get("targets", [])

        # 检查是否已存在同名目标
        for t in targets:
            if t.get("name") == name:
                return f"⚠️ 监控项【{name}】已存在！如需更新请先发送 `删除 {name}`。"

        # 自动识别是 TCP (形如 192.168.1.1:3306) 还是 HTTP
        if "://" not in endpoint and ":" in endpoint:
            # 可能是 host:port
            parts = endpoint.split(":")
            host = parts[0]
            port = int(parts[1]) if parts[1].isdigit() else 80
            new_target = {
                "id": f"target_{int(os.times()[4] * 1000)}",
                "name": name,
                "type": "tcp",
                "host": host,
                "port": port,
                "timeout": timeout,
                "enabled": True
            }
        else:
            # HTTP/HTTPS
            url = endpoint if endpoint.startswith("http") else f"http://{endpoint}"
            new_target = {
                "id": f"target_{int(os.times()[4] * 1000)}",
                "name": name,
                "type": "http",
                "url": url,
                "method": "GET",
                "expected_status": [200, 204, 302],
                "timeout": timeout,
                "enabled": True
            }

        # 先立即测速试一下
        res = self.probe_engine.probe(new_target)
        targets.append(new_target)
        cfg["targets"] = targets
        self._save_config(cfg)

        test_info = f"即时测速: 正常 ({res.latency_ms:.0f}ms)" if res.success else f"即时测速: 异常 ({res.error_message})"
        return (
            f"✅ **监控目标添加成功！**\n"
            f"- **服务名称**: {name}\n"
            f"- **监控端点**: `{endpoint}`\n"
            f"- **当前状态**: {test_info}\n"
            f"\n配置已持久化保存，守护进程将在下一个周期纳入轮询。"
        )

    def cmd_delete(self, name: str) -> str:
        cfg = self._load_config()
        targets = cfg.get("targets", [])
        original_len = len(targets)
        targets = [t for t in targets if t.get("name") != name and t.get("id") != name]

        if len(targets) == original_len:
            return f"❌ 未找到名为【{name}】的监控目标。发送 `查询` 可查看当前列表。"

        cfg["targets"] = targets
        self._save_config(cfg)
        return f"🗑️ 已成功删除监控目标【{name}】！"

    def cmd_toggle(self, name: str, enable: bool) -> str:
        cfg = self._load_config()
        targets = cfg.get("targets", [])
        found = False
        for t in targets:
            if t.get("name") == name or t.get("id") == name:
                t["enabled"] = enable
                found = True
                break

        if not found:
            return f"❌ 未找到名为【{name}】的监控目标。"

        cfg["targets"] = targets
        self._save_config(cfg)
        action_text = "已启用 🟢" if enable else "已停用 ⚪"
        return f"👌 监控目标【{name}】{action_text}！"

    def cmd_set_worklog_time(self, time_str: str) -> str:
        # 简单校验 HH:MM 格式
        if not re.match(r"^\d{1,2}:\d{2}$", time_str):
            return "❌ 时间格式错误，正确格式如：`17:50` 或 `18:00`"

        cfg = self._load_config()
        cfg.setdefault("reminders", {}).setdefault("worklog_reminder", {})["time"] = time_str
        cfg["reminders"]["worklog_reminder"]["enabled"] = True
        self._save_config(cfg)
        return f"⏰ 每日下班工时提醒时间已修改为: `{time_str}`！"

    def cmd_set_health_interval(self, minutes: int) -> str:
        if minutes < 10 or minutes > 240:
            return "❌ 间隔时间建议在 10 ~ 240 分钟之间。"

        cfg = self._load_config()
        cfg.setdefault("reminders", {}).setdefault("health_break", {})["interval_minutes"] = minutes
        cfg["reminders"]["health_break"]["enabled"] = True
        self._save_config(cfg)
        return f"💧 喝水舒展提醒间隔已更新为每 `{minutes}` 分钟一次！"
