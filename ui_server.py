# ui_server.py
import os
import sys

# 解决 Windows GBK 终端下 Unicode/Emoji 输出编码异常
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import json
import time
import socket
import logging
import threading
import secrets
import string
import hashlib
import webbrowser
import xml.etree.ElementTree as ET
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

from notify import NotificationHub
from notify.wxcrypt import WXBizMsgCrypt
from sentry import ProbeEngine, ChatOpsEngine

logger = logging.getLogger("OfficeSentry.Server")

def get_config_path():
    """优先使用不受 git 追踪的本地私有配置 config.local.json"""
    local_cfg = os.path.join(CURRENT_DIR, "config.local.json")
    if os.path.exists(local_cfg):
        return local_cfg
    return os.path.join(CURRENT_DIR, "config.json")

CONFIG_PATH = get_config_path()
chatops_engine = ChatOpsEngine(CONFIG_PATH)

def read_config():
    cfg_file = get_config_path()
    if not os.path.exists(cfg_file):
        return {}
    with open(cfg_file, "r", encoding="utf-8") as f:
        return json.load(f)

def write_config(data):
    cfg_file = get_config_path()
    with open(cfg_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

def generate_aes_key():
    chars = string.ascii_letters + string.digits
    return ''.join(secrets.choice(chars) for _ in range(43))

HTML_CONTENT = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>OfficeSentry 办公哨兵 - 可视化与机器人中心</title>
  <style>
    :root {
      --primary: #2563eb;
      --primary-hover: #1d4ed8;
      --success: #16a34a;
      --danger: #dc2626;
      --warning: #d97706;
      --bg: #f8fafc;
      --card-bg: #ffffff;
      --text: #1e293b;
      --text-muted: #64748b;
      --border: #e2e8f0;
      --wechat: #07c160;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "PingFang SC", "Microsoft YaHei", sans-serif; }
    body { background-color: var(--bg); color: var(--text); padding-bottom: 90px; }
    .container { max-width: 980px; margin: 0 auto; padding: 24px 16px; }
    
    /* Header */
    .header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 24px; padding-bottom: 16px; border-bottom: 1px solid var(--border); }
    .header-title { display: flex; align-items: center; gap: 10px; }
    .header-title h1 { font-size: 22px; font-weight: 700; color: #0f172a; }
    .badge { font-size: 12px; padding: 3px 8px; border-radius: 9999px; background: #e0e7ff; color: #4338ca; font-weight: 600; }
    .btn { display: inline-flex; align-items: center; justify-content: center; gap: 6px; padding: 8px 16px; border-radius: 8px; font-size: 14px; font-weight: 500; cursor: pointer; border: 1px solid transparent; transition: all 0.2s; }
    .btn-primary { background: var(--primary); color: #fff; }
    .btn-primary:hover { background: var(--primary-hover); }
    .btn-secondary { background: #fff; border-color: var(--border); color: var(--text); }
    .btn-secondary:hover { background: #f1f5f9; }
    .btn-success { background: var(--success); color: #fff; }
    .btn-success:hover { background: #15803d; }
    .btn-wechat { background: var(--wechat); color: #fff; }
    .btn-wechat:hover { background: #06ad56; }
    .btn-danger { background: #fee2e2; color: var(--danger); border-color: #fecaca; }
    .btn-danger:hover { background: #fecaca; }
    .btn-sm { padding: 4px 10px; font-size: 12px; border-radius: 6px; }

    /* Nav Tabs */
    .tabs { display: flex; gap: 8px; margin-bottom: 20px; border-bottom: 2px solid var(--border); padding-bottom: 2px; }
    .tab-btn { padding: 10px 18px; font-size: 14px; font-weight: 600; color: var(--text-muted); background: none; border: none; border-bottom: 2px solid transparent; margin-bottom: -4px; cursor: pointer; border-radius: 6px 6px 0 0; }
    .tab-btn.active { color: var(--primary); border-bottom-color: var(--primary); background: #eff6ff; }

    /* Card */
    .card { background: var(--card-bg); border-radius: 12px; border: 1px solid var(--border); box-shadow: 0 1px 3px rgba(0,0,0,0.05); padding: 20px; margin-bottom: 20px; }
    .card-title { font-size: 16px; font-weight: 600; margin-bottom: 16px; display: flex; align-items: center; justify-content: space-between; }
    
    /* Form controls */
    .form-group { margin-bottom: 16px; }
    .form-group label { display: block; font-size: 13px; font-weight: 600; margin-bottom: 6px; color: #334155; }
    .form-group .hint { font-size: 12px; color: var(--text-muted); margin-top: 4px; }
    .form-control { width: 100%; padding: 9px 12px; font-size: 14px; border: 1px solid var(--border); border-radius: 8px; outline: none; transition: border-color 0.2s; }
    .form-control:focus { border-color: var(--primary); box-shadow: 0 0 0 3px rgba(37,99,235,0.1); }
    .form-row { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; }
    
    /* Toggle switch */
    .switch-wrap { display: flex; align-items: center; justify-content: space-between; padding: 12px 14px; border-radius: 8px; border: 1px solid var(--border); background: #fdfdfd; margin-bottom: 12px; }
    .switch-desc { display: flex; flex-direction: column; }
    .switch-name { font-size: 14px; font-weight: 600; }
    .switch-sub { font-size: 12px; color: var(--text-muted); }
    .switch { position: relative; display: inline-block; width: 44px; height: 24px; flex-shrink: 0; }
    .switch input { opacity: 0; width: 0; height: 0; }
    .slider { position: absolute; cursor: pointer; top: 0; left: 0; right: 0; bottom: 0; background-color: #cbd5e1; transition: .3s; border-radius: 24px; }
    .slider:before { position: absolute; content: ""; height: 18px; width: 18px; left: 3px; bottom: 3px; background-color: white; transition: .3s; border-radius: 50%; }
    input:checked + .slider { background-color: var(--primary); }
    input:checked + .slider:before { transform: translateX(20px); }

    /* Target items */
    .target-item { border: 1px solid var(--border); border-radius: 10px; padding: 16px; margin-bottom: 12px; display: flex; align-items: center; justify-content: space-between; background: #fff; transition: border-color 0.2s; }
    .target-item:hover { border-color: #94a3b8; }
    .target-info { display: flex; flex-direction: column; gap: 4px; max-width: 65%; }
    .target-title { font-size: 15px; font-weight: 600; display: flex; align-items: center; gap: 8px; }
    .target-url { font-size: 12px; color: var(--text-muted); word-break: break-all; font-family: monospace; background: #f1f5f9; padding: 2px 6px; border-radius: 4px; display: inline-block; width: fit-content; }
    .target-actions { display: flex; align-items: center; gap: 8px; }
    .probe-tag { font-size: 12px; font-weight: 600; padding: 3px 8px; border-radius: 6px; }
    .probe-ok { background: #dcfce7; color: #15803d; }
    .probe-fail { background: #fee2e2; color: #b91c1c; }

    /* Sticky Footer */
    .footer-bar { position: fixed; bottom: 0; left: 0; right: 0; height: 72px; background: rgba(255,255,255,0.92); backdrop-filter: blur(8px); border-top: 1px solid var(--border); display: flex; align-items: center; justify-content: space-between; padding: 0 32px; z-index: 100; }
    .save-tips { font-size: 13px; color: var(--text-muted); }
    
    /* Modal */
    .modal-overlay { position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.5); display: none; align-items: center; justify-content: center; z-index: 1000; }
    .modal { background: #fff; border-radius: 14px; width: 90%; max-width: 500px; padding: 24px; box-shadow: 0 20px 25px -5px rgba(0,0,0,0.2); }
    .modal-header { font-size: 17px; font-weight: 700; margin-bottom: 16px; display: flex; justify-content: space-between; align-items: center; }
    .modal-footer { display: flex; justify-content: flex-end; gap: 10px; margin-top: 20px; }
    .toast-tip { position: fixed; top: 20px; right: 20px; padding: 12px 20px; border-radius: 8px; background: #0f172a; color: #fff; font-size: 14px; z-index: 9999; display: none; box-shadow: 0 10px 15px -3px rgba(0,0,0,0.3); animation: slideIn 0.3s forwards; }
    @keyframes slideIn { from { transform: translateY(-20px); opacity: 0; } to { transform: translateY(0); opacity: 1; } }

    /* ChatOps UI */
    .chat-box { border: 1px solid var(--border); border-radius: 10px; background: #f8fafc; height: 350px; overflow-y: auto; padding: 16px; display: flex; flex-direction: column; gap: 12px; margin-bottom: 12px; }
    .chat-bubble { max-width: 80%; padding: 10px 14px; border-radius: 10px; font-size: 13px; line-height: 1.5; white-space: pre-wrap; }
    .bubble-user { align-self: flex-end; background: var(--primary); color: #fff; border-bottom-right-radius: 2px; }
    .bubble-bot { align-self: flex-start; background: #fff; border: 1px solid var(--border); color: #1e293b; border-bottom-left-radius: 2px; }
    .chip-group { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 12px; }
    .chip { font-size: 12px; background: #e2e8f0; color: #334155; padding: 4px 10px; border-radius: 9999px; cursor: pointer; transition: background 0.2s; user-select: none; }
    .chip:hover { background: #cbd5e1; }
  </style>
</head>
<body>
  <div id="toastTip" class="toast-tip">提示信息</div>

  <div class="container">
    <div class="header">
      <div class="header-title">
        <h1>🛡️ OfficeSentry 办公哨兵</h1>
        <span class="badge">配置 & 机器人中心</span>
      </div>
      <div>
        <button class="btn btn-secondary btn-sm" onclick="testNotification()">🔔 发送一次测试弹窗</button>
      </div>
    </div>

    <!-- 标签导航 -->
    <div class="tabs">
      <button class="tab-btn active" onclick="switchTab('tab-targets', this)">🎯 巡检监控清单</button>
      <button class="tab-btn" onclick="switchTab('tab-chatops', this)">🤖 机器人交互 (ChatOps)</button>
      <button class="tab-btn" onclick="switchTab('tab-notifications', this)">📢 微信/桌面/群通知</button>
      <button class="tab-btn" onclick="switchTab('tab-reminders', this)">⏰ 办公节律提醒</button>
      <button class="tab-btn" onclick="switchTab('tab-system', this)">⚙️ 巡检频率与防抖</button>
    </div>

    <!-- 选项卡 1: 监控目标清单 -->
    <div id="tab-targets" class="tab-pane">
      <div class="card">
        <div class="card-title">
          <span>监控的服务与接口</span>
          <button class="btn btn-primary btn-sm" onclick="openAddTargetModal()">➕ 添加新监控目标</button>
        </div>
        <div id="targetListContainer">
          <!-- 动态渲染目标列表 -->
        </div>
      </div>
    </div>

    <!-- 选项卡 2: 机器人交互 (ChatOps) -->
    <div id="tab-chatops" class="tab-pane" style="display:none;">
      <div class="card">
        <div class="card-title">
          <span>💬 群机器人 / 个人微信对话模拟调试</span>
          <span style="font-size:12px; font-weight:normal; color:var(--text-muted);">可以直接在下方输入指令查增改配置</span>
        </div>
        
        <div class="chip-group">
          <span class="chip" onclick="quickSend('体检')">⚡ 立即体检</span>
          <span class="chip" onclick="quickSend('查询')">📋 查询列表</span>
          <span class="chip" onclick="quickSend('帮助')">❓ 帮助菜单</span>
          <span class="chip" onclick="quickSend('添加 本地服务 http://127.0.0.1:8080')">➕ 添加测试目标</span>
          <span class="chip" onclick="quickSend('工时提醒 18:00')">⏰ 改下班提醒为18点</span>
        </div>

        <div id="chatHistory" class="chat-box">
          <div class="chat-bubble bubble-bot">你好！我是 OfficeSentry 办公哨兵 🛡️<br>无论是在当前页面、钉钉群，还是在<b>手机个人微信插件</b>里，直接发送【体检】、【查询】、【添加 服务名 网址】、【删除 服务名】等指令，我都会秒回你！</div>
        </div>

        <div style="display:flex; gap: 8px;">
          <input type="text" id="chatInput" class="form-control" placeholder="输入聊天指令，如：体检、查询、添加 致远OA http://192.168.1.100:8080" onkeydown="if(event.key==='Enter') sendChatCommand()">
          <button class="btn btn-primary" onclick="sendChatCommand()">发送</button>
        </div>
      </div>

      <!-- 机器人回调对接指南 -->
      <div class="card">
        <div class="card-title">🔗 接收消息回调对接说明</div>
        <p style="font-size:13px; color:var(--text-muted); margin-bottom: 12px;">
          想在<strong>个人微信（微信插件）或群里</strong>发送指令？支持以下通道：
        </p>

        <div style="display:grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 14px;">
          <div style="padding:14px; background:#f0fdf4; border:1px solid #bbf7d0; border-radius:8px;">
            <div style="font-weight:600; font-size:14px; margin-bottom:6px; color:#15803d;">🟢 个人微信直连 (微信插件)</div>
            <div style="font-size:12px; color:#374151; line-height:1.6;">
              1. 前往「📢 微信/桌面/群通知」选项卡配置企业微信自建应用<br>
              2. 回调地址填写：<br>
              <code style="background:#dcfce7; padding:2px 4px; border-radius:4px; display:inline-block; margin-top:2px;">http://<span class='lan-ip'>127.0.0.1</span>:9527/webhook/wecom-app</code><br>
              3. 扫码关注微信插件，在个人微信通讯录直接对话！
            </div>
          </div>

          <div style="padding:14px; background:#f8fafc; border:1px solid var(--border); border-radius:8px;">
            <div style="font-weight:600; font-size:14px; margin-bottom:6px;">📌 钉钉群机器人 (Outgoing)</div>
            <div style="font-size:12px; color:var(--text-muted); line-height:1.6;">
              1. 钉钉群设置 -> 自定义机器人 -> 勾选 <b>Outgoing</b><br>
              2. POST 地址填写：<br>
              <code style="background:#e2e8f0; padding:2px 4px; border-radius:4px; display:inline-block; margin-top:2px;">http://<span class='lan-ip'>127.0.0.1</span>:9527/webhook/dingtalk</code><br>
              3. 群里 @机器人 发送 <code>体检</code> 即可！
            </div>
          </div>

          <div style="padding:14px; background:#f8fafc; border:1px solid var(--border); border-radius:8px;">
            <div style="font-weight:600; font-size:14px; margin-bottom:6px;">🕊️ 飞书群 / 开放平台机器人</div>
            <div style="font-size:12px; color:var(--text-muted); line-height:1.6;">
              1. 飞书开放平台 -> 事件订阅 -> 请求网址：<br>
              <code style="background:#e2e8f0; padding:2px 4px; border-radius:4px; display:inline-block; margin-top:2px;">http://<span class='lan-ip'>127.0.0.1</span>:9527/webhook/feishu</code><br>
              2. 订阅 <code>im.message.receive_v1</code> 消息事件即可。
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 选项卡 3: 通知通道 -->
    <div id="tab-notifications" class="tab-pane" style="display:none;">
      
      <!-- 重点：个人手机微信直连（微信插件） -->
      <div class="card" style="border: 2px solid #86efac; background: #fcfdfc;">
        <div class="card-title" style="color: #15803d;">
          <span>🟢 个人手机微信直接收发（企业微信 · 微信插件）</span>
          <span class="badge" style="background:#dcfce7; color:#15803d;">强烈推荐</span>
        </div>
        <div class="switch-wrap">
          <div class="switch-desc">
            <span class="switch-name">启用企业微信自建应用 + 微信插件</span>
            <span class="switch-sub">个人微信通讯录直接出现【办公哨兵】，在微信里直接聊天查增改、接收报警推送</span>
          </div>
          <label class="switch">
            <input type="checkbox" id="wecom_app_enabled">
            <span class="slider"></span>
          </label>
        </div>

        <div style="margin-bottom: 16px; padding: 12px; background: #f0fdf4; border-radius: 8px; font-size: 13px; color: #166534; line-height: 1.6;">
          <b>📖 1分钟极速开通指引（免费、零门槛、永不封号）：</b><br>
          1. 浏览器打开并登录 <a href="https://work.weixin.qq.com" target="_blank" style="color:#15803d; font-weight:600;">企业微信管理后台</a>（个人几秒注册，无需企业认证）<br>
          2. 进入 <b>我的企业</b> -> 翻到最底部，复制 <b>企业ID (CorpID)</b><br>
          3. 进入 <b>应用管理</b> -> 点 <b>创建应用</b>，取名「办公哨兵」，记下 <b>AgentId</b><br>
          4. 在该应用详情页下，点击 <b>接收消息 -> 设置 API 接收</b>，将下方生成的 <b>URL / Token / EncodingAESKey</b> 对应粘贴进去保存！<br>
          5. 进入 <b>我的企业 -> 微信插件</b>，用你平时的<b>个人微信扫码关注</b>！大功告成！
        </div>

        <div class="form-row">
          <div class="form-group">
            <label>企业 ID (CorpID)</label>
            <input type="text" id="wecom_corpid" class="form-control" placeholder="如: ww1234567890abcdef">
          </div>
          <div class="form-group">
            <label>应用 AgentId</label>
            <input type="text" id="wecom_agentid" class="form-control" placeholder="如: 1000002">
          </div>
        </div>

        <div class="form-row">
          <div class="form-group">
            <label>Token (令牌)</label>
            <input type="text" id="wecom_token" class="form-control" value="OfficeSentry">
          </div>
          <div class="form-group">
            <label style="display:flex; justify-content:space-between;">
              <span>EncodingAESKey (消息加密密钥, 43位)</span>
              <a href="javascript:void(0)" onclick="generateNewAESKey()" style="color:var(--primary); font-size:12px; font-weight:normal;">🎲 随机生成一个</a>
            </label>
            <input type="text" id="wecom_aes_key" class="form-control" placeholder="点击右上方「随机生成一个」">
          </div>
        </div>

        <div class="form-group">
          <label>企微后台需要填写的 URL (接收消息服务器地址)</label>
          <input type="text" readonly class="form-control" style="background:#f1f5f9; color:#475569;" value="http://<你的公网IP或穿透域名>:9527/webhook/wecom-app">
          <div class="hint">若在公网/移动网络访问，建议通过 cpolar / ngrok 将本地 9527 端口映射为公网域名后填入企微后台。</div>
        </div>
      </div>

      <!-- 桌面通知 -->
      <div class="card">
        <div class="card-title">🖥️ Windows 电脑桌面弹窗</div>
        <div class="switch-wrap">
          <div class="switch-desc">
            <span class="switch-name">启用 Windows 右下角原生 Toast 弹窗</span>
            <span class="switch-sub">接口挂掉或日常提醒时，在电脑右下角弹出系统级通知气泡</span>
          </div>
          <label class="switch">
            <input type="checkbox" id="desktop_toast_enabled">
            <span class="slider"></span>
          </label>
        </div>
      </div>

      <!-- 企业微信群机器人 (单向群播报) -->
      <div class="card">
        <div class="card-title">
          <span>💼 企业微信群机器人 (群内单向播报)</span>
          <button class="btn btn-secondary btn-sm" onclick="testSingleChannel('wechat')">测试企微推送</button>
        </div>
        <div class="switch-wrap">
          <div class="switch-desc">
            <span class="switch-name">开启企业微信群机器人告警通知</span>
            <span class="switch-sub">服务异常或恢复时自动在企微群发送 Markdown 告警卡片</span>
          </div>
          <label class="switch">
            <input type="checkbox" id="wechat_enabled">
            <span class="slider"></span>
          </label>
        </div>
        <div class="form-group">
          <label>企业微信 Webhook 链接</label>
          <input type="text" id="wechat_webhook" class="form-control" placeholder="https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxxxxx">
        </div>
      </div>

      <!-- 飞书群机器人 -->
      <div class="card">
        <div class="card-title">
          <span>🕊️ 飞书群自定义机器人</span>
          <button class="btn btn-secondary btn-sm" onclick="testSingleChannel('feishu')">测试飞书推送</button>
        </div>
        <div class="switch-wrap">
          <div class="switch-desc">
            <span class="switch-name">开启飞书告警通知</span>
            <span class="switch-sub">使用飞书专属红/绿配色交互卡片</span>
          </div>
          <label class="switch">
            <input type="checkbox" id="feishu_enabled">
            <span class="slider"></span>
          </label>
        </div>
        <div class="form-group">
          <label>飞书 Webhook 链接</label>
          <input type="text" id="feishu_webhook" class="form-control" placeholder="https://open.feishu.cn/open-apis/bot/v2/hook/xxxxxx">
        </div>
      </div>

      <!-- 钉钉群机器人 -->
      <div class="card">
        <div class="card-title">
          <span>📌 钉钉群自定义机器人</span>
          <button class="btn btn-secondary btn-sm" onclick="testSingleChannel('dingtalk')">测试钉钉推送</button>
        </div>
        <div class="switch-wrap">
          <div class="switch-desc">
            <span class="switch-name">开启钉钉告警通知</span>
            <span class="switch-sub">发送 Markdown 格式告警消息</span>
          </div>
          <label class="switch">
            <input type="checkbox" id="dingtalk_enabled">
            <span class="slider"></span>
          </label>
        </div>
        <div class="form-group">
          <label>钉钉 Webhook 链接</label>
          <input type="text" id="dingtalk_webhook" class="form-control" placeholder="https://oapi.dingtalk.com/robot/send?access_token=xxxxxx">
        </div>
      </div>
    </div>

    <!-- 选项卡 4: 办公节律提醒 -->
    <div id="tab-reminders" class="tab-pane" style="display:none;">
      <div class="card">
        <div class="card-title">⏰ 每日下班工时/日报填报提醒</div>
        <div class="switch-wrap">
          <div class="switch-desc">
            <span class="switch-name">开启下班工时提醒</span>
            <span class="switch-sub">每天到点在桌面弹出提示，防止忘记填报明道云/OA 日报与工时</span>
          </div>
          <label class="switch">
            <input type="checkbox" id="worklog_enabled">
            <span class="slider"></span>
          </label>
        </div>
        <div class="form-row">
          <div class="form-group">
            <label>提醒时间 (24小时制)</label>
            <input type="time" id="worklog_time" class="form-control" value="17:50">
          </div>
          <div class="form-group">
            <label>提醒文案</label>
            <input type="text" id="worklog_msg" class="form-control" value="今日工作即将结束，请抽空填报工时与工作日志，避免遗漏哦！">
          </div>
        </div>
      </div>

      <div class="card">
        <div class="card-title">💧 久坐喝水与肩颈放松提醒</div>
        <div class="switch-wrap">
          <div class="switch-desc">
            <span class="switch-name">开启周期喝水/舒展提醒</span>
            <span class="switch-sub">工作时间内每隔一段时间提醒离开工位、活动身体</span>
          </div>
          <label class="switch">
            <input type="checkbox" id="health_enabled">
            <span class="slider"></span>
          </label>
        </div>
        <div class="form-row">
          <div class="form-group">
            <label>提醒间隔（分钟）</label>
            <input type="number" id="health_interval" class="form-control" value="60" min="15" max="240">
          </div>
          <div class="form-group">
            <label>生效开始小时 (默认9点)</label>
            <input type="number" id="health_start" class="form-control" value="9" min="0" max="23">
          </div>
          <div class="form-group">
            <label>生效结束小时 (默认18点)</label>
            <input type="number" id="health_end" class="form-control" value="18" min="0" max="23">
          </div>
        </div>
      </div>
    </div>

    <!-- 选项卡 5: 巡检频率与防抖 -->
    <div id="tab-system" class="tab-pane" style="display:none;">
      <div class="card">
        <div class="card-title">⚙️ 巡检防抖策略</div>
        <div class="form-row">
          <div class="form-group">
            <label>轮询检查间隔（秒）</label>
            <input type="number" id="sys_scan_interval" class="form-control" value="30" min="5" max="600">
            <div class="hint">每隔多少秒对所有目标做一次探测（推荐 30~60 秒）</div>
          </div>
          <div class="form-group">
            <label>连续失败报警阈值（次）</label>
            <input type="number" id="sys_fail_threshold" class="form-control" value="2" min="1" max="10">
            <div class="hint">连续失败达到此次数才报警，防范偶发网络毛刺（推荐 2 次）</div>
          </div>
          <div class="form-group">
            <label>报警冷却时间（分钟）</label>
            <input type="number" id="sys_cooldown" class="form-control" value="15" min="1" max="120">
            <div class="hint">故障未解决期间，每隔多少分钟才续报一次，避免刷屏</div>
          </div>
        </div>
      </div>
    </div>
  </div>

  <!-- 底部吸底保存栏 -->
  <div class="footer-bar">
    <div class="save-tips">修改后点击右侧按钮，配置立即自动保存并生效。</div>
    <div style="display:flex; gap: 12px;">
      <button class="btn btn-secondary" onclick="runSingleCheckAll()">⚡ 立即全面测速</button>
      <button class="btn btn-primary" onclick="saveConfiguration()">💾 保存所有配置</button>
    </div>
  </div>

  <!-- 添加/编辑监控目标弹窗 -->
  <div id="targetModal" class="modal-overlay">
    <div class="modal">
      <div class="modal-header">
        <span id="modalTargetTitle">添加监控目标</span>
        <button style="border:none;background:none;cursor:pointer;font-size:18px;" onclick="closeModal()">✕</button>
      </div>
      <input type="hidden" id="modal_target_id">
      <div class="form-group">
        <label>服务名称 (比如: 致远OA测试环境、网关接口)</label>
        <input type="text" id="modal_target_name" class="form-control" placeholder="输入易懂的名字">
      </div>
      <div class="form-row">
        <div class="form-group">
          <label>探测协议</label>
          <select id="modal_target_type" class="form-control" onchange="toggleTypeFields()">
            <option value="http">HTTP / HTTPS 网址</option>
            <option value="tcp">TCP 端口 (数据库/Redis)</option>
          </select>
        </div>
        <div class="form-group" id="wrap_http_method">
          <label>请求方式</label>
          <select id="modal_http_method" class="form-control">
            <option value="GET">GET</option>
            <option value="POST">POST</option>
          </select>
        </div>
      </div>
      <div class="form-group" id="wrap_http_url">
        <label>URL 地址</label>
        <input type="text" id="modal_target_url" class="form-control" placeholder="http://192.168.1.100:8080/health">
      </div>
      <div class="form-row" id="wrap_tcp_fields" style="display:none;">
        <div class="form-group">
          <label>IP / 域名</label>
          <input type="text" id="modal_tcp_host" class="form-control" placeholder="127.0.0.1">
        </div>
        <div class="form-group">
          <label>端口</label>
          <input type="number" id="modal_tcp_port" class="form-control" placeholder="3306">
        </div>
      </div>
      <div class="form-row">
        <div class="form-group">
          <label>超时时间 (秒)</label>
          <input type="number" id="modal_target_timeout" class="form-control" value="5.0" step="0.5">
        </div>
        <div class="form-group" id="wrap_http_status">
          <label>期望正常状态码</label>
          <input type="text" id="modal_target_status" class="form-control" value="200">
        </div>
      </div>
      <div class="modal-footer">
        <button class="btn btn-secondary" onclick="closeModal()">取消</button>
        <button class="btn btn-primary" onclick="confirmSaveTarget()">确认添加</button>
      </div>
    </div>
  </div>

  <script>
    let currentConfig = {};

    function showToast(msg, isError = false) {
      const t = document.getElementById("toastTip");
      t.innerText = msg;
      t.style.background = isError ? "#b91c1c" : "#0f172a";
      t.style.display = "block";
      setTimeout(() => { t.style.display = "none"; }, 3000);
    }

    function switchTab(tabId, el) {
      document.querySelectorAll(".tab-pane").forEach(p => p.style.display = "none");
      document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
      document.getElementById(tabId).style.display = "block";
      el.classList.add("active");
    }

    async function generateNewAESKey() {
      try {
        const res = await fetch("/api/gen-aes-key");
        const d = await res.json();
        if (d.key) {
          document.getElementById("wecom_aes_key").value = d.key;
          showToast("已为你随机生成43位密钥！记得保存配置");
        }
      } catch (e) {
        showToast("生成失败: " + e, true);
      }
    }

    async function loadConfig() {
      try {
        const res = await fetch("/api/config");
        currentConfig = await res.json();
        renderForm();
      } catch (e) {
        showToast("加载配置失败: " + e, true);
      }
      try {
        const ipRes = await fetch("/api/lan-ip");
        const ipData = await ipRes.json();
        if (ipData.ip) {
          document.querySelectorAll(".lan-ip").forEach(span => span.innerText = ipData.ip);
        }
      } catch (_) {}
    }

    function renderForm() {
      const notif = currentConfig.notifications || {};
      document.getElementById("desktop_toast_enabled").checked = notif.desktop_toast?.enabled ?? true;
      document.getElementById("wechat_enabled").checked = notif.wechat_work?.enabled ?? false;
      document.getElementById("wechat_webhook").value = notif.wechat_work?.webhook_url ?? "";
      document.getElementById("feishu_enabled").checked = notif.feishu?.enabled ?? false;
      document.getElementById("feishu_webhook").value = notif.feishu?.webhook_url ?? "";
      document.getElementById("dingtalk_enabled").checked = notif.dingtalk?.enabled ?? false;
      document.getElementById("dingtalk_webhook").value = notif.dingtalk?.webhook_url ?? "";

      // 企业微信微信插件设置
      const wecom = notif.wecom_app || {};
      document.getElementById("wecom_app_enabled").checked = wecom.enabled ?? false;
      document.getElementById("wecom_corpid").value = wecom.corpid ?? "";
      document.getElementById("wecom_agentid").value = wecom.agentid ?? "";
      document.getElementById("wecom_token").value = wecom.token ?? "OfficeSentry";
      document.getElementById("wecom_aes_key").value = wecom.encoding_aes_key ?? "";

      const rem = currentConfig.reminders || {};
      document.getElementById("worklog_enabled").checked = rem.worklog_reminder?.enabled ?? true;
      document.getElementById("worklog_time").value = rem.worklog_reminder?.time || "17:50";
      document.getElementById("worklog_msg").value = rem.worklog_reminder?.message || "";
      document.getElementById("health_enabled").checked = rem.health_break?.enabled ?? true;
      document.getElementById("health_interval").value = rem.health_break?.interval_minutes || 60;
      document.getElementById("health_start").value = rem.health_break?.start_hour || 9;
      document.getElementById("health_end").value = rem.health_break?.end_hour || 18;

      const sys = currentConfig.system || {};
      document.getElementById("sys_scan_interval").value = sys.scan_interval_seconds || 30;
      document.getElementById("sys_fail_threshold").value = sys.fail_threshold || 2;
      document.getElementById("sys_cooldown").value = sys.cooldown_minutes || 15;

      renderTargetsList();
    }

    function renderTargetsList() {
      const container = document.getElementById("targetListContainer");
      container.innerHTML = "";
      const targets = currentConfig.targets || [];

      if (targets.length === 0) {
        container.innerHTML = "<div style='color:#94a3b8;text-align:center;padding:24px;'>暂无监控目标，点击右上角添加</div>";
        return;
      }

      targets.forEach((t, idx) => {
        const item = document.createElement("div");
        item.className = "target-item";
        const endpoint = t.type === "tcp" ? `${t.host}:${t.port}` : t.url;
        item.innerHTML = `
          <div class="target-info">
            <div class="target-title">
              <span>${t.name}</span>
              <span class="badge" style="background:#f1f5f9;color:#475569;">${(t.type || 'http').toUpperCase()}</span>
              <span id="probe_res_${t.id}" class="probe-tag" style="display:none;"></span>
            </div>
            <div class="target-url">${endpoint}</div>
          </div>
          <div class="target-actions">
            <button class="btn btn-secondary btn-sm" onclick="probeSingleTarget('${t.id}')">⚡ 测速</button>
            <label class="switch" title="开启/停用该监控">
              <input type="checkbox" ${t.enabled !== false ? 'checked' : ''} onchange="toggleTargetStatus(${idx}, this.checked)">
              <span class="slider"></span>
            </label>
            <button class="btn btn-danger btn-sm" onclick="deleteTarget(${idx})">删除</button>
          </div>
        `;
        container.appendChild(item);
      });
    }

    function toggleTargetStatus(idx, isChecked) {
      currentConfig.targets[idx].enabled = isChecked;
    }

    function deleteTarget(idx) {
      if (confirm("确定要删除这个监控目标吗？")) {
        currentConfig.targets.splice(idx, 1);
        renderTargetsList();
      }
    }

    function toggleTypeFields() {
      const type = document.getElementById("modal_target_type").value;
      if (type === "tcp") {
        document.getElementById("wrap_http_method").style.display = "none";
        document.getElementById("wrap_http_url").style.display = "none";
        document.getElementById("wrap_http_status").style.display = "none";
        document.getElementById("wrap_tcp_fields").style.display = "grid";
      } else {
        document.getElementById("wrap_http_method").style.display = "block";
        document.getElementById("wrap_http_url").style.display = "block";
        document.getElementById("wrap_http_status").style.display = "block";
        document.getElementById("wrap_tcp_fields").style.display = "none";
      }
    }

    function openAddTargetModal() {
      document.getElementById("modalTargetTitle").innerText = "添加监控目标";
      document.getElementById("modal_target_name").value = "";
      document.getElementById("modal_target_url").value = "";
      document.getElementById("modal_tcp_host").value = "127.0.0.1";
      document.getElementById("modal_tcp_port").value = "3306";
      document.getElementById("modal_target_timeout").value = "5.0";
      document.getElementById("modal_target_status").value = "200";
      document.getElementById("modal_target_type").value = "http";
      toggleTypeFields();
      document.getElementById("targetModal").style.display = "flex";
    }

    function closeModal() {
      document.getElementById("targetModal").style.display = "none";
    }

    function confirmSaveTarget() {
      const name = document.getElementById("modal_target_name").value.trim();
      if (!name) {
        alert("请输入服务名称！");
        return;
      }
      const type = document.getElementById("modal_target_type").value;
      const timeout = parseFloat(document.getElementById("modal_target_timeout").value) || 5.0;

      const newTarget = {
        id: "target_" + Date.now(),
        name: name,
        type: type,
        timeout: timeout,
        enabled: true
      };

      if (type === "tcp") {
        newTarget.host = document.getElementById("modal_tcp_host").value.trim() || "127.0.0.1";
        newTarget.port = parseInt(document.getElementById("modal_tcp_port").value) || 80;
      } else {
        const url = document.getElementById("modal_target_url").value.trim();
        if (!url) {
          alert("请输入 URL 地址！");
          return;
        }
        newTarget.url = url;
        newTarget.method = document.getElementById("modal_http_method").value;
        const statusList = document.getElementById("modal_target_status").value.split(",").map(s => parseInt(s.trim())).filter(s => !isNaN(s));
        newTarget.expected_status = statusList.length ? statusList : [200];
      }

      currentConfig.targets = currentConfig.targets || [];
      currentConfig.targets.push(newTarget);
      renderTargetsList();
      closeModal();
      showToast("监控项已添加！记得点击底部「保存所有配置」");
    }

    async function probeSingleTarget(targetId) {
      const target = currentConfig.targets.find(t => t.id === targetId);
      if (!target) return;
      const tag = document.getElementById("probe_res_" + targetId);
      if (tag) {
        tag.style.display = "inline-block";
        tag.className = "probe-tag";
        tag.innerText = "探测中...";
        tag.style.background = "#e2e8f0";
        tag.style.color = "#475569";
      }
      try {
        const res = await fetch("/api/probe", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(target)
        });
        const data = await res.json();
        if (data.success) {
          tag.className = "probe-tag probe-ok";
          tag.innerText = `OK (${data.latency_ms.toFixed(0)}ms)`;
        } else {
          tag.className = "probe-tag probe-fail";
          tag.innerText = `异常: ${data.error_message}`;
        }
      } catch (e) {
        if (tag) {
          tag.className = "probe-tag probe-fail";
          tag.innerText = "请求失败";
        }
      }
    }

    async function runSingleCheckAll() {
      showToast("正在逐个测试所有监控目标...");
      for (const t of currentConfig.targets) {
        await probeSingleTarget(t.id);
      }
      showToast("所有目标测速完成！");
    }

    async function testNotification() {
      showToast("正在触发桌面测试通知...");
      try {
        const res = await fetch("/api/test-notify", { method: "POST" });
        const d = await res.json();
        if (d.ok) showToast("已成功弹出系统 Toast 通知！");
        else showToast("通知发送异常", true);
      } catch (e) {
        showToast("调用测试接口失败: " + e, true);
      }
    }

    async function testSingleChannel(channel) {
      showToast(`正在发送【${channel}】测试消息...`);
      collectFormData();
      try {
        const res = await fetch("/api/test-channel", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ channel: channel, config: currentConfig })
        });
        const d = await res.json();
        if (d.ok) showToast(`【${channel}】测试成功，请去群里查收！`);
        else showToast(`【${channel}】发送失败: ` + d.error, true);
      } catch (e) {
        showToast("发送异常: " + e, true);
      }
    }

    function quickSend(cmd) {
      document.getElementById("chatInput").value = cmd;
      sendChatCommand();
    }

    async function sendChatCommand() {
      const input = document.getElementById("chatInput");
      const cmd = input.value.trim();
      if (!cmd) return;
      input.value = "";

      const history = document.getElementById("chatHistory");
      const userBubble = document.createElement("div");
      userBubble.className = "chat-bubble bubble-user";
      userBubble.innerText = cmd;
      history.appendChild(userBubble);
      history.scrollTop = history.scrollHeight;

      try {
        const res = await fetch("/api/chatops", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ command: cmd })
        });
        const data = await res.json();
        const botBubble = document.createElement("div");
        botBubble.className = "chat-bubble bubble-bot";
        botBubble.innerText = data.reply;
        history.appendChild(botBubble);
        history.scrollTop = history.scrollHeight;
        await loadConfig();
      } catch (e) {
        const botBubble = document.createElement("div");
        botBubble.className = "chat-bubble bubble-bot";
        botBubble.innerText = "请求失败: " + e;
        history.appendChild(botBubble);
      }
    }

    function collectFormData() {
      currentConfig.notifications = currentConfig.notifications || {};
      currentConfig.notifications.desktop_toast = {
        enabled: document.getElementById("desktop_toast_enabled").checked
      };
      currentConfig.notifications.wechat_work = {
        enabled: document.getElementById("wechat_enabled").checked,
        webhook_url: document.getElementById("wechat_webhook").value.trim()
      };
      currentConfig.notifications.feishu = {
        enabled: document.getElementById("feishu_enabled").checked,
        webhook_url: document.getElementById("feishu_webhook").value.trim()
      };
      currentConfig.notifications.dingtalk = {
        enabled: document.getElementById("dingtalk_enabled").checked,
        webhook_url: document.getElementById("dingtalk_webhook").value.trim(),
        at_all: false
      };

      currentConfig.notifications.wecom_app = {
        enabled: document.getElementById("wecom_app_enabled").checked,
        corpid: document.getElementById("wecom_corpid").value.trim(),
        agentid: document.getElementById("wecom_agentid").value.trim(),
        token: document.getElementById("wecom_token").value.trim() || "OfficeSentry",
        encoding_aes_key: document.getElementById("wecom_aes_key").value.trim()
      };

      currentConfig.reminders = currentConfig.reminders || {};
      currentConfig.reminders.worklog_reminder = {
        enabled: document.getElementById("worklog_enabled").checked,
        time: document.getElementById("worklog_time").value,
        message: document.getElementById("worklog_msg").value
      };
      currentConfig.reminders.health_break = {
        enabled: document.getElementById("health_enabled").checked,
        interval_minutes: parseInt(document.getElementById("health_interval").value) || 60,
        start_hour: parseInt(document.getElementById("health_start").value) || 9,
        end_hour: parseInt(document.getElementById("health_end").value) || 18,
        title: "💧 喝水与舒展提醒",
        message: "连续工作已有一段时间，站起来活动下肩颈、喝杯温水远眺一下吧！"
      };

      currentConfig.system = currentConfig.system || {};
      currentConfig.system.scan_interval_seconds = parseInt(document.getElementById("sys_scan_interval").value) || 30;
      currentConfig.system.fail_threshold = parseInt(document.getElementById("sys_fail_threshold").value) || 2;
      currentConfig.system.cooldown_minutes = parseInt(document.getElementById("sys_cooldown").value) || 15;
    }

    async function saveConfiguration() {
      collectFormData();
      try {
        const res = await fetch("/api/config", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(currentConfig)
        });
        const d = await res.json();
        if (d.ok) {
          showToast("🎉 配置已全部成功保存！");
        } else {
          showToast("保存失败: " + d.error, true);
        }
      } catch (e) {
        showToast("保存异常: " + e, true);
      }
    }

    loadConfig();
    window.addEventListener('focus', loadConfig);
    document.addEventListener('visibilitychange', () => {
      if (!document.hidden) loadConfig();
    });
  </script>
</body>
</html>
"""

class ConfigServerHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def is_local_client(self) -> bool:
        """安全鉴权：判断请求是否来自于本机"""
        client_ip = self.client_address[0]
        return client_ip in ("127.0.0.1", "::1", "localhost")

    def do_GET(self):
        parsed = urlparse(self.path)
        # 🛡️ 安全隔离防线：外部穿透访问严禁查看控制台与内部配置
        if not self.is_local_client():
            if not parsed.path.startswith("/webhook/"):
                self.send_response(403)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.end_headers()
                self.wfile.write(b"403 Forbidden: Management dashboard is strictly restricted to localhost.")
                return

        if parsed.path == "/" or parsed.path == "/index.html":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(HTML_CONTENT.encode("utf-8"))
        elif parsed.path == "/api/config":
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            cfg = read_config()
            self.wfile.write(json.dumps(cfg, ensure_ascii=False).encode("utf-8"))
        elif parsed.path == "/api/lan-ip":
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps({"ip": get_local_ip()}).encode("utf-8"))
        elif parsed.path == "/api/gen-aes-key":
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps({"key": generate_aes_key()}).encode("utf-8"))

        # 企业微信自建应用 / 微信插件 URL 验证 (GET)
        elif parsed.path == "/webhook/wecom-app":
            params = parse_qs(parsed.query)
            msg_sig = params.get("msg_signature", [""])[0]
            timestamp = params.get("timestamp", [""])[0]
            nonce = params.get("nonce", [""])[0]
            echostr = params.get("echostr", [""])[0]

            cfg = read_config().get("notifications", {}).get("wecom_app", {})
            token = cfg.get("token", "OfficeSentry")
            aes_key = cfg.get("encoding_aes_key", "")
            corpid = cfg.get("corpid", "")

            if not (token and aes_key and corpid):
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b"wecom_app config incomplete in OfficeSentry config.json")
                return

            try:
                wxcrypt = WXBizMsgCrypt(token, aes_key, corpid)
                reply_echo = wxcrypt.verify_url(msg_sig, timestamp, nonce, echostr)
                self.send_response(200)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.end_headers()
                self.wfile.write(reply_echo.encode("utf-8"))
            except Exception as e:
                logger.error(f"企业微信验证 URL 失败: {e}")
                self.send_response(403)
                self.end_headers()
                self.wfile.write(str(e).encode("utf-8"))
        # 微信公众号 / 微信测试号 URL 验证 (GET)
        elif parsed.path == "/webhook/wechat-mp":
            params = parse_qs(parsed.query)
            signature = params.get("signature", [""])[0]
            timestamp = params.get("timestamp", [""])[0]
            nonce = params.get("nonce", [""])[0]
            echostr = params.get("echostr", [""])[0]
            token = "OfficeSentry"

            check_sig = hashlib.sha1("".join(sorted([token, timestamp, nonce])).encode("utf-8")).hexdigest()
            if check_sig == signature:
                self.send_response(200)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.end_headers()
                self.wfile.write(echostr.encode("utf-8"))
            else:
                self.send_response(403)
                self.end_headers()
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        parsed = urlparse(self.path)
        # 🛡️ 安全隔离防线：外部穿透访问严禁调用配置修改与控制 API
        if not self.is_local_client():
            if not parsed.path.startswith("/webhook/"):
                self.send_response(403)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.end_headers()
                self.wfile.write(b"403 Forbidden: Configuration APIs are strictly restricted to localhost.")
                return

        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode("utf-8") if content_length > 0 else "{}"
        
        # 1. 企业微信自建应用 / 微信插件 消息接收与被动回复 (POST)
        if parsed.path == "/webhook/wecom-app":
            params = parse_qs(parsed.query)
            msg_sig = params.get("msg_signature", [""])[0]
            timestamp = params.get("timestamp", [""])[0]
            nonce = params.get("nonce", [""])[0]

            cfg = read_config().get("notifications", {}).get("wecom_app", {})
            token = cfg.get("token", "OfficeSentry")
            aes_key = cfg.get("encoding_aes_key", "")
            corpid = cfg.get("corpid", "")

            try:
                wxcrypt = WXBizMsgCrypt(token, aes_key, corpid)
                xml_content = wxcrypt.decrypt_msg(body, msg_sig, timestamp, nonce)
                root = ET.fromstring(xml_content)
                from_user = root.find("FromUserName").text if root.find("FromUserName") is not None else ""
                to_user = root.find("ToUserName").text if root.find("ToUserName") is not None else ""
                content = root.find("Content").text if root.find("Content") is not None else ""
                msg_type = root.find("MsgType").text if root.find("MsgType") is not None else ""

                if msg_type == "text":
                    reply_text = chatops_engine.handle_command(content, sender_name=from_user)
                else:
                    reply_text = "收到消息，请发送文本指令（如【体检】、【查询】）"

                now_ts = str(int(time.time()))
                reply_xml = f"""<xml>
<ToUserName><![CDATA[{from_user}]]></ToUserName>
<FromUserName><![CDATA[{to_user}]]></FromUserName>
<CreateTime>{now_ts}</CreateTime>
<MsgType><![CDATA[text]]></MsgType>
<Content><![CDATA[{reply_text}]]></Content>
</xml>"""
                encrypted_reply = wxcrypt.encrypt_msg(reply_xml, nonce, now_ts)
                self.send_response(200)
                self.send_header("Content-Type", "application/xml; charset=utf-8")
                self.end_headers()
                self.wfile.write(encrypted_reply.encode("utf-8"))
            except Exception as e:
                logger.error(f"处理微信插件消息失败: {e}")
                self.send_response(500)
                self.end_headers()
            return

        try:
            req_data = json.loads(body) if body else {}
        except Exception:
            req_data = {}

        # 2. 聊天交互 API (Web 调试模拟器)
        if parsed.path == "/api/chatops":
            cmd = req_data.get("command", "")
            reply = chatops_engine.handle_command(cmd)
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps({"reply": reply}, ensure_ascii=False).encode("utf-8"))

        # 3. 钉钉群机器人 Outgoing Webhook 回调
        elif parsed.path == "/webhook/dingtalk":
            text_obj = req_data.get("text", {})
            raw_msg = text_obj.get("content", "") if isinstance(text_obj, dict) else str(text_obj)
            sender = req_data.get("senderNick", "")
            reply = chatops_engine.handle_command(raw_msg, sender_name=sender)
            
            resp_payload = {
                "msgtype": "markdown",
                "markdown": {
                    "title": "OfficeSentry 回复",
                    "text": reply
                }
            }
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps(resp_payload, ensure_ascii=False).encode("utf-8"))

        # 4. 飞书事件订阅回调
        elif parsed.path == "/webhook/feishu":
            if req_data.get("type") == "url_verification":
                challenge = req_data.get("challenge", "")
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({"challenge": challenge}).encode("utf-8"))
                return

            event = req_data.get("event", {})
            msg_obj = event.get("message", {})
            content_raw = msg_obj.get("content", "{}")
            try:
                content_json = json.loads(content_raw)
                text_cmd = content_json.get("text", "")
            except Exception:
                text_cmd = content_raw

            reply = chatops_engine.handle_command(text_cmd)
            cfg = read_config()
            feishu_url = cfg.get("notifications", {}).get("feishu", {}).get("webhook_url")
            if feishu_url:
                from notify.feishu import send_feishu_card
                send_feishu_card(feishu_url, "OfficeSentry 回复", reply, level="info")

            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps({"code": 0}).encode("utf-8"))

        # 5. 企业微信普通 Webhook 接收
        elif parsed.path == "/webhook/wechat":
            raw_msg = req_data.get("text", {}).get("content", "") if isinstance(req_data.get("text"), dict) else ""
            reply = chatops_engine.handle_command(raw_msg)
            cfg = read_config()
            wechat_url = cfg.get("notifications", {}).get("wechat_work", {}).get("webhook_url")
            if wechat_url:
                from notify.wechat import send_wechat_markdown
                send_wechat_markdown(wechat_url, reply)

            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps({"errcode": 0}).encode("utf-8"))

        elif parsed.path == "/api/config":
            try:
                write_config(req_data)
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({"ok": True}).encode("utf-8"))
            except Exception as e:
                self.send_response(500)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({"ok": False, "error": str(e)}).encode("utf-8"))

        elif parsed.path == "/api/probe":
            engine = ProbeEngine()
            result = engine.probe(req_data)
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps({
                "success": result.success,
                "latency_ms": result.latency_ms,
                "status_code": result.status_code,
                "error_message": result.error_message
            }).encode("utf-8"))

        elif parsed.path == "/api/test-notify":
            cfg = read_config()
            hub = NotificationHub(cfg)
            hub.send_reminder("OfficeSentry 办公哨兵", "这是一条测试通知：桌面 Toast 弹窗已就绪！")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps({"ok": True}).encode("utf-8"))

        elif parsed.path == "/api/test-channel":
            channel = req_data.get("channel")
            cfg = req_data.get("config", read_config())
            ok = False
            err = ""
            notif = cfg.get("notifications", {})
            if channel == "wechat":
                from notify.wechat import send_wechat_markdown
                url = notif.get("wechat_work", {}).get("webhook_url", "")
                ok = send_wechat_markdown(url, "### 🔔 [OfficeSentry] 企业微信连通性测试\n> 这是一条来自办公哨兵的测试消息，收到表示配置成功！")
                if not ok: err = "发送失败，请检查 Webhook 链接是否正确"
            elif channel == "feishu":
                from notify.feishu import send_feishu_card
                url = notif.get("feishu", {}).get("webhook_url", "")
                ok = send_feishu_card(url, "OfficeSentry 连通性测试", "这是一条来自办公哨兵的测试卡片，收到表示配置成功！", level="info")
                if not ok: err = "发送失败，请检查飞书 Webhook 链接"
            elif channel == "dingtalk":
                from notify.dingtalk import send_dingtalk_markdown
                url = notif.get("dingtalk", {}).get("webhook_url", "")
                ok = send_dingtalk_markdown(url, "OfficeSentry 测试", "### OfficeSentry 连通测试\n收到表示钉钉配置正常！")
                if not ok: err = "发送失败，请检查钉钉 Webhook 链接"
            
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps({"ok": ok, "error": err}).encode("utf-8"))

        # 6. 微信公众号 / 微信测试号 消息接收与被动回复 (POST)
        elif parsed.path == "/webhook/wechat-mp":
            try:
                root = ET.fromstring(body)
                from_user = root.find("FromUserName").text if root.find("FromUserName") is not None else ""
                to_user = root.find("ToUserName").text if root.find("ToUserName") is not None else ""
                msg_type = root.find("MsgType").text if root.find("MsgType") is not None else ""
                content = root.find("Content").text if root.find("Content") is not None else ""

                if msg_type == "text":
                    reply_text = chatops_engine.handle_command(content, sender_name=from_user)
                else:
                    reply_text = "收到消息，请发送文本指令（如【体检】、【查询】）"

                now_ts = str(int(time.time()))
                reply_xml = f"""<xml>
<ToUserName><![CDATA[{from_user}]]></ToUserName>
<FromUserName><![CDATA[{to_user}]]></FromUserName>
<CreateTime>{now_ts}</CreateTime>
<MsgType><![CDATA[text]]></MsgType>
<Content><![CDATA[{reply_text}]]></Content>
</xml>"""
                self.send_response(200)
                self.send_header("Content-Type", "application/xml; charset=utf-8")
                self.end_headers()
                self.wfile.write(reply_xml.encode("utf-8"))
            except Exception as e:
                logger.error(f"处理微信公众号测试号消息异常: {e}")
                self.send_response(500)
                self.end_headers()
            return

        else:
            self.send_response(404)
            self.end_headers()

def is_port_in_use(port=9527):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('127.0.0.1', port)) == 0

def run_server(port=9527, open_browser=True):
    local_url = f"http://127.0.0.1:{port}"
    if is_port_in_use(port):
        print(f"================================================================")
        print(f"   [i] 检测到 OfficeSentry 巡检守护/配置服务已在后台运行！")
        print(f"   网页地址: {local_url}")
        print(f"   已自动为你唤起浏览器...")
        print(f"================================================================")
        if open_browser:
            webbrowser.open(local_url)
        return

    server_address = ('0.0.0.0', port)
    httpd = HTTPServer(server_address, ConfigServerHandler)
    lan_ip = get_local_ip()
    lan_url = f"http://{lan_ip}:{port}"
    print(f"================================================================")
    print(f"   [+] OfficeSentry 傻瓜式配置后台 & 微信插件中心已启动！")
    print(f"   本机访问: {local_url}")
    print(f"   微信插件回调: {lan_url}/webhook/wecom-app")
    print(f"   微信测试号:   {lan_url}/webhook/wechat-mp")
    print(f"   钉钉回调地址: {lan_url}/webhook/dingtalk")
    print(f"================================================================")
    
    if open_browser:
        webbrowser.open(local_url)
    
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n配置后台已停止。")
        httpd.server_close()

if __name__ == "__main__":
    no_browser = "--no-browser" in sys.argv
    run_server(open_browser=not no_browser)
