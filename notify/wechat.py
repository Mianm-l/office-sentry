# notify/wechat.py
import requests
import logging

logger = logging.getLogger("OfficeSentry.WeChat")

def send_wechat_markdown(webhook_url: str, content: str, timeout: int = 5) -> bool:
    """
    向企业微信群机器人发送 Markdown 消息。
    """
    if not webhook_url or not webhook_url.startswith("http"):
        logger.debug("未配置有效的企业微信 Webhook URL")
        return False

    payload = {
        "msgtype": "markdown",
        "markdown": {
            "content": content
        }
    }
    try:
        resp = requests.post(webhook_url, json=payload, timeout=timeout)
        data = resp.json()
        if data.get("errcode") == 0:
            return True
        logger.warning(f"企业微信发送失败: {data}")
        return False
    except Exception as e:
        logger.warning(f"企业微信发送异常: {e}")
        return False
