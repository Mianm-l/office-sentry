# notify/dingtalk.py
import requests
import logging

logger = logging.getLogger("OfficeSentry.DingTalk")

def send_dingtalk_markdown(webhook_url: str, title: str, text: str, at_all: bool = False, timeout: int = 5) -> bool:
    """
    向钉钉群机器人发送 Markdown 消息。
    """
    if not webhook_url or not webhook_url.startswith("http"):
        logger.debug("未配置有效的钉钉 Webhook URL")
        return False

    payload = {
        "msgtype": "markdown",
        "markdown": {
            "title": title,
            "text": text
        },
        "at": {
            "isAtAll": at_all
        }
    }
    try:
        resp = requests.post(webhook_url, json=payload, timeout=timeout)
        data = resp.json()
        if data.get("errcode") == 0:
            return True
        logger.warning(f"钉钉发送失败: {data}")
        return False
    except Exception as e:
        logger.warning(f"钉钉发送异常: {e}")
        return False
