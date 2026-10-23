# sentry/state.py
import time
from typing import Dict, Any, Optional, Tuple
from .monitor import ProbeResult

class TargetState:
    def __init__(self, target_id: str):
        self.target_id = target_id
        self.consecutive_failures: int = 0
        self.is_alerting: bool = False
        self.first_failure_time: Optional[float] = None
        self.last_alert_time: float = 0
        self.last_result: Optional[ProbeResult] = None

class StateManager:
    """
    状态追踪与防告警风暴引擎：
    - 支持失败阈值防抖 (连续失败 N 次才报警)
    - 告警冷却机制 (避免同一故障频繁轰炸)
    - 故障恢复自动判定与历时计算
    """
    def __init__(self, fail_threshold: int = 2, cooldown_minutes: int = 15):
        self.fail_threshold = fail_threshold
        self.cooldown_seconds = cooldown_minutes * 60
        self.states: Dict[str, TargetState] = {}

    def get_state(self, target_id: str) -> TargetState:
        if target_id not in self.states:
            self.states[target_id] = TargetState(target_id)
        return self.states[target_id]

    def update(self, result: ProbeResult) -> Tuple[Optional[str], Dict[str, Any]]:
        """
        更新探针结果，返回事件类型与元数据:
        返回元组: (event_type, details)
        event_type 可为:
          - "ALERT": 触发初次报警
          - "REPEAT_ALERT": 超过冷却时间持续故障报警
          - "RECOVERY": 故障已恢复正常
          - None: 正常稳定状态或在防抖抑制中
        """
        state = self.get_state(result.target_id)
        state.last_result = result
        now = time.time()

        if result.success:
            # 成功分支
            if state.is_alerting:
                # 原本处于故障中，现在恢复了！
                downtime_sec = int(now - (state.first_failure_time or now))
                minutes, seconds = divmod(downtime_sec, 60)
                hours, minutes = divmod(minutes, 60)
                if hours > 0:
                    duration_str = f"{hours}小时{minutes}分{seconds}秒"
                elif minutes > 0:
                    duration_str = f"{minutes}分{seconds}秒"
                else:
                    duration_str = f"{seconds}秒"

                state.is_alerting = False
                state.consecutive_failures = 0
                state.first_failure_time = None
                return "RECOVERY", {
                    "downtime_duration": duration_str,
                    "latency_ms": result.latency_ms
                }
            else:
                # 平时正常运行，重置失败计数
                state.consecutive_failures = 0
                state.first_failure_time = None
                return None, {}

        else:
            # 失败分支
            state.consecutive_failures += 1
            if state.first_failure_time is None:
                state.first_failure_time = now

            # 检查是否达到告警阈值
            if state.consecutive_failures >= self.fail_threshold:
                if not state.is_alerting:
                    # 首次触发报警
                    state.is_alerting = True
                    state.last_alert_time = now
                    return "ALERT", {
                        "consecutive_fails": state.consecutive_failures,
                        "error_message": result.error_message,
                        "latency_ms": result.latency_ms
                    }
                else:
                    # 持续处于报警中，检查冷却时间
                    if now - state.last_alert_time >= self.cooldown_seconds:
                        state.last_alert_time = now
                        return "REPEAT_ALERT", {
                            "consecutive_fails": state.consecutive_failures,
                            "error_message": result.error_message,
                            "latency_ms": result.latency_ms
                        }

            return None, {}
