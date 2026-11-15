#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""手机连接状态改前改后的整页沙箱逐格对照。

用法（仓库根）：
  python -B design/evidence/2026-11-15/phone-link/scripts/link_grid.py \
      --base-ref <开工提交短哈希> [--new-ref <提交引用>]

改之前那份从 base-ref 用 git archive 导出整仓到临时目录再取 local/ui；不给 --new-ref
时新代码读当前工作区，给了就同样导出那一方（拿开工提交对开工提交跑一次，两类都必须
是不同 0 条，用来证明脚本自己没毛病）。

这一批把「现在连着没有」从配对与活动会话的旧规则改成读后端 link，所以每格要分两类比：

1) 配对类——设置抽屉里除 chip 以外的手机访问元素，加详情卡的配对行（#phone-pop-rows）。
   「配过对没有」不受连接状态影响，全部格上七类属性都必须逐项相同。
2) 连接类——抽屉 chip、顶栏手机标识与其文字、详情卡小 chip 与大字。只在不变区逐项比：
   没开、link 没给或 unknown、给 off（开着时退回旧规则），以及新旧恰好一致的那几种
   （waiting 且旧规则说没连、connected 且旧规则说连着）。变化区（其余格）只许这几个
   元素不同，脚本只计数并给每种 link 一格的样例。

每格七类属性：hidden、disabled、textContent、className、dataset.state、style.width、
aria-valuenow。data-link 是这一批新加的属性，不在比对范围里。只读，不改任何产品文件；
输出不含主机路径。

网格：running 两档 × paired_count 0/1 × live_session 真假 × link 六档（没有该字段、
unknown、off、waiting、connected、disconnected）× last_contact_ago_s 四档
（null、30、150、4000），共 192 格；手机组件行固定为装好已启用。
"""
from __future__ import annotations

import argparse
import io
import json
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[5]

# 配对类：设置抽屉里的手机访问元素（去掉 chip），沿用上一批的手机元素清单
PAIR_SELECTORS = [
    "#btn-phone-component-install", "#btn-phone-component-cancel",
    "#btn-phone-feature-install", "#phone-feature-note", "#phone-feature-error",
    "#phone-missing", "#phone-loading", "#phone-access-detail", "#phone-off",
    "#phone-on", "#phone-component-error", "#phone-import-line",
    "#phone-loc-before", "#phone-loc-after", "#phone-loc-before-path",
    "#phone-loc-after-path", "#btn-phone-open-loc", "#phone-prog-text",
    "#phone-prog-num", "#phone-component-progress", "#phone-prog-fill",
    "#phone-loading-error", "#phone-off-error", "#phone-off-note",
    "#btn-phone-start", "#btn-tailscale-recheck", "#phone-channel-hint",
    "#phone-chan-tailscale", "#phone-chan-tailscale-card",
    "#phone-chan-tailscale-status", "#phone-chan-tailscale-text",
    "#phone-chan-cloudflare", "#phone-chan-cloudflare-card",
    "#phone-chan-cloudflare-status", "#phone-chan-cloudflare-text", "#phone-ok",
    "#phone-cred-tip", "#phone-pair", "#phone-code", "#pair-code-note",
    "#phone-qr", "#phone-qr-empty", "#phone-address", "#phone-address-alt",
    "#phone-address-alt-line", "#btn-phone-address-copy", "#phone-channel-note",
    "#phone-on-error", "#phone-stop-confirm", "#phone-stop-row",
    "#btn-phone-stop", "#btn-phone-add-pair", "#phone-probe",
    "#btn-phone-component-retry",
    # 详情卡的配对行（配过对没有，不受连接状态影响）
    "#phone-pop-rows",
]

# 连接类：抽屉 chip、顶栏标识、详情卡小 chip 与大字
LINK_SELECTORS = [
    "#phone-feature-status", "#phone-badge", "#phone-badge-text",
    "#phone-pop-chip", "#phone-pop-chip-text", "#phone-pop-big",
]

# 没有 link 字段时，这一格按旧规则走（与改之前一模一样）
LINK_MISSING = ""
LINKS = [LINK_MISSING, "unknown", "off", "waiting", "connected", "disconnected"]
AGOS = [None, 30, 150, 4000]

SNIPPET_HEAD = """
const GRID = __GRID__;
const PAIR = __PAIR__;
const LINK = __LINK__;
const paintCell = (c) => {
  const st = { running: c.running, address: "http://100.64.0.9:8765/", qr: "",
    pair_code: "", pair_code_status: null, paired_count: c.paired_count,
    live_session: c.live_session, feature: {}, preferred_channel: "",
    tailscale_autostart: false,
    advanced: { features: { phone_control: c.row, relogin_ocr: c.row },
      channels: { tailscale: { available: true, state: "ready", addresses: [] },
                  cloudflare: { available: false, state: "stopped" } },
      credential: { saved: false, staged: false }, phone_access: {} } };
  if (c.link !== null) st.link = c.link;
  if (c.ago !== null) st.last_contact_ago_s = c.ago;
  window.PhonePanel.state = st;
  window.PhonePanel.busy = false;
  window.PhonePanel.pending = "";
  window.PhonePanel.installing = { phone_control: false, relogin_ocr: false };
  window.PhonePanel.notes = { feature: "", missing: "", loading: "", off: "",
    offErr: "", pair: "", onErr: "" };
  window.PhonePanel.location = null;
  window.PhonePanel.lastDownload = "";
  window.PhonePanel.stopAsk = false;
  window.PhonePanel.addPair = false;
  window.PhonePanel.addPairAt = 0;
  window.PhonePanel.copied = false;
  window.PhonePanel.codeSync = null;
  window.PhonePanel.codeLeft = 0;
  window.PhonePanel.lastCode = "";
  window.PhonePanel.channel = "";
  const phoneRow = Object.assign({}, st.feature, st.advanced.features.phone_control);
  window.PhonePanel.paintPhoneAccess(st, phoneRow, { saved: false, staged: false });
  S.statusCard = { kind: "phone", pinned: false };
  paintStatusCards();
};
const dumpEl = (el) => [el.hidden ? 1 : 0, el.disabled ? 1 : 0,
  String(el.textContent || ""),
  typeof el.className === "string" ? el.className : "",
  String((el.dataset && el.dataset.state) || ""),
  el.style && el.style.width ? String(el.style.width) : "",
  String(el.getAttribute("aria-valuenow") || "")];
