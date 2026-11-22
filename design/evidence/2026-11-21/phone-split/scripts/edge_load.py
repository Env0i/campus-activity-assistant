#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""在无头 Edge 中对比 HEAD 与拆分后工作区的手机页加载、全局名与配对前后 DOM。

用法（仓库根，Python 3.12）：
  python design/evidence/2026-11-21/phone-split/scripts/edge_load.py

@author Author
"""
from __future__ import annotations

import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[5]
UI_M = REPO / "local" / "ui" / "m"
EVIDENCE_DIR = Path(__file__).resolve().parents[1]
EDGE_DIR = EVIDENCE_DIR / "edge"
OUT_MD = EVIDENCE_DIR / "edge-load.md"
PROXY_VARS = ("http_proxy", "HTTP_PROXY", "https_proxy", "HTTPS_PROXY", "all_proxy")

SERVER_RUNNER = r"""
import json, os, sys, time
from pathlib import Path

local_dir = sys.argv[1]
ui_dir = sys.argv[2]
sys.path.insert(0, local_dir)

from application.phone_service import PhoneAccessService
from domain.phone_rules import ACTION_PARAMS
from infrastructure.phone_http import PhoneHttpServer

class FakeApi:
    def check(self, request_id=""):
        return {"ok": True, "result": "valid"}
    def list_activities(self, request_id=""):
        return {"ok": True, "items": [], "request_id": request_id}

api = FakeApi()
actions = {name: (lambda _n=name, **kw: getattr(api, _n)(**kw))
           for name in ACTION_PARAMS if hasattr(api, name)}
raw_state = {
    "activities": [
        {
            "id": "a1", "name": "青年志愿者校园导览", "place": "图书馆门前",
            "sign_start": "2026-11-22 09:00:00", "sign_end": "2026-11-22 18:00:00",
            "act_start": "2026-11-23 14:00:00", "act_end": "2026-11-23 16:00:00",
            "signed": False, "cancel_allowed": True,
            "reward_state": "ready", "points": 2, "wage": 0,
        },
        {
            "id": "a2", "name": "实验室安全规范讲座", "place": "学术报告厅",
            "sign_start": "2026-11-22 14:00:00", "sign_end": "2026-11-22 20:00:00",
            "act_start": "2026-11-24 19:00:00", "act_end": "2026-11-24 21:00:00",
            "signed": False, "cancel_allowed": False,
            "reward_state": "ready", "points": 1, "wage": 0,
        },
        {
            "id": "a3", "name": "校园秋日健步行", "place": "南操场",
            "sign_start": "2026-11-20 08:00:00", "sign_end": "2026-11-23 12:00:00",
            "act_start": "2026-11-25 09:00:00", "act_end": "2026-11-25 11:30:00",
            "signed": True, "cancel_allowed": True,
            "reward_state": "ready", "points": 2, "wage": 0,
        },
    ],
    "login": {"session_present": True},
    "plan": None,
    "busy": False,
    "terms": {"accepted_version": "1"},
    "terms_ok": True,
    "business_clock": {
        "state": "ready",
        "epoch_s": 1795312800.0,
        "tick_s": 1000.0,
        "sampled_tick_s": 1000.0,
        "age_s": 0.0,
    },
    "retry_options": {"default": 120, "choices": [
        {"value": 120, "label": "2 分钟"},
        {"value": 0, "label": "直到报名截止"},
    ]},
    "retry_policy": {"retry_for_s": 120, "max_attempts": 0},
}
svc = PhoneAccessService(
    actions=actions,
    now=lambda: 1000.0,
    state_of=lambda: raw_state,
    server_factory=lambda host, port, s: PhoneHttpServer(host, port, s, ui_dir=Path(ui_dir)),
)
started = svc.start("127.0.0.1", 0)
print(json.dumps({"address": started["address"], "pair_code": started["pair_code"]}), flush=True)
try:
    sys.stdin.readline()
finally:
    svc.stop()
