"""
轻量通知模块 — 零外部服务注册，开箱即用

用法:
    python scripts/notify.py "任务完成"
    python scripts/notify.py --level error "爬取失败"
    python scripts/notify.py --title "Hikvision" "699个产品已处理"

通道（按优先级自动选择）:
    1. 控制台输出（始终启用，彩色）
    2. macOS 原生通知（自动检测，无需配置）
    3. 飞书 Webhook（配置 FEISHU_WEBHOOK 环境变量后启用）

通知日志: data/notifications.log（自动归档）
"""

import os
import sys
import json
import platform
import subprocess
import time
from datetime import datetime
from pathlib import Path


NOTIFY_LOG = Path("data/notifications.log")
COLORS = {"info": "\033[94m", "success": "\033[92m", "warn": "\033[93m", "error": "\033[91m", "reset": "\033[0m"}


def _env(key: str, default: str = "") -> str:
    return os.environ.get(key, default)


def _log(level: str, title: str, message: str, extra: dict = None):
    NOTIFY_LOG.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "ts": datetime.now().isoformat(),
        "level": level,
        "title": title,
        "message": message,
    }
    if extra:
        entry.update(extra)
    with open(NOTIFY_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _color(level: str, text: str) -> str:
    c = COLORS.get(level, "")
    r = COLORS["reset"]
    return f"{c}{text}{r}"


def _mac_notify(title: str, message: str):
    """send native macOS notification using osascript"""
    if platform.system() != "Darwin":
        return False
    try:
        subprocess.run([
            "osascript", "-e",
            f'display notification "{message}" with title "{title}" sound name "Glass"'
        ], timeout=5, capture_output=True)
        return True
    except Exception:
        return False


def _feishu_send(title: str, message: str, level: str) -> bool:
    webhook = _env("FEISHU_WEBHOOK")
    if not webhook:
        return False

    level_emoji = {"info": "ℹ️", "success": "✅", "warn": "⚠️", "error": "❌"}
    emoji = level_emoji.get(level, "📢")

    try:
        import urllib.request
        payload = json.dumps({
            "msg_type": "interactive",
            "card": {
                "header": {
                    "title": {"tag": "plain_text", "content": f"{emoji} {title}"},
                    "template": "blue" if level != "error" else "red"
                },
                "elements": [
                    {"tag": "markdown", "content": message},
                    {"tag": "hr"},
                    {"tag": "note", "elements": [
                        {"tag": "plain_text", "content": f"🕐 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"}
                    ]}
                ]
            }
        }).encode("utf-8")
        req = urllib.request.Request(webhook, data=payload, headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=10)
        return True
    except Exception:
        return False


def _pushplus_send(title: str, message: str, level: str) -> bool:
    token = _env("PUSHPLUS_TOKEN")
    if not token:
        return False
    try:
        import urllib.request
        import urllib.parse
        data = urllib.parse.urlencode({"token": token, "title": title, "content": message}).encode()
        urllib.request.urlopen(f"http://www.pushplus.plus/send", data=data, timeout=10)
        return True
    except Exception:
        return False


def notify(message: str, title: str = "竞争分析", level: str = "info", extra: dict = None):
    """
    Send notification through all available channels.

    Args:
        message: notification body
        title: notification title / subject
        level: info, success, warn, error
        extra: additional key-value pairs to log
    """
    ts = datetime.now().strftime("%H:%M:%S")

    icon_map = {"info": "ℹ", "success": "✔", "warn": "⚠", "error": "✖"}

    prefix = _color(level, f"[{icon_map[level]} {ts}] {title}")

    print(f"\n{prefix}")
    for line in message.strip().split("\n"):
        print(f"  {line}")
    print()

    _log(level, title, message, extra)

    _mac_notify(title, message)

    _feishu_send(title, message, level)

    _pushplus_send(title, message, level)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="发送通知")
    parser.add_argument("message", help="通知内容")
    parser.add_argument("--title", default="竞争分析", help="通知标题")
    parser.add_argument("--level", default="info", choices=["info", "success", "warn", "error"], help="通知级别")
    parser.add_argument("--log-only", action="store_true", help="仅写日志，不推送")

    args = parser.parse_args()

    if args.log_only:
        _log(args.level, args.title, args.message)
        print(f"已写入日志: {NOTIFY_LOG}")
        return

    notify(args.message, title=args.title, level=args.level)


if __name__ == "__main__":
    main()
