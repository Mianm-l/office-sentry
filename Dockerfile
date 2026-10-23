# syntax=docker/dockerfile:1
FROM python:3.11-slim

LABEL maintainer="OfficeSentry"
LABEL description="轻量级自动化巡检与办公协同哨兵 (ChatOps & Health Check)"

WORKDIR /app

# 设置环境变量，保持时区与 UTF-8 输出
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    TZ=Asia/Shanghai

# 安装系统基础依赖与时区数据
RUN apt-get update && apt-get install -y --no-install-recommends \
    tzdata \
    ca-certificates \
    && ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone \
    && rm -rf /var/lib/apt/lists/*

# 安装 Python 依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制代码
COPY . .

# 暴露 Webhook 回调与可视化配置端口
EXPOSE 9527

# 启动哨兵守护进程
CMD ["python", "main.py"]
