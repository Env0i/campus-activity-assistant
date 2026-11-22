#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""逐字核对手机页脚本拆分：成员、顶层声明与逐行集合对照 HEAD 原文。

用法（仓库根，Python 3.12）：
  python design/evidence/2026-11-21/phone-split/scripts/move_check.py

@author Author
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[5]
UI_M = REPO / "local" / "ui" / "m"
INDEX_HTML = UI_M / "index.html"
JSSCAN_MJS = REPO / "tools" / "code_shape" / "jsscan.mjs"
JSLEX_MJS = REPO / "tools" / "code_shape" / "jslex.mjs"
OUT_MD = Path(__file__).resolve().parents[1] / "move-check.md"

ALLOWED_ADDED_LINES = frozenset({
    '"use strict";',
    "Object.assign(PhoneModel, {",
    "});",
})

NODE_EXTRACT_SCRIPT = r"""
import { readFileSync } from "node:fs";
import { pathToFileURL } from "node:url";
const [jsscanPath, jslexPath, ...files] = process.argv.slice(2);
const { findFunctions } = await import(pathToFileURL(jsscanPath).href);
const { braceDepths } = await import(pathToFileURL(jslexPath).href);

function scanObjectMembers(src, tokens, funcs, depths, targetDepth, maxLine) {
  const pmMethods = new Map();
  for (const f of funcs) {
    if (f.depth === 0 && f.startTok != null) pmMethods.set(f.startTok, f);
  }
  const out = [];
  for (let k = 0; k < tokens.length; k++) {
    const t = tokens[k];
    if (maxLine && t.line >= maxLine) continue;
    if (depths[k] !== targetDepth || t.type !== "id") continue;
    const f = pmMethods.get(k) || (tokens[k - 1]?.value === "async" && pmMethods.get(k - 1));
    if (f) {
      out.push({ name: f.name, kind: "method", start: f.start, end: f.end });
      k = f.bodyClose;
    } else if (tokens[k + 1]?.value === ":") {
      let end = t.line, j = k + 2;
      while (j < tokens.length && depths[j] >= targetDepth
             && !(depths[j] === targetDepth && tokens[j].value === ",")) {
        end = tokens[j].line;
        j += 1;
      }
      out.push({ name: t.value, kind: "prop", start: t.line, end });
      k = j;
    }
  }
  return out;
}

function scanDomDecls(tokens, funcs, depths, minLine, targetDepth) {
  const fMap = new Map();
  for (const f of funcs) {
    if (f.depth === 0 && f.kind === "function" && f.start >= minLine && f.name) {
      fMap.set(f.startTok, f);
    }
  }
  const out = [];
  for (let k = 0; k < tokens.length; k++) {
    const t = tokens[k];
    if (t.line < minLine || depths[k] !== targetDepth) continue;
    const f = fMap.get(k);
    if (f) {
      out.push({ name: f.name, kind: "func", start: f.start, end: f.end });
      k = f.bodyClose;
      continue;
    }
    if (t.value === "const" && tokens[k + 1]?.type === "id") {
      let end = t.line, j = k + 2;
      while (j < tokens.length && !(depths[j] === targetDepth && tokens[j].value === ";")) {
        end = tokens[j].line;
        j += 1;
      }
      if (j < tokens.length) end = tokens[j].line;
      out.push({ name: tokens[k + 1].value, kind: "const", start: t.line, end });
      k = j;
    }
  }
  return out;
}

function inspectFile(filePath, isOrig) {
  const src = readFileSync(filePath, "utf8");
  const { tokens, funcs } = findFunctions(src);
  const depths = braceDepths(tokens);
  if (isOrig) {
    let domStart = 0;
    for (let k = 0; k < tokens.length - 4; k++) {
      if (tokens[k].value === "if" && tokens[k + 2].value === "typeof"
          && tokens[k + 3].value === "document") {
        domStart = tokens[k].line;
        break;
      }
    }
    const members = scanObjectMembers(src, tokens, funcs, depths, 1, domStart);
    const domDecls = scanDomDecls(tokens, funcs, depths, domStart + 1, 1);
    return { members, domDecls };
  }
  const hasAssign = tokens.some((t, i) => depths[i] === 0 && t.value === "Object"
    && tokens[i + 2]?.value === "assign" && tokens[i + 4]?.value === "PhoneModel");
  const hasConstPM = tokens.some((t, i) => depths[i] === 0 && t.value === "const"
    && tokens[i + 1]?.value === "PhoneModel");
  const members = (hasConstPM || hasAssign) ? scanObjectMembers(src, tokens, funcs, depths, 1, 0) : [];
  const domDecls = (!hasConstPM && !hasAssign) ? scanDomDecls(tokens, funcs, depths, 1, 0) : [];
  return { members, domDecls };
}

const result = {};
for (let i = 0; i < files.length; i++) {
  result[files[i]] = inspectFile(files[i], i === 0);
}
process.stdout.write(JSON.stringify(result));
"""


