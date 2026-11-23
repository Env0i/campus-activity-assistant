#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""在整理后的手机页脚本位置复跑第一组 72 条变异，并与 phone-net/after.md 对照。

用法（仓库根，Python 3.12）：
  python design/evidence/2026-11-23/phone-session-tidy/scripts/net_after_tidy.py --list
  python design/evidence/2026-11-23/phone-session-tidy/scripts/net_after_tidy.py --workers 4

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
OUT_MD = Path(__file__).resolve().parents[1] / "net-after-tidy.md"

# 因提炼 adoptCookieCsrf() 与 PhoneModel.sessionVerdict() 而搬迁或改写条件的条目：
# id -> (新函数名, 新定位原文, 新替换原文, 变动原因)
RELOCATIONS: dict[str, tuple[str, str, str, str]] = {
    "M06": (
        "adoptCookieCsrf",
        "if (fresh) model.csrf = fresh;",
        "if (!(fresh)) model.csrf = fresh;",
        "api() 写请求分支刷新 CSRF 迁入 adoptCookieCsrf()",
    ),
    "M07": (
        "adoptCookieCsrf",
        "if (fresh) model.csrf = fresh;",
        "if (fresh) void 0;",
        "api() 写请求分支刷新 CSRF 迁入 adoptCookieCsrf()",
    ),
    "M12": (
        "api",
        'if (verdict === "need_pair")',
        'if (!(verdict === "need_pair"))',
        "api() /api/action 401 分流改按 PhoneModel.sessionVerdict 判定",
    ),
    "M13": (
        "api",
        'if (verdict === "forbidden")',
        'if (!(verdict === "forbidden"))',
        "api() /api/action 403 分流改按 PhoneModel.sessionVerdict 判定",
    ),
    "M47": (
        "poll",
        'if (verdict === "need_pair")',
        'if (!(verdict === "need_pair"))',
        "poll() 401 分流改按 PhoneModel.sessionVerdict 判定",
    ),
    "M48": (
        "poll",
        'if (verdict === "forbidden")',
        'if (!(verdict === "forbidden"))',
        "poll() 403 分流改按 PhoneModel.sessionVerdict 判定",
    ),
    "M49": (
        "poll",
        'if (verdict !== "ok")',
        'if (!(verdict !== "ok"))',
        "poll() 非 200 分流改按 PhoneModel.sessionVerdict 判定",
    ),
    "M61": (
        "adoptCookieCsrf",
        "if (fresh) model.csrf = fresh;",
        "if (!(fresh)) model.csrf = fresh;",
        "onForbidden() 刷新 CSRF 迁入 adoptCookieCsrf()",
    ),
    "M62": (
        "adoptCookieCsrf",
        "if (fresh) model.csrf = fresh;",
        "if (fresh) void 0;",
        "onForbidden() 刷新 CSRF 迁入 adoptCookieCsrf()",
    ),
}


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
    """DOM 层相对原 app.js 左移两格：调整带行首锚点或多行的缩进。"""
    if locate.startswith("^  "):
        new_loc = "^" + locate[3:]
        new_repl = repl[2:] if repl.startswith("  ") else repl
        return new_loc, new_repl
    if "\n" in locate:
        parts = locate.split("\n")
        adjusted = [parts[0]] + [p[2:] if p.startswith("  ") else p for p in parts[1:]]
        return "\n".join(adjusted), repl
    return locate, repl


def resolve_mutation(mut: tuple) -> tuple[str, str, str, int, str, str, bool]:
    mid, kind, fn, occur, locate, repl = mut
    if mid in RELOCATIONS:
        new_fn, new_loc, new_repl, _ = RELOCATIONS[mid]
        return mid, kind, new_fn, 1, new_loc, new_repl, True
    adj_loc, adj_repl = dedent_dom_mutation(locate, repl)
    return mid, kind, fn, occur, adj_loc, adj_repl, False


