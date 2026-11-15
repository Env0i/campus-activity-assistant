#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""设置抽屉「高级功能」组一项一行后，「展开区不变区」的整页沙箱逐格对照。

用法（仓库根）：
  python -B design/evidence/2026-11-15/adv-rows/scripts/detail_grid.py \\
      --base-ref <开工提交短哈希> [--new-ref <提交引用>]

这一批把「手机访问」「验证码识别」两节收成一项一行：标题行留在外面（标题行那一带的元素
会变，也会被删），说明/通道/配对/地址/位置/导入兜底/红条这一批收进展开区。展开区里那一
批 id 不变、内容也不该变，本脚本就是证明「展开区没被改坏」：只比 SELECTORS 里这些元素。

改之前那一方从 base-ref 用 git archive 导出整仓到临时目录再取 local/ui；不给 --new-ref
时新代码读当前工作区，给了就同样导出那一方（拿开工提交对开工提交跑一次，输出必须是不同
0 条，用来证明脚本自己没毛病）。

只比两边 index.html 里都还在的元素（ids_in() 取交集）：标题行的元素与本批删掉的元素自动
落在外面，统计里单列。展开区的元素与状态无关，所以一格都不跳过；真跑出不同就是展开区被
改坏了，要贴明细，不能放宽口径。

每格逐个元素比对七类属性：hidden、disabled、textContent、className、dataset.state、
style.width、aria-valuenow。输出总格数、实际比对格数、元素数与比对条数、不同条数；
不同大于 0 退出 1，并打印不同的格与属性明细。

网格：download.state 六档 × status 五档 × ready/available/running 各两档（240 组），
再叠 installing、busy、面板 notes 与 OcrPanel.note/error 有无、组件位置有无、下载进度
数字有无（各两档），共 7680 格。第一遍只比对每格的哈希（两枚 32 位散列拼接），有差异
的格再逐属性重画比对。只读，不改任何产品文件；输出不含主机路径。
"""
from __future__ import annotations

import argparse
import io
import json
import re
import subprocess
import tarfile
import tempfile
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[5]

# 展开区里 id 不变、内容不该变的元素（顺序即报告顺序）
SELECTORS = [
    # 手机访问：说明、错误、导入兜底、组件位置
    "#phone-feature-note", "#phone-feature-error", "#phone-component-error",
    "#phone-import-line", "#phone-missing", "#phone-size-note",
    "#phone-loc-before", "#phone-loc-before-path", "#phone-loading-error",
    "#phone-download-note",
    # 手机访问：展开区主体
    "#phone-access-detail", "#phone-off", "#phone-off-note",
    # "#phone-off-error" 是变化区：返修批把「开不起来的原因」从这条红条挪到标题行下的小字里
    # （与 #phone-probe、#ocr-note 同一类），所以不比对它，免得把「变化」当「不变」
    "#phone-channel", "#phone-chan-tailscale-card", "#phone-chan-tailscale",
    "#phone-chan-tailscale-status", "#phone-chan-tailscale-text",
    "#phone-chan-cloudflare-card", "#phone-chan-cloudflare",
    "#phone-chan-cloudflare-status", "#phone-chan-cloudflare-text",
    "#btn-tailscale-recheck", "#phone-channel-hint",
    # 手机访问：开启态（配对、地址、状态）
    "#phone-on", "#phone-ok", "#phone-cred-tip", "#phone-pair", "#phone-code",
    "#pair-code-note", "#phone-qr", "#phone-qr-empty", "#phone-pair-note",
    "#phone-address", "#btn-phone-address-copy", "#phone-address-alt-line",
    "#phone-address-alt", "#phone-channel-note", "#phone-on-error",
    "#phone-stop-confirm", "#btn-phone-stop-cancel", "#btn-phone-stop-confirm",
    "#phone-stop-row", "#btn-phone-add-pair", "#phone-loc-after",
    "#phone-loc-after-path", "#btn-phone-open-loc", "#phone-status",
    # 验证码识别：下载、导入兜底、组件位置、开关说明
    "#ocr-download-state", "#ocr-download-error", "#ocr-import-line",
    "#ocr-missing", "#ocr-size-note", "#ocr-loc-before", "#ocr-loc-before-path",
    "#ocr-off-note", "#ocr-loc-after", "#ocr-loc-after-path", "#btn-ocr-open-loc",
]

DL_STATES = ["", "downloading", "verifying", "installed", "failed", "cancelled"]
STATUSES = ["missing", "checking", "outdated", "failed", "ready"]

SNIPPET_HEAD = """
const GRID = __GRID__;
const SELECTORS = __SELECTORS__;
const RED_BARS = __RED_BARS__;
let BROKEN = false;
const NOTES_ON = { feature: "面板备注F", missing: "面板备注M", loading: "面板备注L",
  off: "面板备注O", offErr: "面板备注E", pair: "面板备注P", onErr: "面板备注N" };
