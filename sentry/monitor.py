# sentry/monitor.py
import time
import socket
import logging
import requests
import urllib3
from dataclasses import dataclass
from typing import Dict, Any, List, Optional

# 忽略开发环境可能出现的自签名证书告警
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
logger = logging.getLogger("OfficeSentry.Monitor")

@dataclass
class ProbeResult:
    target_id: str
    name: str
    target_type: str
    endpoint: str
    success: bool
    latency_ms: float
    status_code: Optional[int] = None
    error_message: str = ""

class ProbeEngine:
    """
    轻量探针核心引擎：支持 HTTP/HTTPS 接口探测与 TCP 端口连通性检查。
    """
    def __init__(self, default_timeout: float = 5.0):
        self.default_timeout = default_timeout
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "OfficeSentry/1.0 (HealthCheck; Windows)"
        })

    def probe_http(self, item: Dict[str, Any]) -> ProbeResult:
        name = item.get("name", "未命名服务")
        target_id = item.get("id", name)
        url = item.get("url", "")
        method = item.get("method", "GET").upper()
        headers = item.get("headers", {})
        timeout = item.get("timeout", self.default_timeout)
        expected_status = item.get("expected_status", [200])
        keyword = item.get("keyword", None)
        verify_ssl = item.get("verify_ssl", False)

        start_time = time.perf_counter()
        try:
            resp = self.session.request(
                method=method,
                url=url,
                headers=headers,
                timeout=timeout,
                verify=verify_ssl
            )
            latency = (time.perf_counter() - start_time) * 1000

            # 校验 HTTP 状态码
            if resp.status_code not in expected_status:
                return ProbeResult(
                    target_id=target_id,
                    name=name,
                    target_type="http",
                    endpoint=url,
                    success=False,
                    latency_ms=latency,
                    status_code=resp.status_code,
                    error_message=f"状态码异常: {resp.status_code} (期望: {expected_status})"
                )

            # 校验关键字
            if keyword and keyword not in resp.text:
                return ProbeResult(
                    target_id=target_id,
                    name=name,
                    target_type="http",
                    endpoint=url,
                    success=False,
                    latency_ms=latency,
                    status_code=resp.status_code,
                    error_message=f"返回内容缺少期望关键字: '{keyword}'"
                )

            return ProbeResult(
                target_id=target_id,
                name=name,
                target_type="http",
                endpoint=url,
                success=True,
                latency_ms=latency,
                status_code=resp.status_code
            )

        except requests.exceptions.Timeout:
            latency = (time.perf_counter() - start_time) * 1000
            return ProbeResult(
                target_id=target_id,
                name=name,
                target_type="http",
                endpoint=url,
                success=False,
                latency_ms=latency,
                error_message=f"请求超时 (> {timeout}s)"
            )
        except requests.exceptions.ConnectionError as e:
            latency = (time.perf_counter() - start_time) * 1000
            return ProbeResult(
                target_id=target_id,
                name=name,
                target_type="http",
                endpoint=url,
                success=False,
                latency_ms=latency,
                error_message=f"网络连接拒绝/无法访问 ({e.__class__.__name__})"
            )
        except Exception as e:
            latency = (time.perf_counter() - start_time) * 1000
            return ProbeResult(
                target_id=target_id,
                name=name,
                target_type="http",
                endpoint=url,
                success=False,
                latency_ms=latency,
                error_message=f"探针异常: {str(e)}"
            )

    def probe_tcp(self, item: Dict[str, Any]) -> ProbeResult:
        name = item.get("name", "TCP 服务")
        target_id = item.get("id", name)
        host = item.get("host", "127.0.0.1")
        port = item.get("port", 80)
        timeout = item.get("timeout", self.default_timeout)
        endpoint_desc = f"{host}:{port}"

        start_time = time.perf_counter()
        try:
            with socket.create_connection((host, int(port)), timeout=timeout):
                latency = (time.perf_counter() - start_time) * 1000
                return ProbeResult(
                    target_id=target_id,
                    name=name,
                    target_type="tcp",
                    endpoint=endpoint_desc,
                    success=True,
                    latency_ms=latency
                )
        except socket.timeout:
            latency = (time.perf_counter() - start_time) * 1000
            return ProbeResult(
                target_id=target_id,
                name=name,
                target_type="tcp",
                endpoint=endpoint_desc,
                success=False,
                latency_ms=latency,
                error_message=f"TCP 端口连接超时 (> {timeout}s)"
            )
        except Exception as e:
            latency = (time.perf_counter() - start_time) * 1000
            return ProbeResult(
                target_id=target_id,
                name=name,
                target_type="tcp",
                endpoint=endpoint_desc,
                success=False,
                latency_ms=latency,
                error_message=f"TCP 端口不可达: {str(e)}"
            )

    def probe(self, item: Dict[str, Any]) -> ProbeResult:
        target_type = item.get("type", "http").lower()
        if target_type == "tcp":
            return self.probe_tcp(item)
        return self.probe_http(item)