const dumpGroup = (group) => group.map((sel) => dumpEl(document.querySelector(sel)));
const hashOf = (dump) => {
  const s = JSON.stringify(dump);
  let a = 5381;
  let b = 52711;
  for (let i = 0; i < s.length; i += 1) {
    a = ((a << 5) + a + s.charCodeAt(i)) | 0;
    b = ((b << 5) + b + s.charCodeAt(i)) | 0;
  }
  return a + ":" + b;
};
"""

SNIPPET_HASH = SNIPPET_HEAD + """
for (const c of GRID) {
  paintCell(c);
  out.push({ pair: hashOf(dumpGroup(PAIR)), link: hashOf(dumpGroup(LINK)) });
}
"""

SNIPPET_DETAIL = SNIPPET_HEAD + """
const INDEXES = __INDEXES__;
for (const i of INDEXES) {
  paintCell(GRID[i]);
  out.push({ index: i, cell: GRID[i], dump: dumpGroup(LINK) });
}
"""

PROPS = ["hidden", "disabled", "textContent", "className", "dataset.state",
         "style.width", "aria-valuenow"]


def build_grid() -> list:
    row = {"download": {"state": ""}, "status": "ready", "ready": True,
           "available": True}
    cells = []
    for running in (False, True):
        for paired in (0, 1):
            for live in (False, True):
                for link in LINKS:
                    for ago in AGOS:
                        cells.append({"running": running, "paired_count": paired,
                                      "live_session": live,
                                      "link": None if link == LINK_MISSING else link,
                                      "ago": ago, "row": row})
    return cells


def old_linked(cell: dict) -> bool:
    """改之前的两档规则：开着，且配过对或有活动会话"""
    return bool(cell["running"]) and (cell["paired_count"] > 0
                                      or bool(cell["live_session"]))


def invariant(cell: dict) -> bool:
    """连接类在这一格里新旧必须一模一样"""
    if not cell["running"]:
        return True
    link = cell["link"]
    if link in (None, "unknown", "off"):
        return True
    if link == "waiting":
        return not old_linked(cell)
    if link == "connected":
        return old_linked(cell)
    return False


def ids_in(ui_dir: Path) -> set:
    import re
    html = (ui_dir / "index.html").read_text(encoding="utf-8")
    return {"#" + name for name in re.findall(r'id="([^"]+)"', html)}


def export_ui(ref: str) -> Path:
    """git archive 整仓导出到临时目录，返回里面的 local/ui。"""
    root = Path(tempfile.mkdtemp(prefix="phone-link-grid-"))
    data = subprocess.run(["git", "archive", ref], cwd=str(REPO), check=True,
                          capture_output=True).stdout
    with tarfile.open(fileobj=io.BytesIO(data)) as tar:
        tar.extractall(root, filter="data")
    ui = root / "local" / "ui"
    if not (ui / "index.html").is_file():
        raise SystemExit("导出 %s 里没有 local/ui/index.html" % ref)
    return ui


def run_node(ui_dir: Path, snippet: str) -> list:
    node = shutil.which("node")
    if not node:
        raise SystemExit("本机没有 node，无法跑整页沙箱对照")
    with tempfile.TemporaryDirectory() as name:
        harness = Path(name) / "harness.js"
        part = Path(name) / "snippet.js"
        from fixtures.ui_harness import JS_HARNESS  # 同一套 DOM 桩与页面清单
        harness.write_text(JS_HARNESS, encoding="utf-8")
        part.write_text(snippet, encoding="utf-8")
        res = subprocess.run([node, str(harness), str(ui_dir), str(part)],
                             capture_output=True, text=True, encoding="utf-8",
                             errors="replace", timeout=300)
        if res.returncode != 0:
            raise SystemExit("沙箱崩溃（%s）：%s"
                             % ("工作区" if ui_dir == REPO / "local" / "ui" else "导出副本",
                                res.stderr[-1500:]))
        marker = res.stdout.rfind("__RESULT__")
        if marker < 0:
            raise SystemExit("沙箱没有输出结果：%s" % res.stdout[-800:])
        return json.loads(res.stdout[marker + len("__RESULT__"):].strip() or "[]")


def detail(indexes: list, grid: list, old_ui: Path, new_ui: Path) -> list:
    snippet = (SNIPPET_DETAIL.replace("__GRID__", json.dumps(grid, ensure_ascii=False))
               .replace("__PAIR__", json.dumps([]))
               .replace("__LINK__", json.dumps(LINK_SELECTORS))
               .replace("__INDEXES__", json.dumps(indexes)))
    return run_node(old_ui, snippet), run_node(new_ui, snippet)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-ref", required=True, help="开工提交短哈希（改之前的基准）")
    parser.add_argument("--new-ref", default="", help="新代码那一方的提交引用（不给读工作区）")
    args = parser.parse_args()

    sys.path.insert(0, str(REPO / "local" / "tests"))
    grid = build_grid()
    old_ui = export_ui(args.base_ref)
    new_ui = export_ui(args.new_ref) if args.new_ref else REPO / "local" / "ui"
    old_ids, new_ids = ids_in(old_ui), ids_in(new_ui)
    pair = [sel for sel in PAIR_SELECTORS if sel in old_ids and sel in new_ids]
    link = [sel for sel in LINK_SELECTORS if sel in old_ids and sel in new_ids]
    missing = [sel for sel in PAIR_SELECTORS + LINK_SELECTORS
               if sel not in old_ids or sel not in new_ids]
    try:
        snippet = (SNIPPET_HASH.replace("__GRID__", json.dumps(grid, ensure_ascii=False))
                   .replace("__PAIR__", json.dumps(pair))
                   .replace("__LINK__", json.dumps(link)))
        old_dump = run_node(old_ui, snippet)
        new_dump = run_node(new_ui, snippet)
    finally:
        shutil.rmtree(old_ui.parent, ignore_errors=True)
        if args.new_ref:
            shutil.rmtree(new_ui.parent.parent, ignore_errors=True)

    if len(old_dump) != len(grid) or len(new_dump) != len(grid):
        raise SystemExit("网格没画完：旧 %d / 新 %d，应为 %d"
                         % (len(old_dump), len(new_dump), len(grid)))

    pair_diff = [i for i in range(len(grid))
                 if old_dump[i]["pair"] != new_dump[i]["pair"]]
    keep = [i for i in range(len(grid)) if invariant(grid[i])]
    link_diff = [i for i in keep
                 if old_dump[i]["link"] != new_dump[i]["link"]]
    variant = [i for i in range(len(grid)) if not invariant(grid[i])]
    changed_link = [i for i in variant
                    if old_dump[i]["link"] != new_dump[i]["link"]]

    print("网格大小：%d 格（%d 组 × last_contact_ago_s 四档）"
          % (len(grid), len(grid) // len(AGOS)))
    print("配对类：%d 个元素 × %d 类属性 × %d 格 = %d 条比对"
          % (len(pair), len(PROPS), len(grid), len(pair) * len(PROPS) * len(grid)))
    print("配对类不同的条数：%d" % len(pair_diff))
    print("连接类：不变区 %d 格 × %d 个元素 × %d 类属性 = %d 条比对"
          % (len(keep), len(link), len(PROPS), len(keep) * len(link) * len(PROPS)))
    print("连接类不变区不同的条数：%d" % len(link_diff))
    print("变化区格数：%d，其中连接类确实变了 %d 格" % (len(variant), len(changed_link)))
    if missing:
        print("两边不全有的元素（不比对）：%s" % "/".join(missing))

    samples = []
    for value in LINKS:
        for i in changed_link:
            if (grid[i]["link"] or LINK_MISSING) == value:
                samples.append(i)
                break
    watch = list(samples)
    if 0 not in watch:
        watch.append(0)
    if watch:
        old_ui = export_ui(args.base_ref)
        new_ui = export_ui(args.new_ref) if args.new_ref else REPO / "local" / "ui"
        try:
            olds, news = detail(watch, grid, old_ui, new_ui)
        finally:
            shutil.rmtree(old_ui.parent, ignore_errors=True)
            if args.new_ref:
                shutil.rmtree(new_ui.parent.parent, ignore_errors=True)
        for old_item, new_item in zip(olds, news):
            cell = old_item["cell"]
            if old_item["index"] not in samples:
                # 体检格：详情卡只有真画出来才会有这几个字，全空说明网格画错了
                first = {sel: old_item["dump"][k] for k, sel in enumerate(LINK_SELECTORS)
                         if sel in link}
                print("首格体检（确认详情卡真的画了）：chip=%r 标识=%r 详情小 chip=%r 详情大字=%r"
                      % (first["#phone-feature-status"][2], first["#phone-badge-text"][2],
                         first["#phone-pop-chip-text"][2], first["#phone-pop-big"][2]))
                continue
            print("  样例：link=%s 秒数=%s 配过对=%s 活动会话=%s"
                  % (cell["link"] if cell["link"] is not None else "（没有该字段）",
                     cell["ago"], "是" if cell["paired_count"] else "否",
                     "是" if cell["live_session"] else "否"))
            for k, sel in enumerate(LINK_SELECTORS):
                if sel not in link:
                    continue
                before, after = old_item["dump"][k], new_item["dump"][k]
                print("    %s 旧=%s 新=%s"
                      % (sel, json.dumps(before, ensure_ascii=False),
                         json.dumps(after, ensure_ascii=False)))

    if pair_diff:
        print("配对类不同的格（前 10 个）：%s" % pair_diff[:10])
    if link_diff:
        print("不变区不同的格（前 10 个）：%s" % link_diff[:10])
    return 1 if (pair_diff or link_diff) else 0


if __name__ == "__main__":
    sys.exit(main())
