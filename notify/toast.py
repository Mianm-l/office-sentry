# notify/toast.py
import subprocess
import base64
import html
import logging

logger = logging.getLogger("OfficeSentry.Toast")

def send_toast(title: str, message: str, app_id: str = r"{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\WindowsPowerShell\v1.0\powershell.exe") -> bool:
    """
    通过 Windows 10/11 原生 WinRT API 弹出系统级 Toast 桌面通知。
    默认采用 PowerShell 注册的系统级 AUMID，确保无需创建开始菜单快捷方式即可可靠弹出通知横幅。
    """
    clean_title = title.replace("'", "''").replace("\r", " ").replace("\n", " ")
    clean_message = message.replace("'", "''")

    ps_script = f"""
$ProgressPreference = 'SilentlyContinue'
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
$template = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02)
$toastXml = [xml]$template.GetXml()
$toastXml.GetElementsByTagName('text')[0].AppendChild($toastXml.CreateTextNode('{clean_title}')) | Out-Null
$toastXml.GetElementsByTagName('text')[1].AppendChild($toastXml.CreateTextNode('{clean_message}')) | Out-Null

$xml = New-Object Windows.Data.Xml.Dom.XmlDocument
$xml.LoadXml($toastXml.OuterXml)
$toast = [Windows.UI.Notifications.ToastNotification]::new($xml)
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('{app_id}').Show($toast)
"""
    try:
        encoded = base64.b64encode(ps_script.encode('utf-16le')).decode('ascii')
        res = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-EncodedCommand", encoded],
            capture_output=True,
            text=True,
            timeout=5
        )
        if res.returncode == 0:
            return True
        logger.warning(f"桌面 Toast 发送失败: {res.stderr}")
        return False
    except Exception as e:
        logger.warning(f"桌面 Toast 异常: {e}")
        return False
