#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""手机页移动前事实清点（只读）：DOM 五组、字段读写、组间调用、PhoneModel 用途与加载现状。

用法（仓库根，Python 3.12）：
  python design/evidence/2026-11-22/phone-net/scripts/move_facts.py
  python design/evidence/2026-11-22/phone-net/scripts/move_facts.py --check

@author Author
"""
from __future__ import annotations

import argparse
import ast
import json
import re
import shutil
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[5]
APP_JS = REPO / "local" / "ui" / "m" / "app.js"
INDEX_HTML = REPO / "local" / "ui" / "m" / "index.html"
PHONE_HTTP = REPO / "local" / "infrastructure" / "phone_http.py"
TEST_PHONE_UI = REPO / "local" / "tests" / "test_phone_ui.py"
JSSCAN_MJS = REPO / "tools" / "code_shape" / "jsscan.mjs"
JSLEX_MJS = REPO / "tools" / "code_shape" / "jslex.mjs"
OUT_MD = Path(__file__).resolve().parents[1] / "move-facts.md"

GROUPS = (
    ("请求与配对会话", (
        "readCookie", "api", "postAction", "renderPair", "setPairError", "beginPairLock",
        "schedulePairTick", "stopPairLock", "applyPairFailure", "pair", "poll",
        "onPollFail", "onNeedPair", "onForbidden", "schedule", "probeExistingSession",
    )),
    ("摄入与渲染", (
        "setBanner", "clearStaleBanner", "syncOffline", "renderAlerts", "canWrite",
        "refreshControls", "renderBar", "buildRow", "buildWhy", "goSigned", "renderItems",
        "renderRail", "renderBoard", "renderStats", "toggleSearch", "renderPlan",
        "renderTasks", "addLog", "scheduleTick", "tickClock", "tickBoardLed",
        "tickRowLeft", "ingest",
    )),
    ("外壳与接线", (
        "sheetBusy", "openSheet", "closeSheet", "showSheetError", "askConfirm",
        "onConfirmYes", "wire",
    )),
    ("计划操作", (
        "startPlan", "reconcile", "cancelPendingStart", "stopPlan", "showComputerWindow",
        "cancelTask", "reselectFailed", "finishPlanView", "saveRetry", "fillRetryOptions",
        "renderReview", "removeFromReview", "openReview",
    )),
    ("重新登录", (
        "renderRelogin", "openRelogin", "endReloginControls", "ingestRelogin",
        "beginRelogin", "submitRelogin", "cancelRelogin", "refreshRelogin",
    )),
)

FUNC_GROUP = {fn: grp for grp, fns in GROUPS for fn in fns}

NODE_SCAN_SCRIPT = r"""
import { readFileSync } from "node:fs";
import { pathToFileURL } from "node:url";
const [appPath, jsscanPath, jslexPath] = process.argv.slice(2);
const { findFunctions } = await import(pathToFileURL(jsscanPath).href);
const { braceDepths } = await import(pathToFileURL(jslexPath).href);
const src = readFileSync(appPath, "utf8");
const { tokens, funcs, balanced } = findFunctions(src);
const depths = braceDepths(tokens);
const ASSIGN = new Set(["=", "+=", "-=", "*=", "/=", "%=", "**=", "<<=",
  ">>=", ">>>=", "&=", "|=", "^=", "&&=", "||=", "??="]);
const MUTATE = new Set(["add", "delete", "clear", "push", "pop", "shift",
  "unshift", "splice", "sort", "reverse", "set"]);

let domStartLine = 0;
for (let k = 0; k < tokens.length - 4; k++) {
  if (tokens[k].value === "if" && tokens[k+2].value === "typeof"
      && tokens[k+3].value === "document") {
    domStartLine = tokens[k].line;
    break;
  }
}