const NOTES_OFF = { feature: "", missing: "", loading: "", off: "", offErr: "",
  pair: "", onErr: "" };
const LOC = { path: "P:/demo/dir", short: "…\\\\\\\\advanced\\\\\\\\demo" };
const paintCell = (c) => {
  BROKEN = String((c.row || {}).status || "") === "failed";
  const st = { running: c.running, address: "http://100.64.0.9:8765/", qr: "",
    pair_code: "", pair_code_status: null, paired_count: 0, live_session: false,
    feature: {}, preferred_channel: "", tailscale_autostart: false,
    advanced: { features: { phone_control: c.row, relogin_ocr: c.row },
      channels: { tailscale: { available: true, state: "ready", addresses: [] },
                  cloudflare: { available: false, state: "stopped" } },
      credential: { saved: false, staged: false }, phone_access: {} } };
  window.PhonePanel.state = st;
  window.PhonePanel.busy = c.busy;
  window.PhonePanel.pending = "";
  window.PhonePanel.installing = { phone_control: c.installing,
                                   relogin_ocr: c.installing };
  window.PhonePanel.notes = Object.assign({}, c.notes ? NOTES_ON : NOTES_OFF);
  window.PhonePanel.location = c.loc ? LOC : null;
  window.PhonePanel.lastDownload = "";
  window.PhonePanel.stopAsk = false;
  window.PhonePanel.addPair = false;
  window.PhonePanel.addPairAt = 0;
  window.PhonePanel.copied = false;
  window.PhonePanel.codeSync = null;
  window.PhonePanel.codeLeft = 0;
  window.PhonePanel.lastCode = "";
  window.PhonePanel.channel = "";
  window.OcrPanel.busy = c.busy;
  window.OcrPanel.note = c.notes ? "面板备注R" : "";
  window.OcrPanel.error = c.notes ? "面板备注X" : "";
  window.OcrPanel.location = c.loc ? LOC : null;
  window.OcrPanel.lastDownload = "";
  const phoneRow = Object.assign({}, st.feature, st.advanced.features.phone_control);
  window.PhonePanel.paintPhoneAccess(st, phoneRow, { saved: false, staged: false });
  paintOcrDownload();
};
const dumpEl = (el) => [el.hidden ? 1 : 0, el.disabled ? 1 : 0,
  String(el.textContent || ""),
  typeof el.className === "string" ? el.className : "",
  String((el.dataset && el.dataset.state) || ""),
  el.style && el.style.width ? String(el.style.width) : "",
  String(el.getAttribute("aria-valuenow") || "")];
// 坏档那一格的红条不再承载「组件文件不完整…」那句（那句话挪到标题行下的小字里），
// 两侧都记成同一个占位符，好让同一格上的其它元素照常比对。
const dumpOne = (sel) => (BROKEN && RED_BARS.indexOf(sel) >= 0)
  ? "-" : dumpEl(document.querySelector(sel));