def read_head_app() -> str:
    res = subprocess.run(
        ["git", "show", "HEAD:local/ui/m/app.js"],
        cwd=REPO, capture_output=True, check=True,
    )
    return res.stdout.decode("utf-8").replace("\r\n", "\n")


def read_script_list() -> list[str]:
    html = INDEX_HTML.read_text(encoding="utf-8")
    return re.findall(r'<script\s+src="([^"]+)"\s*></script>', html)


def run_node_extract(paths: list[Path]) -> dict:
    node = shutil.which("node")
    if not node:
        raise RuntimeError("node 不可用")
    args = [node, "--input-type=module", "-", str(JSSCAN_MJS), str(JSLEX_MJS), *(str(p) for p in paths)]
    res = subprocess.run(
        args, input=NODE_EXTRACT_SCRIPT,
        capture_output=True, text=True, encoding="utf-8", check=True,
    )
    return json.loads(res.stdout)


def slice_text(lines: list[str], start: int, end: int, strip_two: bool) -> str:
    chunk = lines[start - 1:end]
    if strip_two:
        stripped = []
        for ln in chunk:
            if ln == "":
                stripped.append("")
            elif ln.startswith("  "):
                stripped.append(ln[2:])
            else:
                stripped.append(ln)
        chunk = stripped
    return "\n".join(chunk)


def header_comment_lines(text: str) -> Counter[str]:
    lines = text.splitlines()
    out: Counter[str] = Counter()
    idx = 0
    if idx < len(lines) and lines[idx].strip() == '"use strict";':
        idx += 1
    while idx < len(lines) and lines[idx].strip() == "":
        idx += 1
    if idx < len(lines) and lines[idx].lstrip().startswith("/*"):
        while idx < len(lines):
            cur = lines[idx].lstrip()
            out[cur] += 1
            idx += 1
            if "*/" in cur:
                break
    return out


def check_items(orig_lines: list[str], orig_items: list[dict], strip_orig: bool,
                new_texts: dict[str, list[str]], new_map: dict[str, list[dict]]) -> list[str]:
    errors: list[str] = []
    by_name: dict[str, list[tuple[str, str]]] = {}
    for fname, items in new_map.items():
        for it in items:
            code = slice_text(new_texts[fname], it["start"], it["end"], False)
            by_name.setdefault(it["name"], []).append((fname, code))
    for orig in orig_items:
        name = orig["name"]
        expected = slice_text(orig_lines, orig["start"], orig["end"], strip_orig)
        found = by_name.get(name, [])
        if len(found) != 1:
            errors.append(f"成员/声明 {name} 在新文件中出现 {len(found)} 次（应为 1 次）")
            continue
        fname, actual = found[0]
        if actual != expected:
            errors.append(f"成员/声明 {name} 在 {fname} 中与原文不一致")
    orig_names = {o["name"] for o in orig_items}
    extra = sorted(set(by_name) - orig_names)
    for name in extra:
        errors.append(f"新文件中多出声明 {name}")
    return errors