const pmMethods = new Map();
for (const f of funcs) {
  if (f.depth === 0 && f.start < domStartLine) pmMethods.set(f.startTok, f);
}
const phoneModel = [];
for (let k = 0; k < tokens.length; k++) {
  const t = tokens[k];
  if (t.line >= domStartLine || depths[k] !== 1 || t.type !== "id") continue;
  const f = pmMethods.get(k) || (tokens[k-1]?.value === "async" && pmMethods.get(k-1));
  if (f) {
    phoneModel.push({ name: f.name, kind: "method", start: f.start, end: f.end, lines: f.lines });
    k = f.bodyClose;
  } else if (tokens[k+1]?.value === ":") {
    let end = t.line, j = k + 2;
    while (j < tokens.length && depths[j] >= 1 && !(depths[j] === 1 && tokens[j].value === ",")) {
      end = tokens[j].line;
      j += 1;
    }
    phoneModel.push({ name: t.value, kind: "prop", start: t.line, end, lines: end - t.line + 1 });
    k = j;
  }
}

const modelDecl = {};
let inModel = false, modelTok = -1;
for (let k = 0; k < tokens.length; k++) {
  const t = tokens[k];
  if (t.line > domStartLine && depths[k] === 1 && t.value === "const" && tokens[k+1]?.value === "model") {
    inModel = true; modelTok = k; continue;
  }
  if (inModel && depths[k] === 2 && t.type === "id" && tokens[k+1]?.value === ":") {
    modelDecl[t.value] = t.line;
  }
  if (inModel && k > modelTok + 3 && depths[k] <= 1 && t.value === "}") { inModel = false; }
}

const phoneUiExports = new Set();
for (let k = 0; k < tokens.length - 5; k++) {
  if (tokens[k].line > domStartLine && tokens[k].value === "globalThis"
      && tokens[k+1].value === "." && tokens[k+2].value === "PhoneUI"
      && tokens[k+3].value === "=" && tokens[k+4].value === "{") {
    const close = tokens[k+4].match;
    for (let j = k + 5; j < close; j++) {
      if (tokens[j].type === "id" && tokens[j].line >= tokens[k+4].line) {
        const prev = tokens[j-1]?.value;
        if (prev === "{" || prev === ",") phoneUiExports.add(tokens[j].value);
      }
    }
  }
}

const domFuncs = funcs.filter(f => f.depth === 0 && f.start >= domStartLine);
const domSet = new Set(domFuncs.map(f => f.name));
const ungrouped = [];
for (let k = 0; k < tokens.length; k++) {
  const t = tokens[k];
  if (t.line <= domStartLine || depths[k] !== 1) continue;
  if (t.type === "id" && ["const", "let", "var"].includes(t.value) && tokens[k+1]?.type === "id") {
    ungrouped.push({ name: tokens[k+1].value, kind: t.value, line: t.line });
  }
}

const domRows = domFuncs.map((f) => {
  const reads = {}, writes = {}, calls = {}, pmUses = {};
  for (let k = f.bodyOpen + 1; k < f.bodyClose; k++) {
    const t = tokens[k];
    const prev = tokens[k-1]?.value;
    if (t.type === "id" && t.value === "model" && tokens[k+1]?.value === "."
        && tokens[k+2]?.type === "id" && prev !== "." && prev !== "?.") {
      const field = tokens[k+2].value;
      let j = k + 2;
      while (tokens[j+1]?.value === "." && tokens[j+2]?.type === "id") j += 2;
      const nxt = tokens[j+1]?.value;
      const isWrite = prev === "++" || prev === "--" || nxt === "++" || nxt === "--"
        || ASSIGN.has(nxt) || (j > k + 2 && MUTATE.has(tokens[j].value) && nxt === "(");
      const bag = isWrite ? writes : reads;
      bag[field] = (bag[field] || 0) + 1;
    } else if (t.type === "id" && domSet.has(t.value) && tokens[k+1]?.value === "("
               && prev !== "." && prev !== "?." && prev !== "function" && t.value !== f.name) {
      calls[t.value] = (calls[t.value] || 0) + 1;
    } else if (t.type === "id" && t.value === "PhoneModel" && tokens[k+1]?.value === "."
               && tokens[k+2]?.type === "id" && prev !== "." && prev !== "?.") {
      const m = tokens[k+2].value;
      pmUses[m] = (pmUses[m] || 0) + 1;
    }
  }
  return {
    name: f.name, start: f.start, end: f.end, lines: f.lines,
    reads, writes, calls, pmUses, inPhoneUI: phoneUiExports.has(f.name),
  };
});