def parse_expected_after() -> dict[str, str]:
    out: dict[str, str] = {}
    pat = re.compile(r"^\|\s*(M\d+)\s*\|.*\|\s*(行为守|字面守|无人守|无效|等价)\s*\|\s*(?:`[^`]*`|—)\s*\|$")
    for line in AFTER_MD.read_text(encoding="utf-8").splitlines():
        m = pat.match(line.strip())
        if m:
            out[m.group(1)] = m.group(2)
    return out


def open_overlay_replica(zip_path: Path) -> Path:
    root = Path(tempfile.mkdtemp(prefix="phone_tidy_mut_"))
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(root)
    for p in UI_M.iterdir():
        if p.is_file():
            (root / "local/ui/m" / p.name).write_bytes(p.read_bytes())
    return root


def list_locations(mod) -> int:
    scripts = read_manifest()
    fn_map = locate_top_functions(scripts)
    orig_texts = {
        Path("local/ui/m") / s: (UI_M / s).read_text(encoding="utf-8").replace("\r\n", "\n")
        for s in scripts
    }
    missed = 0
    for mut in mod.MUTATIONS:
        mid, kind, fn, occur, adj_loc, adj_repl, reloc = resolve_mutation(mut)
        loc_info = fn_map.get(fn)
        ok = False
        file_str = "—"
        if loc_info:
            rel_path, start, end = loc_info
            file_str = rel_path.as_posix()
            ok = mod.apply_in_func(orig_texts[rel_path], start, end, adj_loc, adj_repl) is not None
        if not ok:
            missed += 1
        tag = "RELOC" if reloc else "ORIG"
        loc_one = adj_loc.replace("\n", "\\n")
        print(f"{mid}\t{kind}\t{tag}\t{file_str}:{fn}\t{'OK' if ok else 'MISS'}\t{loc_one} => {adj_repl}")
    print(f"Total: {len(mod.MUTATIONS)} (locate miss: {missed})")
    return 1 if missed else 0


def run_one(mod, root: Path, orig_texts: dict[Path, str],
            fn_map: dict[str, tuple[Path, int, int]], bmap: dict[str, bool], mut: tuple) -> dict:
    mid, kind, fn, occur, adj_loc, adj_repl, reloc = resolve_mutation(mut)
    loc_info = fn_map.get(fn)
    if not loc_info:
        return {"id": mid, "kind": kind, "func": fn, "occur": occur, "file": "—", "reloc": reloc,
                "locate": adj_loc, "replace": adj_repl, "status": "定位不到", "first_fail": "",
                "note": "未找到目标函数"}
    rel_path, start, end = loc_info
    orig_lf = orig_texts[rel_path]
    mutated = mod.apply_in_func(orig_lf, start, end, adj_loc, adj_repl)
    if mutated is None:
        return {"id": mid, "kind": kind, "func": fn, "occur": occur, "file": rel_path.as_posix(),
                "reloc": reloc, "locate": adj_loc, "replace": adj_repl, "status": "定位不到",
                "first_fail": "", "note": "定位不唯一或未命中"}
    target = root / rel_path
    target.write_text(mutated, encoding="utf-8", newline="\n")
    try:
        chk = subprocess.run([shutil.which("node"), "--check", str(target)],
                             capture_output=True, text=True, check=False)
        if chk.returncode != 0:
            return {"id": mid, "kind": kind, "func": fn, "occur": occur, "file": rel_path.as_posix(),
                    "reloc": reloc, "locate": adj_loc, "replace": adj_repl, "status": "定位不到",
                    "first_fail": "", "note": "node --check 失败"}
        code, fails, _ = mod.run_unittest(root)
    finally:
        target.write_text(orig_lf, encoding="utf-8", newline="\n")
    if code == 0:
        return {"id": mid, "kind": kind, "func": fn, "occur": occur, "file": rel_path.as_posix(),
                "reloc": reloc, "locate": adj_loc, "replace": adj_repl, "status": "无人守",
                "first_fail": "", "note": ""}
    if not fails:
        return {"id": mid, "kind": kind, "func": fn, "occur": occur, "file": rel_path.as_posix(),
                "reloc": reloc, "locate": adj_loc, "replace": adj_repl, "status": "字面守",
                "first_fail": "(unknown)", "note": ""}
    status = "行为守" if any(bmap.get(f, False) for f in fails) else "字面守"
    return {"id": mid, "kind": kind, "func": fn, "occur": occur, "file": rel_path.as_posix(),
            "reloc": reloc, "locate": adj_loc, "replace": adj_repl, "status": status,
            "first_fail": fails[0], "note": ""}


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
    tmp_zip_dir = Path(tempfile.mkdtemp(prefix="phone_tidy_zip_"))
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