def check_lines(orig_text: str, scripts: list[str], new_texts: dict[str, str]) -> tuple[list[str], dict]:
    orig_counter: Counter[str] = Counter()
    for ln in orig_text.splitlines():
        s = ln.lstrip()
        if s:
            orig_counter[s] += 1
    for removed in ('if (typeof document !== "undefined") {', "}"):
        if orig_counter[removed] > 0:
            orig_counter[removed] -= 1
            if orig_counter[removed] == 0:
                del orig_counter[removed]

    new_counter: Counter[str] = Counter()
    hdr_counter: Counter[str] = Counter()
    for name in scripts:
        text = new_texts[name]
        for ln in text.splitlines():
            s = ln.lstrip()
            if s:
                new_counter[s] += 1
        hdr_counter += header_comment_lines(text)

    errors: list[str] = []
    missing = orig_counter - new_counter
    for ln, cnt in sorted(missing.items()):
        errors.append(f"原文非空行缺失 x{cnt}: {ln}")

    extra = new_counter - orig_counter
    for ln, cnt in sorted(extra.items()):
        if ln in ALLOWED_ADDED_LINES:
            continue
        hdr_cnt = hdr_counter.get(ln, 0)
        if cnt <= hdr_cnt:
            continue
        errors.append(f"新文件多出非白名单行 x{cnt - hdr_cnt}: {ln}")

    stats = {
        "orig_nonempty": sum(orig_counter.values()) + 2,
        "new_nonempty": sum(new_counter.values()),
        "header_lines": sum(hdr_counter.values()),
    }
    return errors, stats


def build_report(scripts: list[str], pm_count: int, dom_count: int,
                 stats: dict, errors: list[str]) -> str:
    status = "PASS（0 项失败）" if not errors else f"FAIL（{len(errors)} 项失败）"
    lines = [
        "# 手机页拆分逐字核对（move_check）",
        "",
        f"- 结论：**{status}**",
        f"- 原文来源：`git show HEAD:local/ui/m/app.js`（非空行 {stats['orig_nonempty']} 行）",
        f"- 新文件清单（按 `local/ui/m/index.html` 顺序，共 {len(scripts)} 份）："
        + "、".join(f"`{s}`" for s in scripts),
        f"- PhoneModel 成员核对：{pm_count} 个",
        f"- DOM 顶层声明（函数与 const）核对：{dom_count} 个",
        f"- 新文件非空行合计：{stats['new_nonempty']} 行（含新增文件头注释 {stats['header_lines']} 行）",
        "",
    ]
    if errors:
        lines.extend(["## 失败项", ""])
        lines.extend(f"- {e}" for e in errors)
    else:
        lines.append("全部 PhoneModel 成员、DOM 顶层声明及非空行频次均与 HEAD 原文逐字一致。")
    return "\n".join(lines) + "\n"


def main() -> int:
    import tempfile
    orig_text = read_head_app()
    orig_lines = orig_text.splitlines()
    scripts = read_script_list()
    script_paths = [UI_M / s for s in scripts]
    missing_files = [s for s, p in zip(scripts, script_paths) if not p.is_file()]
    if missing_files:
        print("缺少脚本文件:", missing_files, file=sys.stderr)
        return 1

    with tempfile.NamedTemporaryFile("w", suffix=".js", encoding="utf-8", delete=False) as tf:
        tf.write(orig_text)
        orig_tmp = Path(tf.name)
    try:
        scanned = run_node_extract([orig_tmp, *script_paths])
    finally:
        orig_tmp.unlink(missing_ok=True)

    orig_scan = scanned[str(orig_tmp)]
    new_texts = {s: (UI_M / s).read_text(encoding="utf-8").replace("\r\n", "\n") for s in scripts}
    new_lines = {s: text.splitlines() for s, text in new_texts.items()}
    new_pm = {s: scanned[str(UI_M / s)]["members"] for s in scripts}
    new_dom = {s: scanned[str(UI_M / s)]["domDecls"] for s in scripts}

    errors = []
    errors.extend(check_items(orig_lines, orig_scan["members"], False, new_lines, new_pm))
    errors.extend(check_items(orig_lines, orig_scan["domDecls"], True, new_lines, new_dom))
    line_errors, stats = check_lines(orig_text, scripts, new_texts)
    errors.extend(line_errors)

    report = build_report(scripts, len(orig_scan["members"]), len(orig_scan["domDecls"]), stats, errors)
    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text(report, encoding="utf-8", newline="\n")
    print(report)
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
