# -*- coding: utf-8 -*-
"""汇总宿主机与手机结果，给 README 的数字来源（计划 20261112-esm-verify 的 H12 要求「用脚本算，不手抄」）。

只读 results/ 下的 host-*、phone-* 文件；dry-run-* 不进结论，只在最后一节列出旁证。
不写任何文件。运行示例（仓库根，PowerShell 5.1 或 Git Bash 均可）：
  py -3.12 -I -X utf8 -B design/evidence/2026-11-12/esm-verify/tools/summarize.py
"""
from __future__ import annotations

import glob
import json
import os
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.join(os.path.dirname(HERE), "results")
FORMS = ["legacy", "flat", "chain", "preload-chain"]
CHANNELS = ["tailscale", "cloudflare"]


def load(path: str) -> dict:
    # 宿主机用 PowerShell 写的 JSON 带 BOM，用 utf-8-sig 同时兼容有无 BOM
    with open(path, "r", encoding="utf-8-sig") as handle:
        return json.load(handle)


def files(pattern: str) -> list[str]:
    return sorted(glob.glob(os.path.join(RESULTS, pattern)))


def fmt(value) -> str:
    return "-" if value is None else "%g" % round(value, 1)


def section_h1() -> None:
    print("## H1 产品真实加载（host-product-*）")
    for path in files("host-product-*.json"):
        d = load(path)
        rows = d.get("rows") or []
        ports = d.get("listen_ports") or []
        status = [r.get("status") for r in rows]
        head = [str(r.get("head") or "")[:15] for r in rows]
        print("  %s ports=%s status=%s head=%s stopped_ports=%s" % (
            os.path.basename(path), ports, status, head[:1], "see json"))


def section_h2_h6() -> None:
    print("## H2/H6 桌面样机（host-onefile-*, host-onedir-*，产品写法与对照）")
    for mode in ["onefile", "onedir"]:
        for dirkind in ["plain", "space", "cjk"]:
            pat = "host-%s-%s-product.json" % (mode, dirkind)
            for path in files(pat):
                d = load(path)
                s = d.get("snapshot") or {}
                print("  %-34s proto=%s ready=%s caps_ok=%s done_ms=%s" % (
                    os.path.basename(path), (s.get("location") or {}).get("protocol"),
                    s.get("ready"), (s.get("caps") or {}).get("all_caps_ok"),
                    fmt(s.get("done_ms"))))
    done = []
    ready = []
    for path in files("host-*-product.json") + files("host-onefile-plain-run*.json"):
        d = load(path)
        s = d.get("snapshot") or {}
        if s.get("done_ms") is not None:
            done.append(s["done_ms"])
        ready.append(bool(s.get("ready")))
    if done:
        print("  product 全部 done_ms: n=%d median=%s min=%s max=%s; ready=%d/%d" % (
            len(done), fmt(statistics.median(done)), fmt(min(done)), fmt(max(done)),
            sum(ready), len(ready)))
    for path in files("host-onefile-plain-run*.json"):
        s = load(path).get("snapshot") or {}
        print("  %s ready=%s done_ms=%s" % (os.path.basename(path), s.get("ready"), fmt(s.get("done_ms"))))
    for path in files("host-*-file-url-noallow.json"):
        d = load(path)
        print("  %s allow=%s default=%s proto=%s ready=%s caps=%d" % (
            os.path.basename(path), d.get("allow_file_urls"),
            d.get("allow_file_urls_is_pywebview_default"),
            ((d.get("snapshot") or {}).get("location") or {}).get("protocol"),
            (d.get("snapshot") or {}).get("ready"),
            len(((d.get("snapshot") or {}).get("caps") or {}))))


