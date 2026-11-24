# -*- coding: utf-8 -*-
"""worker 控制台、JSON 配置读取、飞书通知、浏览器启动与命令行注册辅助。

从 grab.py 搬出：Playwright 延迟导入与路径/网络/日志端口都在调用时由 grab 传入，
本模块不 import grab、playwright 或任何 infrastructure 模块。

@author Author
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


def setup_console():
    """Windows 控制台默认 GBK，中文/特殊符号会抛 UnicodeEncodeError，这里强制 UTF-8。"""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def read_json(path, default=None, *, log_fn, opener=open):
    """读 JSON：文件不存在静默回 default；读取/解析失败写日志再回 default。"""
    try:
        with opener(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return default
    except Exception as exc:  # noqa: BLE001 - 读失败不抛，但不能装成「文件不存在」
        log_fn("[!] 读取 %s 失败（%s）" % (Path(path).name, type(exc).__name__))
        return default


def notify(title, lines, template="green", *, read_json_fn, config_file,
           urllib_mod, log_fn):
    """可选飞书群机器人通知：config.json 里配了 webhook 才会发。"""
    cfg = read_json_fn(config_file, {}) or {}
    hook = str(cfg.get("feishu_webhook") or "").strip()
    if not hook:
        return False
    card = {
        "config": {"wide_screen_mode": True},
        "header": {"template": template,
                   "title": {"tag": "plain_text", "content": title}},
        "elements": [{"tag": "div", "text": {"tag": "lark_md",
                                             "content": "\n".join(lines)}}],
    }
    body = json.dumps({"msg_type": "interactive", "card": card},
                      ensure_ascii=False).encode("utf-8")
    req = urllib_mod.request.Request(hook, data=body,
                                     headers={"Content-Type": "application/json"})
    try:
        with urllib_mod.request.urlopen(req, timeout=10) as resp:
            payload = json.loads(resp.read().decode("utf-8", "replace"))
        ok = payload.get("code") == 0 or payload.get("StatusCode") == 0
        log_fn("[i] 飞书通知%s" % ("已发送" if ok else "失败：%s" % str(payload)[:80]))
        return ok
    except Exception as exc:
        log_fn("[i] 飞书通知失败：%s" % type(exc).__name__)
        return False


def launch_browser(pw, headless):
    """按「Chrome → Edge → 自带内核」的顺序找浏览器。"""
    for channel in ("chrome", "msedge"):
        try:
            return pw.chromium.launch(channel=channel, headless=headless)
        except Exception:
            continue
    try:
        return pw.chromium.launch(headless=headless)
    except Exception as exc:
        raise RuntimeError(
            "没找到可用的浏览器：请先装 Chrome 或 Edge，"
            "或执行 python -m playwright install chromium 下载自带内核。") from exc


def new_context(browser, with_state=True, *, state_file):
    kwargs = {"locale": "zh-CN", "viewport": {"width": 1366, "height": 900}}
    if with_state and state_file.exists():
        kwargs["storage_state"] = str(state_file)
    return browser.new_context(**kwargs)


def run_selftest(args, *, sync_playwright, launch_browser_fn, new_context_fn, base):
    """selftest 子命令：拉起浏览器并打开站点首页做基本自检。"""
    print("[i] 自检：拉起浏览器并打开站点首页 ...")
    with sync_playwright() as pw:
        browser = launch_browser_fn(pw, headless=True)
        try:
            ctx = new_context_fn(browser, with_state=False)
            page = ctx.new_page()
            page.goto(base + "/stu/", wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(1500)
            title = page.title()
            body = page.inner_text("body")[:120].replace("\n", " ")
            print("[OK] 打开成功：title=%s" % title)
            print("[i] 页面片段：%s" % body)
            if "学生" not in body and "校园助手" not in title:
                print("[!] 页面内容看起来不对，可能被网络/代理拦截。")
                return 2
            return 0
        except Exception as exc:
            print("[X] 自检失败：%s" % type(exc).__name__)
            print("    请确认已安装：pip install playwright && playwright install chromium")
            return 2
        finally:
            browser.close()


def add_grab_parser(sub, cmd_grab_fn):
    """注册 grab 子命令参数。"""
    p = sub.add_parser("grab", help="到点自动报名（不传 --pick/--name/--activity-id 则交互选择）")
    p.add_argument("--pick", type=int, default=0, metavar="N",
                   help="按 list 里的序号直接选（与交互列表顺序一致）")
    p.add_argument("--name", default="",
                   help="活动名关键词，或配合 --activity-id 作为通知里的名字")
    p.add_argument("--activity-id", default="", help="活动 id（一般不用手抄，用 --pick 即可）")
    p.add_argument("--at", default="", help="报名开始时间；不给则自动从活动列表读取")
    p.add_argument("--lead", type=float, default=100, help="提前多少秒打开页面，默认 100")
    p.add_argument("--window", type=float, default=120, help="开放后重试窗口秒数，默认 120（--retry-for 缺省时沿用）")
    p.add_argument("--sign-end", default="", help="报名截止时间；是自动重试的绝对硬上限")
    p.add_argument("--retry-for", type=float, default=None,
                   help="重试持续秒数，默认沿用 --window；0 表示持续到 --sign-end（缺截止则回退 120 秒）")
    p.add_argument("--max-attempts", type=int, default=0,
                   help="最大提交次数，只数真正点 signUp 的次数；0 表示不限")
    p.add_argument("--relogin-wait", type=float, default=0,
                   help="内部：登录失效后等图形界面自动登录的秒数（决策 015）；0 表示不等，直接按登录失效结束")
    p.add_argument("--retry-start", type=float, default=0,
                   help="内部：计划接纳时固定的重试起点（epoch 秒），由图形界面传入；"
                        "CLI 独跑留空则用本进程入口时刻")
    p.add_argument("--headed", action="store_true", help="显示浏览器窗口（默认后台运行）")
    p.add_argument("--dry-run", action="store_true", help="只检查页面/按钮，不提交")
    p.set_defaults(func=cmd_grab_fn)
