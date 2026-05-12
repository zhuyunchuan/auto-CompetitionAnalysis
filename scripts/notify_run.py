"""
命令包装器 — 运行任意命令并自动发送完成/失败通知

用法:
    python scripts/notify_run.py -- python your_crawl_script.py
    python scripts/notify_run.py --title "Hikvision爬取" -- python collect_hikvision.py
    python scripts/notify_run.py -- bash -c "python a.py && python b.py"

特性:
    - 自动计时，显示耗时
    - 成功/失败自动通知
    - 退出码透传（方便脚本链式调用）
"""

import sys
import os
import subprocess
import time
import argparse
from pathlib import Path
from datetime import datetime


def _format_duration(seconds: float) -> str:
    if seconds < 60:
        return f"{seconds:.0f}秒"
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    if minutes < 60:
        return f"{minutes}分{secs}秒"
    hours = minutes // 60
    mins = minutes % 60
    return f"{hours}时{mins}分{secs}秒"


def main():
    parser = argparse.ArgumentParser(description="运行命令并发送通知")
    parser.add_argument("--title", default=None, help="任务名称（不填则使用命令名）")
    parser.add_argument("--no-notify", action="store_true", help="不发送通知，仅计时运行")
    parser.add_argument("cmd", nargs=argparse.REMAINDER, help="要运行的命令")

    args = parser.parse_args()

    if not args.cmd or (len(args.cmd) == 1 and args.cmd[0] == "--"):
        parser.print_help()
        sys.exit(1)

    if args.cmd[0] == "--":
        args.cmd = args.cmd[1:]

    if not args.cmd:
        parser.print_help()
        sys.exit(1)

    title = args.title or Path(args.cmd[0]).stem
    cmd_str = " ".join(args.cmd)

    print(f"\n{'='*60}")
    print(f"  🚀 任务: {title}")
    print(f"  📋 命令: {cmd_str}")
    print(f"  🕐 开始: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}\n")

    start = time.time()
    proc = subprocess.run(args.cmd)
    elapsed = time.time() - start
    duration_str = _format_duration(elapsed)

    exit_code = proc.returncode

    print(f"\n{'='*60}")

    if exit_code == 0:
        print(f"  ✅ 成功 | {title}")
    else:
        print(f"  ❌ 失败 (退出码 {exit_code}) | {title}")
    print(f"  ⏱ 耗时: {duration_str}")
    print(f"{'='*60}\n")

    if not args.no_notify:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from notify import notify

        if exit_code == 0:
            notify(
                f"命令执行成功\n\n```\n{cmd_str}\n```\n\n⏱ 耗时: {duration_str}",
                title=title,
                level="success",
                extra={"exit_code": exit_code, "duration": round(elapsed, 1)}
            )
        else:
            notify(
                f"命令执行失败\n\n```\n{cmd_str}\n```\n\n退出码: {exit_code}\n⏱ 耗时: {duration_str}",
                title=title,
                level="error",
                extra={"exit_code": exit_code, "duration": round(elapsed, 1)}
            )

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