"""

NORMALIZE_DOM_JS = r"""
() => {
  function ser(node) {
    if (node.nodeType === 3) {
      const t = node.nodeValue.replace(/\s+/g, " ").trim();
      return t ? t : "";
    }
    if (node.nodeType !== 1) return "";
    const tag = node.tagName.toLowerCase();
    if (tag === "script") return "";
    const attrs = [];
    for (const name of node.getAttributeNames().sort()) {
      let val = node.getAttribute(name);
      if (name === "value") continue;
      if (val === null) val = "";
      attrs.push(`${name}="${val}"`);
    }
    if ("hidden" in node && node.hidden && !node.hasAttribute("hidden")) attrs.push("hidden=\"\"");
    if ("disabled" in node && node.disabled && !node.hasAttribute("disabled")) attrs.push("disabled=\"\"");
    const open = attrs.length ? `<${tag} ${attrs.join(" ")}>` : `<${tag}>`;
    if (node.id === "pair-led" && document.getElementById("pair")?.hidden) {
      return `${open}[pair-code-dots:${node.childNodes.length}]</${tag}>`;
    }
    const children = [];
    for (const c of node.childNodes) {
      const s = ser(c);
      if (s) children.push(s);
    }
    return `${open}${children.join("")}</${tag}>`;
  }
  return ser(document.body);
}
"""


def clean_env(data_dir: Path) -> dict[str, str]:
    env = dict(os.environ)
    for k in PROXY_VARS:
        env.pop(k, None)
    env["CAMPUS_DATA_DIR"] = str(data_dir)
    return env


def read_manifest() -> list[str]:
    html = (UI_M / "index.html").read_text(encoding="utf-8")
    return re.findall(r'<script\s+src="([^"]+)"\s*></script>', html)


def collect_top_level_names(scripts: list[str]) -> set[str]:
    pat = re.compile(
        r"^(?:async\s+)?function\s+([A-Za-z_$][A-Za-z0-9_$]*)"
        r"|^(?:const|let|class)\s+([A-Za-z_$][A-Za-z0-9_$]*)"
    )
    names: set[str] = set()
    for s in scripts:
        for ln in (UI_M / s).read_text(encoding="utf-8").splitlines():
            m = pat.match(ln)
            if m:
                names.add(m.group(1) or m.group(2))
    return names


def extract_head_replica() -> Path:
    tmp = Path(tempfile.mkdtemp(prefix="phone_edge_head_"))
    zpath = tmp / "head.zip"
    rep = tmp / "repo"
    subprocess.run(["git", "archive", "--format=zip", "--output", str(zpath), "HEAD"],
                   cwd=REPO, check=True, capture_output=True)
    with zipfile.ZipFile(zpath) as zf:
        zf.extractall(rep)
    zpath.unlink(missing_ok=True)
    return rep


def start_fake_server(local_dir: Path, ui_dir: Path, data_dir: Path):
    proc = subprocess.Popen(
        [sys.executable, "-B", "-c", SERVER_RUNNER, str(local_dir), str(ui_dir)],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, encoding="utf-8", env=clean_env(data_dir),
    )
    line = proc.stdout.readline().strip()
    if not line:
        err = proc.stderr.read() if proc.stderr else ""
        proc.kill()
        raise RuntimeError(f"替身手机服务启动失败：{err}")
    info = json.loads(line)
    return proc, info["address"].rstrip("/"), info["pair_code"]


def stop_fake_server(proc) -> None:
    try:
        if proc.stdin:
            proc.stdin.write("\n")
            proc.stdin.flush()
        proc.wait(timeout=5)
    except Exception:
        proc.kill()


def run_edge_session(browser, label: str, base_url: str, pair_code: str,
                     check_blank_names: set[str] | None) -> dict:
    ctx = browser.new_context(viewport={"width": 390, "height": 844})
    page = ctx.new_page()
    win_overlap: list[str] = []
    if check_blank_names is not None:
        page.goto("about:blank")
        builtin = set(page.evaluate("Object.getOwnPropertyNames(window)"))
        win_overlap = sorted(check_blank_names & builtin)

    responses: list[dict] = []
    console_errs: list[str] = []
    page_errs: list[str] = []
    req_fails: list[str] = []

    def on_resp(resp):
        path = "/" + resp.url.split("/", 3)[-1].split("?", 1)[0]
        if path.endswith(".js") or path in ("/", "/styles.css"):
            responses.append({"path": path, "status": resp.status,
                              "ctype": resp.headers.get("content-type", "")})

    page.on("response", on_resp)
    page.on("console", lambda m: console_errs.append(m.text) if m.type == "error" else None)
    page.on("pageerror", lambda exc: page_errs.append(str(exc)))
    page.on("requestfailed", lambda req: req_fails.append(f"{req.url}: {req.failure}"))

    page.goto(base_url + "/", wait_until="networkidle")
    page.wait_for_selector("#pair-code", state="visible", timeout=10000)
    before_dom = page.evaluate(NORMALIZE_DOM_JS)
    page.screenshot(path=str(EDGE_DIR / f"{label}-before.png"), full_page=True)
    (EDGE_DIR / f"{label}-before.html").write_text(before_dom + "\n", encoding="utf-8", newline="\n")

    page.fill("#pair-code", pair_code)
    page.click("#btn-pair")
    page.wait_for_selector("#app:not([hidden])", timeout=10000)
    page.wait_for_selector("#today-items .row", timeout=10000)
    after_dom = page.evaluate(NORMALIZE_DOM_JS)
    page.screenshot(path=str(EDGE_DIR / f"{label}-after.png"), full_page=True)
    (EDGE_DIR / f"{label}-after.html").write_text(after_dom + "\n", encoding="utf-8", newline="\n")

    ctx.close()
    return {
        "label": label,
        "responses": responses,
        "console_errors": console_errs,
        "page_errors": page_errs,
        "request_failures": req_fails,
        "window_overlap": win_overlap,
        "before_dom": before_dom,
        "after_dom": after_dom,
    }


def format_report(head_res: dict, work_res: dict, scripts: list[str], top_count: int) -> tuple[str, bool]:
    before_eq = head_res["before_dom"] == work_res["before_dom"]
    after_eq = head_res["after_dom"] == work_res["after_dom"]
    work_js = [r for r in work_res["responses"] if r["path"].endswith(".js")]
    js_ok = len(work_js) == len(scripts) and all(
        r["status"] == 200 and "javascript" in r["ctype"].lower() for r in work_js
    )
    clean_errs = (
        not head_res["console_errors"] and not head_res["page_errors"] and not head_res["request_failures"]
        and not work_res["console_errors"] and not work_res["page_errors"] and not work_res["request_failures"]
    )
    ok = js_ok and clean_errs and not work_res["window_overlap"] and before_eq and after_eq

    lines = [
        "# 真 Edge 加载核对（HEAD 与拆分工作区对照）",
        "",
        f"- 结论：**{'PASS' if ok else 'FAIL'}**",
        "- 浏览器：Playwright `msedge` 无头模式，视口 `390×844`，仅访问 `127.0.0.1` 随机端口替身服务（3 场固定活动、固定业务时钟）",
        f"- `about:blank` `window` 自带属性与 12 份脚本 {top_count} 个顶格声明交集：`{work_res['window_overlap']}`（{'空' if not work_res['window_overlap'] else '存在冲突'}）",
        f"- 配对前规整 `body` DOM（剔除 `<script>` 标签后）对比：**{'一致' if before_eq else '不一致'}**",
        f"- 配对后规整 `body` DOM（剔除 `<script>` 标签，并将已隐藏 `#pair` 内随随机配对码变化的 `#pair-led` 点阵归一化为点阵数后）对比：**{'一致' if after_eq else '不一致'}**",
        f"- HEAD 错误数：console={len(head_res['console_errors'])}, pageerror={len(head_res['page_errors'])}, failed={len(head_res['request_failures'])}",
        f"- 工作区错误数：console={len(work_res['console_errors'])}, pageerror={len(work_res['page_errors'])}, failed={len(work_res['request_failures'])}",
        "",
        "## 工作区静态资源请求记录",
        "",
        "| 路径 | HTTP 状态 | Content-Type |",
        "|---|---:|---|",
        *(f"| `{r['path']}` | {r['status']} | `{r['ctype']}` |" for r in work_res["responses"]),
        "",
        "## 产物位置",
        "",
        "- `edge/head-before.html`、`edge/head-before.png`、`edge/head-after.html`、`edge/head-after.png`",
        "- `edge/work-before.html`、`edge/work-before.png`、`edge/work-after.html`、`edge/work-after.png`",
    ]
    return "\n".join(lines) + "\n", ok


def main() -> int:
    from playwright.sync_api import sync_playwright

    EDGE_DIR.mkdir(parents=True, exist_ok=True)
    scripts = read_manifest()
    top_names = collect_top_level_names(scripts)
    head_rep = extract_head_replica()
    data_head = Path(tempfile.mkdtemp(prefix="phone_edge_data_head_"))
    data_work = Path(tempfile.mkdtemp(prefix="phone_edge_data_work_"))
    head_proc = work_proc = None
    try:
        head_proc, head_url, head_code = start_fake_server(
            head_rep / "local", head_rep / "local/ui/m", data_head)
        work_proc, work_url, work_code = start_fake_server(
            REPO / "local", UI_M, data_work)
        with sync_playwright() as pw:
            browser = pw.chromium.launch(channel="msedge", headless=True)
            try:
                head_res = run_edge_session(browser, "head", head_url, head_code, None)
                work_res = run_edge_session(browser, "work", work_url, work_code, top_names)
            finally:
                browser.close()
    finally:
        if head_proc is not None:
            stop_fake_server(head_proc)
        if work_proc is not None:
            stop_fake_server(work_proc)
        shutil.rmtree(head_rep.parent, ignore_errors=True)
        shutil.rmtree(data_head, ignore_errors=True)
        shutil.rmtree(data_work, ignore_errors=True)

    md, ok = format_report(head_res, work_res, scripts, len(top_names))
    OUT_MD.write_text(md, encoding="utf-8", newline="\n")
    print(md)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