process.stdout.write(JSON.stringify({
  balanced, phoneModel, modelDecl, domRows, ungrouped,
  phoneUiExports: Array.from(phoneUiExports),
}));
"""


def run_node_scan() -> dict:
    node = shutil.which("node")
    if not node:
        raise RuntimeError("node 不可用")
    proc = subprocess.run(
        [node, "--input-type=module", "-", str(APP_JS), str(JSSCAN_MJS), str(JSLEX_MJS)],
        input=NODE_SCAN_SCRIPT, text=True, capture_output=True, encoding="utf-8", check=True,
    )
    return json.loads(proc.stdout)


def scan_test_calls(dom_names: list[str], pm_names: list[str]) -> tuple[Counter, Counter]:
    src = TEST_PHONE_UI.read_text(encoding="utf-8")
    ui_calls: Counter[str] = Counter()
    for m in re.finditer(r"(?:globalThis\.)?(?:PhoneUI|ui)\.([A-Za-z_$][\w$]*)\s*\(", src):
        if m.group(1) in dom_names:
            ui_calls[m.group(1)] += 1
    pm_hits: Counter[str] = Counter()
    pm_set = set(pm_names)
    for m in re.finditer(r"\bPhoneModel\.([A-Za-z_$][\w$]*)\b", src):
        if m.group(1) in pm_set:
            pm_hits[m.group(1)] += 1
    return ui_calls, pm_hits


def parse_page_loading() -> tuple[list[str], list[tuple[str, str, str]]]:
    html = INDEX_HTML.read_text(encoding="utf-8")
    scripts = re.findall(r"<script\b[^>]*>.*?</script>", html, flags=re.S | re.I)
    tree = ast.parse(PHONE_HTTP.read_text(encoding="utf-8"))
    static_rows = []
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "PHONE_STATIC" for t in node.targets
        ):
            for route, (fname, ctype) in ast.literal_eval(node.value).items():
                static_rows.append((str(route), str(fname), str(ctype)))
    return scripts, static_rows


def fmt_counts(counter: dict[str, int]) -> str:
    if not counter:
        return "—"
    return "、".join(f"`{k}`({counter[k]})" if counter[k] > 1 else f"`{k}`" for k in sorted(counter))


def build_facts() -> dict:
    data = run_node_scan()
    if not data["balanced"]:
        raise RuntimeError("app.js 括号未配平")
    rows = data["domRows"]
    by_name = {r["name"]: r for r in rows}
    called_by: dict[str, Counter[str]] = defaultdict(Counter)
    for r in rows:
        for callee, cnt in r["calls"].items():
            called_by[callee][r["name"]] += cnt
    ui_calls, pm_hits = scan_test_calls(list(by_name), [m["name"] for m in data["phoneModel"]])
    scripts, static_rows = parse_page_loading()
    return {
        "data": data, "rows": rows, "by_name": by_name,
        "missing": [fn for fn in FUNC_GROUP if fn not in by_name],
        "extra_funcs": [r["name"] for r in rows if r["name"] not in FUNC_GROUP],
        "called_by": called_by, "ui_calls": ui_calls, "pm_hits": pm_hits,
        "scripts": scripts, "static_rows": static_rows,
    }


def build_field_stats(rows: list[dict], model_decl: dict[str, int]) -> list[dict]:
    writers: dict[str, dict[str, int]] = defaultdict(dict)
    readers: dict[str, dict[str, int]] = defaultdict(dict)
    for r in rows:
        for fld, cnt in r["writes"].items():
            writers[fld][r["name"]] = cnt
        for fld, cnt in r["reads"].items():
            readers[fld][r["name"]] = cnt
    all_fields = sorted(set(model_decl) | set(writers) | set(readers))
    out = []
    for fld in all_fields:
        w_groups = {FUNC_GROUP.get(fn, "未归组") for fn in writers[fld]}
        out.append({
            "name": fld,
            "decl_line": model_decl.get(fld),
            "writers": writers[fld],
            "readers": readers[fld],
            "multi_group_write": len(w_groups) >= 2,
        })
    return out


def fmt_fn_groups(fn_counts: dict[str, int]) -> str:
    if not fn_counts:
        return "—"
    parts = []
    for fn in sorted(fn_counts):
        grp = FUNC_GROUP.get(fn, "未归组")
        cnt = fn_counts[fn]
        parts.append(f"`{fn}`[{grp}]×{cnt}" if cnt > 1 else f"`{fn}`[{grp}]")
    return "、".join(parts)


def render_table1(facts: dict) -> list[str]:
    rows, called_by, ui_calls = facts["rows"], facts["called_by"], facts["ui_calls"]
    lines = [
        "## 表一 DOM 层函数",
        "",
        "| 函数名 | 起止行 | 行数 | 所属组 | 读的 model 字段 | 写的 model 字段 | 调用的其他 DOM 函数 | 被哪些 DOM 函数调用 | 挂在 PhoneUI | test_phone_ui.py 调用次数 |",
        "|---|---|---:|---|---|---|---|---|---|---:|",
    ]
    tot_lines = tot_r_pairs = tot_r_cnt = tot_w_pairs = tot_w_cnt = tot_ui = tot_test = 0
    for r in rows:
        name = r["name"]
        grp = FUNC_GROUP.get(name, "未归组")
        tot_lines += r["lines"]
        tot_r_pairs += len(r["reads"])
        tot_r_cnt += sum(r["reads"].values())
        tot_w_pairs += len(r["writes"])
        tot_w_cnt += sum(r["writes"].values())
        tot_ui += 1 if r["inPhoneUI"] else 0
        t_cnt = ui_calls.get(name, 0)
        tot_test += t_cnt
        lines.append(
            f"| `{name}` | {r['start']}–{r['end']} | {r['lines']} | {grp} | "
            f"{fmt_counts(r['reads'])} | {fmt_counts(r['writes'])} | "
            f"{fmt_counts(r['calls'])} | {fmt_counts(called_by[name])} | "
            f"{'是' if r['inPhoneUI'] else '否'} | {t_cnt} |"
        )
    lines.append(
        f"| **合计** | **{len(rows)} 个函数** | **{tot_lines}** | **5 组** | "
        f"**{tot_r_pairs} 关系 / {tot_r_cnt} 次** | **{tot_w_pairs} 关系 / {tot_w_cnt} 次** | "
        f"— | — | **{tot_ui} 个** | **{tot_test} 次** |"
    )
    return lines


def render_table2(field_stats: list[dict]) -> list[str]:
    lines = [
        "",
        "## 表二 model 字段",
        "",
        "| 字段名 | 声明行 | 写它的函数及所属组 | 读它的函数及所属组 | 被两个及以上组写 |",
        "|---|---:|---|---|---|",
    ]
    w_pairs = w_cnt = r_pairs = r_cnt = multi_cnt = 0
    for fs in field_stats:
        w_pairs += len(fs["writers"])
        w_cnt += sum(fs["writers"].values())
        r_pairs += len(fs["readers"])
        r_cnt += sum(fs["readers"].values())
        if fs["multi_group_write"]:
            multi_cnt += 1
        decl = str(fs["decl_line"]) if fs["decl_line"] else "未声明（动态）"
        lines.append(
            f"| `{fs['name']}` | {decl} | {fmt_fn_groups(fs['writers'])} | "
            f"{fmt_fn_groups(fs['readers'])} | {'是' if fs['multi_group_write'] else '否'} |"
        )
    lines.append(
        f"| **合计** | **{len(field_stats)} 个字段** | **{w_pairs} 关系 / {w_cnt} 次** | "
        f"**{r_pairs} 关系 / {r_cnt} 次** | **{multi_cnt} 个** |"
    )
    lines.append("")
    lines.append(
        "> 注：P1 口径只计 `model.<字段>` 直接访问；另有两个经 `PhoneModel` 传入 `model` 引用的间接写：`ingest` 调 `PhoneModel.setClock(model, ...)` 写 `model.clock`、`buildRow` 调 `PhoneModel.toggleWhy(model, ...)` 写 `model.whyId`。"
    )
    return lines


def render_table3(rows: list[dict]) -> list[str]:
    edges = sorted(
        (FUNC_GROUP.get(r["name"], "未归组"), FUNC_GROUP.get(c, "未归组"), f"`{r['name']}` → `{c}`", cnt)
        for r in rows for c, cnt in r["calls"].items()
        if FUNC_GROUP.get(r["name"], "未归组") != FUNC_GROUP.get(c, "未归组")
    )
    lines = ["", "## 表三 组间调用", "", "| 调用方组 | 被调方组 | 函数对 | 次数 |", "|---|---|---|---:|"]
    lines.extend(f"| {cg} | {tg} | {pair} | {cnt} |" for cg, tg, pair, cnt in edges)
    lines.append(f"| **合计** | **{len(edges)} 对跨组函数对** | — | **{sum(e[3] for e in edges)} 次** |")
    return lines


def render_table4(facts: dict) -> list[str]:
    pm_list, pm_hits = facts["data"]["phoneModel"], facts["pm_hits"]
    used_groups: dict[str, set[str]] = defaultdict(set)
    for r in facts["rows"]:
        grp = FUNC_GROUP.get(r["name"], "未归组")
        for m in r["pmUses"]:
            used_groups[m].add(grp)
    lines = ["", "## 表四 PhoneModel 成员", "", "| 名字 | 起止行 | 行数 | 被哪些组的 DOM 函数用 | test_phone_ui.py 出现次数 |", "|---|---:|---:|---|---:|"]
    for m in pm_list:
        grps = "、".join(sorted(used_groups[m["name"]])) or "—"
        lines.append(f"| `{m['name']}` | {m['start']}–{m['end']} | {m['lines']} | {grps} | {pm_hits.get(m['name'], 0)} |")
    lines.append(
        f"| **合计** | **{len(pm_list)} 个成员** | **{sum(m['lines'] for m in pm_list)}** | "
        f"**{sum(1 for m in pm_list if used_groups[m['name']])} 个被 DOM 使用** | "
        f"**{sum(pm_hits.get(m['name'], 0) for m in pm_list)} 次** |"
    )
    return lines


def render_table5(facts: dict) -> list[str]:
    ungrouped = list(facts["data"]["ungrouped"]) + [
        {"name": fn, "kind": "function", "line": facts["by_name"][fn]["start"]} for fn in facts["extra_funcs"]
    ]
    notes = {"$": "DOM 选择器快捷箭头函数 `document.getElementById(id)`", "REQUEST_TIMEOUT_MS": "请求超时常量 `8000`",
             "model": "DOM 层闭包状态对象", "SHEET_TITLES": "sheet 标题映射常量", "LIST_ZONES": "列表三区映射常量"}
    lines = ["", "## 表五 未归组的顶层名字", "", "| 名字 | 形态 | 定义行 | 说明 |", "|---|---|---:|---|"]
    lines.extend(f"| `{i['name']}` | {i['kind']} | {i['line']} | {notes.get(i['name'], '未归组顶层函数')} |" for i in ungrouped)
    lines.append(f"| **合计** | **{len(ungrouped)} 项** | — | — |")
    return lines


def render_table6(facts: dict) -> list[str]:
    scripts, static_rows = facts["scripts"], facts["static_rows"]
    lines = ["", "## 表六 页面加载现状", "", "### index.html 的 script 标签原文", "", "| 序号 | 标签原文 |", "|---:|---|"]
    lines.extend(f"| {idx} | `{tag}` |" for idx, tag in enumerate(scripts, 1))
    lines.extend(["", "### PHONE_STATIC 全部条目", "", "| 路径 | 文件名 | Content-Type |", "|---|---|---|"])
    lines.extend(f"| `{r}` | `{f}` | `{c}` |" for r, f, c in static_rows)
    lines.append(f"| **合计** | **{len(scripts)} 条 script / {len(static_rows)} 条静态路径** | — |")
    return lines


def verify_facts(facts: dict, field_stats: list[dict]) -> list[str]:
    errors = []
    if facts["missing"]:
        errors.append("P0 名单缺失函数: " + ", ".join(facts["missing"]))
    if facts["extra_funcs"]:
        errors.append("DOM 块出现名单外顶层函数: " + ", ".join(facts["extra_funcs"]))
    t1_w_pairs = sum(len(r["writes"]) for r in facts["rows"])
    t1_w_cnt = sum(sum(r["writes"].values()) for r in facts["rows"])
    t2_w_pairs = sum(len(fs["writers"]) for fs in field_stats)
    t2_w_cnt = sum(sum(fs["writers"].values()) for fs in field_stats)
    if t1_w_pairs != t2_w_pairs or t1_w_cnt != t2_w_cnt:
        errors.append(f"写入合计不一致: 表一({t1_w_pairs}/{t1_w_cnt}) != 表二({t2_w_pairs}/{t2_w_cnt})")
    return errors


def render_markdown(facts: dict, field_stats: list[dict]) -> str:
    header = [
        "# 手机页（local/ui/m）移动前事实清点",
        "",
        "- 数据来源：`local/ui/m/app.js`、`local/ui/m/index.html`、`local/infrastructure/phone_http.py`、`local/tests/test_phone_ui.py`。",
        "- 口径：函数范围与词法借 `tools/code_shape/jsscan.mjs`、`jslex.mjs`；`model.字段` 读写只计直接访问（赋值、复合赋值、自增自减与 `add`/`delete`/`clear`/`push` 等原地修改及嵌套属性赋值计写，其余计读）；字符常量与注释不计。",
        "",
    ]
    body = (
        header
        + render_table1(facts)
        + render_table2(field_stats)
        + render_table3(facts["rows"])
        + render_table4(facts)
        + render_table5(facts)
        + render_table6(facts)
    )
    return "\n".join(body) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="清点手机页 DOM 层事实表")
    parser.add_argument("--check", action="store_true", help="只重算核对，不写文件")
    args = parser.parse_args(argv)
    facts = build_facts()
    field_stats = build_field_stats(facts["rows"], facts["data"]["modelDecl"])
    errors = verify_facts(facts, field_stats)
    if errors:
        for err in errors:
            print("ERROR:", err, file=sys.stderr)
        return 1
    t1_w = sum(sum(r["writes"].values()) for r in facts["rows"])
    t1_wp = sum(len(r["writes"]) for r in facts["rows"])
    if args.check:
        print(f"OK: P0 全部 {len(FUNC_GROUP)} 个函数匹配，写入合计表一=表二 ({t1_wp} 关系 / {t1_w} 次)")
        return 0
    OUT_MD.write_text(render_markdown(facts, field_stats), encoding="utf-8", newline="\n")
    print(f"Wrote {OUT_MD} ({len(facts['rows'])} funcs, {len(field_stats)} fields, {t1_wp}/{t1_w} writes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
