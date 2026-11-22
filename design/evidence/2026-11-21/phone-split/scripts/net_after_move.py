#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""在拆分后的新文件位置复跑第一组 72 条变异，并与 phone-net/after.md 对照。

用法（仓库根，Python 3.12）：
  python design/evidence/2026-11-21/phone-split/scripts/net_after_move.py --workers 4

@author Author
"""
from __future__ import annotations

import argparse
import concurrent.futures
import importlib.util
import json
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[5]
UI_M = REPO / "local" / "ui" / "m"
JSSCAN_MJS = REPO / "tools" / "code_shape" / "jsscan.mjs"
PHONE_NET_DIR = REPO / "design" / "evidence" / "2026-11-22" / "phone-net"
MUTATE_PY = PHONE_NET_DIR / "scripts" / "mutate_phone.py"
EQUIV_JSON = PHONE_NET_DIR / "scripts" / "equiv.json"
AFTER_MD = PHONE_NET_DIR / "after.md"
OUT_MD = Path(__file__).resolve().parents[1] / "net-after-move.md"

OVERLAY_FILES = (
    "local/infrastructure/phone_http.py",
    "local/tests/test_phone_ui.py",
    "local/tests/test_phone_infra.py",
    "local/tests/test_retry_policy.py",
    "tools/code_shape/baseline.json",
)


def load_mutate_module():
    spec = importlib.util.spec_from_file_location("phone_net_mutate", MUTATE_PY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def read_manifest() -> list[str]:
    html = (UI_M / "index.html").read_text(encoding="utf-8")
    return re.findall(r'<script\s+src="([^"]+)"\s*></script>', html)


def locate_top_functions(scripts: list[str]) -> dict[str, tuple[Path, int, int]]:
    node = shutil.which("node")
    if not node:
        raise RuntimeError("node 不可用")
    code = (
        'import { readFileSync } from "node:fs";\n'
        'import { pathToFileURL } from "node:url";\n'
        'const [scan, ...files] = process.argv.slice(2);\n'
        'const { findFunctions } = await import(pathToFileURL(scan).href);\n'
        'const out = {};\n'
        'for (const fpath of files) {\n'
        '  const { funcs } = findFunctions(readFileSync(fpath, "utf8"));\n'
        '  for (const f of funcs) {\n'
        '    if (f.depth === 0 && f.kind === "function" && f.name) {\n'
        '      out[f.name] = [fpath, f.start, f.end];\n'
        '    }\n'
        '  }\n'
        '}\n'
        'process.stdout.write(JSON.stringify(out));\n'
    )
    paths = [str(UI_M / s) for s in scripts]
    res = subprocess.run(
        [node, "--input-type=module", "-", str(JSSCAN_MJS), *paths],
        input=code, capture_output=True, text=True, encoding="utf-8", check=True,
    )
    raw = json.loads(res.stdout)
    return {name: (Path(info[0]).relative_to(REPO), info[1], info[2]) for name, info in raw.items()}


def dedent_dom_mutation(locate: str, repl: str) -> tuple[str, str]:
    """DOM 层从 if 块内左移两格：调整带行首锚点或多行的缩进。"""
    if locate.startswith("^  "):
        new_loc = "^" + locate[3:]
        new_repl = repl[2:] if repl.startswith("  ") else repl
        return new_loc, new_repl
    if "\n" in locate:
        parts = locate.split("\n")
        adjusted = [parts[0]] + [p[2:] if p.startswith("  ") else p for p in parts[1:]]
        return "\n".join(adjusted), repl
    return locate, repl


def parse_expected_after() -> dict[str, str]:
    out: dict[str, str] = {}
    pat = re.compile(r"^\|\s*(M\d+)\s*\|.*\|\s*(行为守|字面守|无人守|无效|等价)\s*\|\s*(?:`[^`]*`|—)\s*\|$")
    for line in AFTER_MD.read_text(encoding="utf-8").splitlines():
        m = pat.match(line.strip())
        if m:
            out[m.group(1)] = m.group(2)
    return out


def open_overlay_replica(zip_path: Path) -> Path:
    root = Path(tempfile.mkdtemp(prefix="phone_split_mut_"))
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(root)
    (root / "local/ui/m/app.js").unlink(missing_ok=True)
    for p in UI_M.iterdir():
        if p.is_file():
            (root / "local/ui/m" / p.name).write_bytes(p.read_bytes())
    for rel in OVERLAY_FILES:
        dst = root / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes((REPO / rel).read_bytes())
    return root


def run_one(mod, root: Path, orig_texts: dict[Path, str],
            fn_map: dict[str, tuple[Path, int, int]], bmap: dict[str, bool], mut: tuple) -> dict:
    mid, kind, fn, occur, locate, repl = mut
    loc_info = fn_map.get(fn)
    if not loc_info:
        return {"id": mid, "kind": kind, "func": fn, "occur": occur, "file": "—",
                "locate": locate, "replace": repl, "status": "无效", "first_fail": ""}
    rel_path, start, end = loc_info
    adj_loc, adj_repl = dedent_dom_mutation(locate, repl)
    orig_lf = orig_texts[rel_path]
    mutated = mod.apply_in_func(orig_lf, start, end, adj_loc, adj_repl)
    if mutated is None:
        return {"id": mid, "kind": kind, "func": fn, "occur": occur, "file": rel_path.as_posix(),
                "locate": adj_loc, "replace": adj_repl, "status": "无效", "first_fail": ""}
    target = root / rel_path
    target.write_text(mutated, encoding="utf-8", newline="\n")
    try:
        chk = subprocess.run([shutil.which("node"), "--check", str(target)],
                             capture_output=True, text=True, check=False)
        if chk.returncode != 0:
            return {"id": mid, "kind": kind, "func": fn, "occur": occur, "file": rel_path.as_posix(),
                    "locate": adj_loc, "replace": adj_repl, "status": "无效", "first_fail": ""}
        code, fails, _ = mod.run_unittest(root)
    finally:
        target.write_text(orig_lf, encoding="utf-8", newline="\n")
    if code == 0:
        return {"id": mid, "kind": kind, "func": fn, "occur": occur, "file": rel_path.as_posix(),
                "locate": adj_loc, "replace": adj_repl, "status": "无人守", "first_fail": ""}
    if not fails:
        return {"id": mid, "kind": kind, "func": fn, "occur": occur, "file": rel_path.as_posix(),
                "locate": adj_loc, "replace": adj_repl, "status": "字面守", "first_fail": "(unknown)"}
    status = "行为守" if any(bmap.get(f, False) for f in fails) else "字面守"
    return {"id": mid, "kind": kind, "func": fn, "occur": occur, "file": rel_path.as_posix(),
            "locate": adj_loc, "replace": adj_repl, "status": status, "first_fail": fails[0]}


def worker_chunk(mod, zip_path: Path, orig_texts: dict[Path, str],
                 fn_map: dict[str, tuple[Path, int, int]], bmap: dict[str, bool], chunk: list[tuple]) -> list[dict]:
    root = open_overlay_replica(zip_path)
    try:
        return [run_one(mod, root, orig_texts, fn_map, bmap, mut) for mut in chunk]
    finally:
        shutil.rmtree(root, ignore_errors=True)


def run_all(mod, workers: int) -> list[dict]:
    scripts = read_manifest()
    fn_map = locate_top_functions(scripts)
    orig_texts = {
        Path("local/ui/m") / s: (UI_M / s).read_text(encoding="utf-8").replace("\r\n", "\n")
        for s in scripts
    }
    bmap = mod.test_behavior_map()
    tmp_zip_dir = Path(tempfile.mkdtemp(prefix="phone_split_zip_"))
    zip_path = tmp_zip_dir / "repo.zip"
    try:
        mod.create_archive_zip(zip_path)
        w = max(1, min(4, workers, len(mod.MUTATIONS)))
        chunks = [list(mod.MUTATIONS)[i::w] for i in range(w)]
        merged: list[dict] = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=w) as ex:
            futs = [ex.submit(worker_chunk, mod, zip_path, orig_texts, fn_map, bmap, ch)
                    for ch in chunks if ch]
            for fut in concurrent.futures.as_completed(futs):
                merged.extend(fut.result())
        order = {m[0]: idx for idx, m in enumerate(mod.MUTATIONS)}
        merged.sort(key=lambda r: order[r["id"]])
        return merged
    finally:
        shutil.rmtree(tmp_zip_dir, ignore_errors=True)


def format_report(results: list[dict], equiv: dict[str, str], expected: dict[str, str]) -> tuple[str, int]:
    counts = {"行为守": 0, "字面守": 0, "无人守": 0, "无效": 0, "等价": 0}
    mismatches = 0
    rows = []
    for r in results:
        st = r["status"]
        if st == "无人守" and r["id"] in equiv:
            st = "等价"
        counts[st] = counts.get(st, 0) + 1
        exp = expected.get(r["id"], "?")
        match_str = "一致" if st == exp else f"不一致（原={exp}）"
        if st != exp:
            mismatches += 1
        ff = f"`{r['first_fail']}`" if r["first_fail"] else "—"
        rows.append(f"| {r['id']} | {r['kind']} | `{r['file']}` | `{r['func']}` | {st} | {exp} | {match_str} | {ff} |")
    verdict = "**完全一致（0 条偏差）**" if mismatches == 0 else f"**存在偏差（{mismatches} 条不一致）**"
    lines = [
        "# 拆分后安全网复跑对照（72 条变异）",
        "",
        f"- 原版对照：`design/evidence/2026-11-22/phone-net/after.md`",
        f"- 总结论：{verdict}（行为守 {counts['行为守']}、等价 {counts['等价']}、字面守 {counts['字面守']}、无人守 {counts['无人守']}、无效 {counts['无效']}，共 {len(results)} 条）",
        "",
        "| 编号 | 类 | 新文件 | 函数 | 本次结论 | 原结论 | 对照 | 第一条失败用例 |",
        "|---|---|---|---|---|---|---|---|",
        *rows,
    ]
    return "\n".join(lines) + "\n", mismatches


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="拆分后安全网 72 条变异复跑")
    ap.add_argument("--workers", type=int, default=4, help="并行副本数（最大 4）")
    args = ap.parse_args(argv)
    mod = load_mutate_module()
    equiv = json.loads(EQUIV_JSON.read_text(encoding="utf-8"))
    expected = parse_expected_after()
    results = run_all(mod, args.workers)
    md, mismatches = format_report(results, equiv, expected)
    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text(md, encoding="utf-8", newline="\n")
    print(f"Wrote {OUT_MD} ({len(results)} mutations, mismatches={mismatches})")
    return 1 if mismatches else 0


if __name__ == "__main__":
    raise SystemExit(main())