def format_report(results: list[dict], equiv: dict[str, str], expected: dict[str, str]) -> tuple[str, int, int]:
    counts = {"行为守": 0, "字面守": 0, "无人守": 0, "定位不到": 0, "等价": 0}
    mismatches = 0
    unlocated: list[dict] = []
    rows = []
    for r in results:
        st = r["status"]
        if st == "定位不到":
            unlocated.append(r)
        elif st == "无人守" and r["id"] in equiv:
            st = "等价"
        counts[st] = counts.get(st, 0) + 1
        exp = expected.get(r["id"], "?")
        match_str = "一致" if st == exp else f"不一致（原={exp}）"
        if st != exp:
            mismatches += 1
        ff = f"`{r['first_fail']}`" if r["first_fail"] else "—"
        tag = "重定位" if r["reloc"] else "原样"
        rows.append(
            f"| {r['id']} | {r['kind']} | `{r['file']}` | `{r['func']}` | {tag} | {st} | {exp} | {match_str} | {ff} |"
        )
    verdict = "**完全一致（0 条偏差）**" if mismatches == 0 else f"**存在偏差（{mismatches} 条不一致）**"
    lines = [
        "# 整理后安全网复跑对照（72 条变异）",
        "",
        "- 原版对照：`design/evidence/2026-11-22/phone-net/after.md`",
        f"- 总结论：{verdict}（行为守 {counts['行为守']}、等价 {counts['等价']}、字面守 {counts['字面守']}、无人守 {counts['无人守']}、定位不到 {counts['定位不到']}，共 {len(results)} 条）",
        "",
        "| 编号 | 类 | 文件 | 新函数 | 定位方式 | 本次结论 | 原结论 | 对照 | 第一条失败用例 |",
        "|---|---|---|---|---|---|---|---|---|",
        *rows,
        "",
        "## 定位不到的条目",
        "",
    ]
    if not unlocated:
        lines.append("- 无（72 条全部唯一命中并通过 `node --check`）。")
    else:
        for r in unlocated:
            lines.append(f"- `{r['id']}`（`{r['file']}` / `{r['func']}`）：{r['note']}（定位原文：`{r['locate']}`）")
    return "\n".join(lines) + "\n", mismatches, len(unlocated)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="手机页整理后安全网 72 条变异复跑")
    ap.add_argument("--list", action="store_true", help="只列清单并核对定位")
    ap.add_argument("--workers", type=int, default=4, help="并行副本数（最大 4）")
    args = ap.parse_args(argv)
    mod = load_mutate_module()
    if args.list:
        return list_locations(mod)
    equiv = json.loads(EQUIV_JSON.read_text(encoding="utf-8"))
    expected = parse_expected_after()
    results = run_all(mod, args.workers)
    md, mismatches, missed = format_report(results, equiv, expected)
    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text(md, encoding="utf-8", newline="\n")
    print(f"Wrote {OUT_MD} ({len(results)} mutations, mismatches={mismatches}, unlocated={missed})")
    return 1 if (mismatches or missed) else 0


if __name__ == "__main__":
    raise SystemExit(main())
