# notify/feishu.py
import requests
import logging

logger = logging.getLogger("OfficeSentry.Feishu")

def send_feishu_card(webhook_url: str, title: str, content: str, level: str = "error", timeout: int = 5) -> bool:
    """
    向飞书群机器人发送富文本卡片消息。
    level: "error" (红), "warning" (橙), "success" (绿), "info" (蓝)
    """
    if not webhook_url or not webhook_url.startswith("http"):
        logger.debug("未配置有效的飞书 Webhook URL")
        return False

    template_map = {
        "error": "red",
        "warning": "orange",
        "success": "green",
        "info": "blue"
    }
    color_template = template_map.get(level, "blue")

    payload = {
        "msg_type": "interactive",
        "card": {
          "header": {
            "title": {
              "tag": "plain_text",
              "content": title
            },
            "template": color_template
          },
          "elements": [
            {
              "tag": "markdown",
              "content": content
            }
          ]
        }
    }
    try:
        resp = requests.post(webhook_url, json=payload, timeout=timeout)
        data = resp.json()
        if data.get("code") == 0 or data.get("StatusCode") == 0:
            return True
        logger.warning(f"飞书发送失败: {data}")
        return False
    except Exception as e:
        logger.warning(f"飞书发送异常: {e}")
        return False