def section_h3_h9_desktop() -> None:
    print("## H3/H9 桌面 40 模块（host-*-h9-*，每形态 6 次：onefile/onedir x 三目录）")
    for form in FORMS:
        key = form if form != "preload-chain" else "preload"
        runs = files("host-*-h9-%s.json" % key)
        vals, orders, counts = [], set(), set()
        for path in runs:
            s = load(path).get("snapshot") or {}
            vals.append(s.get("done_ms"))
            orders.add(tuple(s.get("esm_order") or []))
            counts.add(s.get("esm_count"))
        valid = [v for v in vals if v is not None]
        print("  %-13s n=%d valid=%d median=%s min=%s max=%s distinct_orders=%d esm_count=%s" % (
            form, len(runs), len(valid),
            fmt(statistics.median(valid)) if valid else "-",
            fmt(min(valid)) if valid else "-", fmt(max(valid)) if valid else "-",
            len(orders), sorted(counts, key=str)))
    print("  cycle（顶层循环，预期报错）:")
    for path in files("host-*-cycle.json"):
        s = load(path).get("snapshot") or {}
        errs = [e.get("message") for e in (s.get("errors") or [])]
        print("    %s errors=%s" % (os.path.basename(path), errs[:1]))


def section_h9_phone() -> None:
    print("## H9 手机 payload.done_ms（phone-*，只统计带 form 的 H9 运行记录）")
    print("  通道        形态           有效/总次  中位数  最大值  未完成(done_ms 空)")
    generic = 0
    for channel in CHANNELS:
        for form in FORMS:
            # 通用上报在每个形态的循环里都会扫到一次，下面只在 form 为 legacy 时计数，避免重复
            total = 0
            vals = []
            nulls = 0
            for path in files("phone-%s-ios-safari-*.json" % channel):
                p = load(path).get("payload") or {}
                if p.get("page") != "h9":
                    continue
                if p.get("form") is None:
                    if form == FORMS[0]:
                        generic += 1
                    continue
                if p.get("form") != form:
                    continue
                total += 1
                if p.get("done_ms") is None:
                    nulls += 1
                else:
                    vals.append(p["done_ms"])
            if total == 0:
                print("  %-11s %-14s 0/0" % (channel, form))
                continue
            print("  %-11s %-14s %d/%d      %8s %8s %d" % (
                channel, form, len(vals), total,
                fmt(statistics.median(vals)) if vals else "-",
                fmt(max(vals)) if vals else "-", nulls))
    print("  不带 form 的 H9 页通用上报（与前面某次运行的 done_ms 重复，不计入）: %d 条" % generic)


def section_phone_pages() -> None:
    print("## H4/H8/H11 手机各页（phone-*）")
    table = {}
    for channel in CHANNELS:
        for path in files("phone-%s-ios-safari-*.json" % channel):
            p = load(path).get("payload") or {}
            page = p.get("page")
            key = (channel, page)
            table.setdefault(key, []).append(p)
    for key in sorted(table):
        items = table[key]
        if key[1] == "h2":
            ok = sum(1 for p in items if (p.get("caps") or {}).get("all_caps_ok"))
            print("  %s h2 runs=%d all_caps_ok=%d/%d" % (key[0], len(items), ok, len(items)))
        elif key[1] == "h11":
            shown = [((p.get("fallback") or {}).get("at_ms")) for p in items
                     if (p.get("fallback") or {}).get("shown")]
            print("  %s h11 runs=%d fallback_shown=%d/%d at_ms=%s" % (
                key[0], len(items), len(shown), len(items), sorted(shown)))
        else:
            print("  %s %s runs=%d" % (key[0], key[1], len(items)))


def section_h5() -> None:
    print("## H5 后端早推（host-*-product.json 与 dry-run-product.json 的 backend_push）")
    for path in files("host-*-product.json") + files("dry-run-product.json"):
        d = load(path)
        bp = d.get("backend_push") or []
        recv = [(e.get("phase"), e.get("n"), bool(e.get("received_by_page"))) for e in bp]
        gui = [e.get("duration_ms") for e in bp if e.get("phase") == "gui_start"]
        queued = len((d.get("snapshot") or {}).get("backend_queued") or [])
        replayed = (d.get("snapshot") or {}).get("backend_replayed")
        print("  %-34s received=%d/%d gui_start_ms=%s queued=%d replayed=%s" % (
            os.path.basename(path), sum(1 for r in recv if r[2]), len(recv),
            fmt(gui[0]) if gui else "-", queued, replayed))


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass
    section_h1()
    print()
    section_h2_h6()
    print()
    section_h3_h9_desktop()
    print()
    section_h9_phone()
    print()
    section_phone_pages()
    print()
    section_h5()
    return 0


if __name__ == "__main__":
    sys.exit(main())