const dumpCell = () => SELECTORS.map((sel) => dumpOne(sel));
const hashCell = (dump) => {
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
for (const c of GRID) { paintCell(c); out.push(hashCell(dumpCell())); }
"""

SNIPPET_DETAIL = SNIPPET_HEAD + """
const INDEXES = __INDEXES__;
for (const i of INDEXES) {
  paintCell(GRID[i]);
  const dump = {};
  for (const sel of SELECTORS) dump[sel] = dumpOne(sel);
  out.push({ index: i, cell: GRID[i], dump: dump });
}
"""

PROPS = ["hidden", "disabled", "textContent", "className", "dataset.state",
         "style.width", "aria-valuenow"]

# 坏档格上这两条红条的内容按设计变了（句子挪进小字），不参与逐属性比对
RED_BARS = ["#phone-component-error", "#ocr-download-error"]


def build_grid() -> list:
    cells = []
    for dl in DL_STATES:
        for status in STATUSES:
            for ready in (False, True):
                for available in (False, True):
                    for running in (False, True):
                        for installing in (False, True):
                            for busy in (False, True):
                                for notes in (False, True):
                                    for loc in (False, True):
                                        for big in (False, True):
                                            download = {"state": dl}
                                            if big:
                                                download["total_bytes"] = 33135040
                                                download["downloaded"] = 9961472
                                            cells.append({
                                                "row": {"download": download,
                                                        "status": status,
                                                        "ready": ready,
                                                        "available": available},
                                                "running": running,
                                                "installing": installing,
                                                "busy": busy, "notes": notes,
                                                "loc": loc})
    return cells


def ids_in(ui_dir: Path) -> set:
    """这一方 index.html 里出现的元素（#id 形式）"""
    html = (ui_dir / "index.html").read_text(encoding="utf-8")
    return {"#" + name for name in re.findall(r'id="([^"]+)"', html)}


def skip_cell(cell: dict) -> bool:
    """一格也不跳过：展开区的元素在所有格上都该一样。

    上一批（两行组件绘制）在这里跳过读状态还没结论的格，因为那几格正是那一批要改的
    样子；本批改的是标题行，展开区里这些元素的内容与状态无关，7680 格全比才叫证明。
    唯一的例外是坏档格上的两条红条：那句「组件文件不完整…」按设计挪到了标题行下的
    小字里，两侧在那里都记成占位符（见 RED_BARS），别的元素照常逐属性比。
    若真出现不同，说明展开区被改坏了，要逐格贴出明细，不能反过来放宽这里。
    """
    return False


def export_ui(ref: str) -> Path:
    """git archive 整仓导出到临时目录，返回里面的 local/ui（改之前的那份）。"""
    root = Path(tempfile.mkdtemp(prefix="adv-rows-grid-"))
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
            raise SystemExit("沙箱崩溃（ui 目录 %s）：%s"
                             % ("工作区" if ui_dir == REPO / "local" / "ui" else "导出副本",
                                res.stderr[-1500:]))
        marker = res.stdout.rfind("__RESULT__")
        if marker < 0:
            raise SystemExit("沙箱没有输出结果：%s" % res.stdout[-800:])
        return json.loads(res.stdout[marker + len("__RESULT__"):].strip() or "[]")


def compare_cells(old, new) -> tuple:
    diffs = []
    for i, (h1, h2) in enumerate(zip(old, new)):
        if h1 != h2:
            diffs.append(i)
    return diffs


def print_detail(indexes: list, grid: list, selectors: list, old_ui: Path, new_ui: Path) -> int:
    snippet = (SNIPPET_DETAIL.replace("__GRID__", json.dumps(grid, ensure_ascii=False))
               .replace("__SELECTORS__", json.dumps(selectors))
               .replace("__RED_BARS__", json.dumps(RED_BARS))
                   .replace("__RED_BARS__", json.dumps(RED_BARS))
               .replace("__INDEXES__", json.dumps(indexes)))
    old_detail = run_node(old_ui, snippet)
    new_detail = run_node(new_ui, snippet)
    shown = 0
    for old_item, new_item in zip(old_detail, new_detail):
        for sel in selectors:
            a = old_item["dump"][sel]
            b = new_item["dump"][sel]
            for k, prop in enumerate(PROPS):
                if a[k] != b[k]:
                    shown += 1
                    if shown <= 40:
                        print("  不同：格 %d %s %s.%s 旧=%r 新=%r"
                              % (old_item["index"], json.dumps(old_item["cell"],
                                                               ensure_ascii=False),
                                 sel, prop, a[k], b[k]))
    return shown


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-ref", required=True, help="开工提交短哈希（改之前的基准）")
    parser.add_argument("--new-ref", default="", help="新代码那一方的提交引用（不给读工作区）")
    args = parser.parse_args()

    # 输出重定向到文件时也按 UTF-8 写，避免中文在管道里变成乱码
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.path.insert(0, str(REPO / "local" / "tests"))
    all_cells = build_grid()
    grid = [cell for cell in all_cells if not skip_cell(cell)]
    old_ui = export_ui(args.base_ref)
    new_ui = export_ui(args.new_ref) if args.new_ref else REPO / "local" / "ui"
    old_ids, new_ids = ids_in(old_ui), ids_in(new_ui)
    selectors = [sel for sel in SELECTORS if sel in old_ids and sel in new_ids]
    excluded = [sel for sel in SELECTORS if sel not in selectors]
    try:
        snippet = (SNIPPET_HASH.replace("__GRID__", json.dumps(grid, ensure_ascii=False))
                   .replace("__SELECTORS__", json.dumps(selectors))
               .replace("__RED_BARS__", json.dumps(RED_BARS))
                   .replace("__RED_BARS__", json.dumps(RED_BARS)))
        old_hashes = run_node(old_ui, snippet)
        new_hashes = run_node(new_ui, snippet)
    finally:
        shutil.rmtree(old_ui.parent, ignore_errors=True)
        if args.new_ref:
            shutil.rmtree(new_ui.parent.parent, ignore_errors=True)

    if len(old_hashes) != len(grid) or len(new_hashes) != len(grid):
        raise SystemExit("网格没画完：旧 %d / 新 %d，应为 %d"
                         % (len(old_hashes), len(new_hashes), len(grid)))
    diffs = compare_cells(old_hashes, new_hashes)
    comparisons = len(grid) * len(selectors) * len(PROPS)
    # 快照组合（下载状态 × 组件状态 × ready/available/running）× 其余五档各两种
    print("网格大小：%d 格（%d 组 × installing/busy/notes/位置/进度数字 各两档）"
          % (len(all_cells), len(all_cells) // 32))
    print("实际比对格数：%d（展开区与状态无关，一格不跳）" % len(grid))
    print("旧代码基准：%s；新代码：%s"
          % (args.base_ref, args.new_ref if args.new_ref else "当前工作区"))
    print("两边都有的元素 %d 个 × %d 类属性：%d 条比对"
          % (len(selectors), len(PROPS), comparisons))
    print("只在一方存在、不比对的元素：%s"
          % ("/".join(excluded) if excluded else "无"))
    print("不同的条数：%d" % len(diffs))
    if diffs:
        print("不同的格（前 %d 个逐属性明细）：" % min(len(diffs), 40))
        # 明细要再画一遍：导出目录已删，这里重建一次
        old_ui = export_ui(args.base_ref)
        new_ui = export_ui(args.new_ref) if args.new_ref else REPO / "local" / "ui"
        try:
            shown = print_detail(diffs[:40], grid, selectors, old_ui, new_ui)
        finally:
            shutil.rmtree(old_ui.parent, ignore_errors=True)
            if args.new_ref:
                shutil.rmtree(new_ui.parent.parent, ignore_errors=True)
        print("属性级不同合计：%d" % shown)
    return 1 if diffs else 0


if __name__ == "__main__":
    sys.exit(main())
