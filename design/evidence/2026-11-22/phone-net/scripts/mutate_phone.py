#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""手机页第一组（请求与配对会话）16 个函数的单点变异与行为测试判定。

用法（仓库根，Python 3.12）：
  python design/evidence/2026-11-22/phone-net/scripts/mutate_phone.py --list
  python design/evidence/2026-11-22/phone-net/scripts/mutate_phone.py --baseline
  python design/evidence/2026-11-22/phone-net/scripts/mutate_phone.py --workers 4 --out design/evidence/2026-11-22/phone-net/before.md

@author Author
"""
from __future__ import annotations

import argparse
import ast
import concurrent.futures
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[5]
APP_REL = Path("local/ui/m/app.js")
TEST_REL = Path("local/tests/test_phone_ui.py")
JSSCAN_MJS = REPO / "tools" / "code_shape" / "jsscan.mjs"
PROXY_VARS = ("http_proxy", "HTTP_PROXY", "https_proxy", "HTTPS_PROXY", "all_proxy")

# (编号, 类别, 函数名, 函数内出现次序, 定位原文, 替换后原文)
# 说明：单行定位时若同函数内有缩进不同的重复行，用行首锚定匹配。
MUTATIONS: tuple[tuple[str, str, str, int, str, str], ...] = (
    ("M01", "乙", "readCookie", 1, 'typeof document.cookie === "string" ?', '!(typeof document.cookie === "string") ?'),
    ("M02", "乙", "readCookie", 1, "if (at < 0)", "if (!(at < 0))"),
    ("M03", "乙", "readCookie", 1, "if (part.slice(0, at).trim() !== name)", "if (!(part.slice(0, at).trim() !== name))"),
    ("M04", "乙", "api", 1, 'if (opts.body && typeof opts.body !== "string")', 'if (!(opts.body && typeof opts.body !== "string"))'),
    ("M05", "乙", "api", 1, 'if (opts.method === "POST")', 'if (!(opts.method === "POST"))'),
    ("M06", "乙", "api", 1, "if (fresh) model.csrf = fresh;", "if (!(fresh)) model.csrf = fresh;"),
    ("M07", "甲", "api", 1, "if (fresh) model.csrf = fresh;", "if (fresh) void 0;"),
    ("M08", "乙", "api", 1, "if (model.csrf) opts.headers", "if (!(model.csrf)) opts.headers"),
    ("M09", "乙", "api", 1, 'typeof AbortController === "function" ?', '!(typeof AbortController === "function") ?'),
    ("M10", "乙", "api", 1, "if (controller) {", "if (!(controller)) {"),
    ("M11", "乙", "api", 1, 'if (path === "/api/action")', 'if (!(path === "/api/action"))'),
    ("M12", "乙", "api", 1, "if (resp.status === 401)", "if (!(resp.status === 401))"),
    ("M13", "乙", "api", 1, "if (resp.status === 403)", "if (!(resp.status === 403))"),
    ("M14", "乙", "api", 1, "if (resp.status !== 200 || body.ok === false)", "if (!(resp.status !== 200 || body.ok === false))"),
    ("M15", "乙", "api", 1, "if (controller) clearTimeout(timer);", "if (!(controller)) clearTimeout(timer);"),
    ("M16", "乙", "renderPair", 1, "view.tagTone ?", "!(view.tagTone) ?"),
    ("M17", "乙", "renderPair", 1, "if (d.cls)", "if (!(d.cls))"),
    ("M18", "乙", "renderPair", 1, "view.hasErr ?", "!(view.hasErr) ?"),
    ("M19", "甲", "setPairError", 1, 'model.pairErr = String(text || "");', "void 0;"),
    ("M20", "甲", "beginPairLock", 1, "model.pairLockLeft = Math.max(0, Math.floor(Number(seconds) || 0));", "void 0;"),
    ("M21", "乙", "beginPairLock", 1, "if (model.pairLockLeft > 0)", "if (!(model.pairLockLeft > 0))"),
    ("M22", "甲", "schedulePairTick", 1,
     'model.pairTickTimer = setTimeout(() => {\n      model.pairTickTimer = 0;\n      model.pairLockLeft = PhoneModel.pairTickLeft(model.pairLockLeft);\n      if (model.pairLockLeft > 0) schedulePairTick();\n      else model.pairErr = "";   // UI-F6（原型 lockLeft 归零清 pairErr）：解锁即收回旧错误条\n      renderPair();\n    }, 1000);',
     "void 0;"),
    ("M23", "甲", "schedulePairTick", 1, "model.pairTickTimer = 0;", "void 0;"),
    ("M24", "甲", "schedulePairTick", 1, "model.pairLockLeft = PhoneModel.pairTickLeft(model.pairLockLeft);", "void 0;"),
    ("M25", "乙", "schedulePairTick", 1, "if (model.pairLockLeft > 0)", "if (!(model.pairLockLeft > 0))"),
    ("M26", "甲", "schedulePairTick", 1, 'else model.pairErr = "";', "else void 0;"),
    ("M27", "乙", "stopPairLock", 1, "if (model.pairTickTimer)", "if (!(model.pairTickTimer))"),
    ("M28", "甲", "stopPairLock", 1, "model.pairTickTimer = 0;", "void 0;"),
    ("M29", "甲", "stopPairLock", 1, "model.pairLockLeft = 0;", "void 0;"),
    ("M30", "乙", "applyPairFailure", 1, 'if (error === "locked")', 'if (!(error === "locked"))'),
    ("M31", "乙", "applyPairFailure", 1, 'if (error === "bad_code")', 'if (!(error === "bad_code"))'),
    ("M32", "乙", "pair", 1, "if (model.pairing)", "if (!(model.pairing))"),
    ("M33", "甲", "pair", 1, '^    model.pairErr = "";', "    void 0;"),
    ("M34", "乙", "pair", 1, "if (!code)", "if (!(!code))"),
    ("M35", "甲", "pair", 1, "model.pairing = true;", "void 0;"),
    ("M36", "乙", "pair", 1, "if (status !== 200 || !body.ok)", "if (!(status !== 200 || !body.ok))"),
    ("M37", "甲", "pair", 1, 'model.csrf = String(body.csrf || "");', "void 0;"),
    ("M38", "甲", "pair", 1, "model.paired = true;", "void 0;"),
    ("M39", "甲", "pair", 1, "model.pairOkPending = true;", "void 0;"),
    ("M40", "甲", "pair", 2, '^      model.pairErr = "";', "      void 0;"),
    ("M41", "甲", "pair", 1, "model.pairing = false;", "void 0;"),
    ("M42", "乙", "poll", 1, "if (model.flying)", "if (!(model.flying))"),
    ("M43", "乙", "poll", 1, "if (!model.csrf)", "if (!(!model.csrf))"),
    ("M44", "甲", "poll", 1, 'if (!model.csrf) model.csrf = readCookie("campus_phone_csrf");', "if (!model.csrf) void 0;"),
    ("M45", "甲", "poll", 1, "model.flying = true;", "void 0;"),
    ("M46", "乙", "poll", 1, "force ?", "!(force) ?"),
    ("M47", "乙", "poll", 1, "if (status === 401)", "if (!(status === 401))"),
    ("M48", "乙", "poll", 1, "if (status === 403)", "if (!(status === 403))"),
    ("M49", "乙", "poll", 1, "if (status !== 200)", "if (!(status !== 200))"),
    ("M50", "甲", "poll", 1, "model.lastOkAt = Date.now();", "void 0;"),
    ("M51", "甲", "poll", 1, "model.backoff = 1000;", "void 0;"),
    ("M52", "甲", "poll", 1, "model.paired = true;", "void 0;"),
    ("M53", "甲", "poll", 1, "model.flying = false;", "void 0;"),
    ("M54", "甲", "onPollFail", 1, "model.offlineTries = Number(model.offlineTries || 0) + 1;", "void 0;"),
    ("M55", "甲", "onPollFail", 1, "model.backoff = PhoneModel.nextBackoff(model.backoff);", "void 0;"),
    ("M56", "甲", "onNeedPair", 1, "model.paired = false;", "void 0;"),
    ("M57", "乙", "onNeedPair", 1, "if (model.pollTimer)", "if (!(model.pollTimer))"),
    ("M58", "甲", "onNeedPair", 1, "model.pollTimer = null;", "void 0;"),
    ("M59", "乙", "onNeedPair", 1, "if (model.tickTimer)", "if (!(model.tickTimer))"),
    ("M60", "甲", "onNeedPair", 1, "model.tickTimer = null;", "void 0;"),
    ("M61", "乙", "onForbidden", 1, "if (fresh) model.csrf = fresh;", "if (!(fresh)) model.csrf = fresh;"),
    ("M62", "甲", "onForbidden", 1, "if (fresh) model.csrf = fresh;", "if (fresh) void 0;"),
    ("M63", "乙", "onForbidden", 1, 'code === "bad_csrf"', '!(code === "bad_csrf")'),
    ("M64", "甲", "onForbidden", 1, "model.backoff = PhoneModel.nextBackoff(model.backoff);", "void 0;"),
    ("M65", "乙", "schedule", 1, "if (model.pollTimer)", "if (!(model.pollTimer))"),
    ("M66", "甲", "schedule", 1, "model.pollTimer = null;", "void 0;"),
    ("M67", "乙", "schedule", 1, 'if (typeof document !== "undefined" && document.hidden)', 'if (!(typeof document !== "undefined" && document.hidden))'),
    ("M68", "乙", "schedule", 1, "if (!model.paired || model.flying)", "if (!(!model.paired || model.flying))"),
    ("M69", "甲", "schedule", 1, "model.pollTimer = setTimeout(() => poll(false), PhoneModel.syncDelay(model));", "void 0;"),
    ("M70", "乙", "probeExistingSession", 1, "if (model.probed)", "if (!(model.probed))"),
    ("M71", "甲", "probeExistingSession", 1, "model.probed = true;", "void 0;"),
    ("M72", "乙", "probeExistingSession", 1, 'if (!readCookie("campus_phone_csrf"))', 'if (!(!readCookie("campus_phone_csrf")))'),
)


def clean_env() -> dict[str, str]:
    env = dict(os.environ)
    for k in PROXY_VARS:
        env.pop(k, None)
    return env


def func_ranges(app_path: Path) -> dict[str, tuple[int, int]]:
    node = shutil.which("node")
    if not node:
        raise RuntimeError("node 不可用")
    code = (
        'import { readFileSync } from "node:fs";\n'
        'import { pathToFileURL } from "node:url";\n'
        'const [app, scan] = process.argv.slice(1);\n'
        'const { findFunctions } = await import(pathToFileURL(scan).href);\n'
        'const { funcs } = findFunctions(readFileSync(app, "utf8"));\n'
        'const out = {};\n'
        'for (const f of funcs) if (f.depth === 0 && f.start >= 1367) out[f.name] = [f.start, f.end];\n'
        'process.stdout.write(JSON.stringify(out));\n'
    )
    res = subprocess.run(
        [node, "-e", code, "--input-type=module", str(app_path), str(JSSCAN_MJS)],
        capture_output=True, text=True, encoding="utf-8", check=False,
    )
    if res.returncode != 0:
        res = subprocess.run(
            [node, "--input-type=module", "-", str(app_path), str(JSSCAN_MJS)],
            input=code, capture_output=True, text=True, encoding="utf-8", check=True,
        )
    return {k: tuple(v) for k, v in json.loads(res.stdout).items()}


def test_behavior_map() -> dict[str, bool]:
    tree = ast.parse((REPO / TEST_REL).read_text(encoding="utf-8"))
    out: dict[str, bool] = {}
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name.startswith("test_"):
                    uses_node = any(
                        isinstance(c, ast.Call) and isinstance(c.func, ast.Name) and c.func.id == "run_phone_js"
                        for c in ast.walk(item)
                    )
                    out[f"{node.name}.{item.name}"] = uses_node
    return out


def apply_in_func(text: str, start: int, end: int, locate: str, repl: str) -> str | None:
    lines = text.splitlines(keepends=False)
    head = "\n".join(lines[:start - 1])
    body = "\n".join(lines[start - 1:end])
    tail = "\n".join(lines[end:])
    if locate.startswith("^"):
        pat = re.compile(locate, re.M)
        hits = list(pat.finditer(body))
        if len(hits) != 1:
            return None
        new_body = pat.sub(lambda _m: repl, body, count=1)
    else:
        if body.count(locate) != 1:
            return None
        new_body = body.replace(locate, repl, 1)
    parts = [p for p in (head, new_body, tail) if p]
    return "\n".join(parts) + ("\n" if text.endswith("\n") else "")


def create_archive_zip(zip_path: Path) -> None:
    subprocess.run(
        ["git", "archive", "--format=zip", "--output", str(zip_path), "HEAD"],
        cwd=REPO, check=True, capture_output=True,
    )


def open_replica(zip_path: Path) -> Path:
    root = Path(tempfile.mkdtemp(prefix="phone_mut_"))
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(root)
    dst_test = root / TEST_REL
    dst_test.parent.mkdir(parents=True, exist_ok=True)
    dst_test.write_bytes((REPO / TEST_REL).read_bytes())
    return root


def _parse_running_test(out_text: str) -> list[str]:
    m = re.findall(r"^([A-Za-z0-9_]+)\s+\(([^)]+)\)\s+\.\.\.", out_text, flags=re.M)
    if not m:
        return []
    meth, qual = m[-1]
    parts = qual.split(".")
    cls = parts[-2] if len(parts) >= 2 else ""
    return [f"{cls}.{meth}" if cls else meth]


def run_unittest(root: Path) -> tuple[int, list[str], int]:
    try:
        res = subprocess.run(
            [sys.executable, "-B", "-m", "unittest", "discover", "-s", "local/tests", "-p", "test_phone_ui.py", "-v"],
            cwd=root, env=clean_env(), capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=45,
        )
    except subprocess.TimeoutExpired as exc:
        out_text = (exc.stdout or b"" if isinstance(exc.stdout, bytes) else exc.stdout or "")
        err_text = (exc.stderr or b"" if isinstance(exc.stderr, bytes) else exc.stderr or "")
        if isinstance(out_text, bytes):
            out_text = out_text.decode("utf-8", "replace")
        if isinstance(err_text, bytes):
            err_text = err_text.decode("utf-8", "replace")
        return 124, _parse_running_test(out_text + "\n" + err_text), 0
    out_text = (res.stdout or "") + "\n" + (res.stderr or "")
    fails = re.findall(r"^(?:FAIL|ERROR):\s+([A-Za-z0-9_]+)\s+\(([^)]+)\)", out_text, flags=re.M)
    names = []
    for meth, qual in fails:
        parts = qual.split(".")
        cls = parts[-2] if len(parts) >= 2 else ""
        names.append(f"{cls}.{meth}" if cls else meth)
    skipped = 0
    m = re.search(r"skipped=(\d+)", out_text)
    if m:
        skipped = int(m.group(1))
    return res.returncode, names, skipped


def run_one_in_replica(root: Path, orig_lf: str, ranges: dict[str, tuple[int, int]],
                       bmap: dict[str, bool], mut: tuple) -> dict:
    mid, kind, fn, occur, locate, repl = mut
    app_file = root / APP_REL
    rng = ranges.get(fn)
    if not rng:
        return {"id": mid, "kind": kind, "func": fn, "occur": occur, "locate": locate,
                "replace": repl, "status": "无效", "first_fail": "", "note": "未找到目标函数"}
    mutated = apply_in_func(orig_lf, rng[0], rng[1], locate, repl)
    if mutated is None:
        return {"id": mid, "kind": kind, "func": fn, "occur": occur, "locate": locate,
                "replace": repl, "status": "无效", "first_fail": "", "note": "定位不唯一或未命中"}
    app_file.write_text(mutated, encoding="utf-8", newline="\n")
    node = shutil.which("node")
    chk = subprocess.run([node, "--check", str(app_file)], capture_output=True, text=True, check=False)
    if chk.returncode != 0:
        return {"id": mid, "kind": kind, "func": fn, "occur": occur, "locate": locate,
                "replace": repl, "status": "无效", "first_fail": "", "note": "node --check 失败"}
    code, fails, _ = run_unittest(root)
    if code == 0:
        return {"id": mid, "kind": kind, "func": fn, "occur": occur, "locate": locate,
                "replace": repl, "status": "无人守", "first_fail": "", "note": ""}
    if not fails:
        return {"id": mid, "kind": kind, "func": fn, "occur": occur, "locate": locate,
                "replace": repl, "status": "字面守", "first_fail": "(unknown)", "note": "非零退出但未解析出用例名"}
    behav = [f for f in fails if bmap.get(f, False)]
    status = "行为守" if behav else "字面守"
    return {"id": mid, "kind": kind, "func": fn, "occur": occur, "locate": locate,
            "replace": repl, "status": status, "first_fail": fails[0], "note": ""}


def worker_chunk(zip_path: Path, orig_lf: str, ranges: dict[str, tuple[int, int]],
                 bmap: dict[str, bool], chunk: list[tuple]) -> list[dict]:
    root = open_replica(zip_path)
    results = []
    try:
        for mut in chunk:
            results.append(run_one_in_replica(root, orig_lf, ranges, bmap, mut))
    finally:
        shutil.rmtree(root, ignore_errors=True)
    return results


def list_mutations(ranges: dict[str, tuple[int, int]], orig_lf: str) -> int:
    bad = 0
    for mid, kind, fn, occur, locate, repl in MUTATIONS:
        rng = ranges.get(fn)
        ok = bool(rng and apply_in_func(orig_lf, rng[0], rng[1], locate, repl) is not None)
        if not ok:
            bad += 1
        loc_one = locate.replace("\n", "\\n")
        print(f"{mid}\t{kind}\t{fn}\t#{occur}\t{'OK' if ok else 'MISS'}\t{loc_one} => {repl}")
    print(f"Total: {len(MUTATIONS)} (locate miss: {bad})")
    return 1 if bad else 0


def format_report(results: list[dict], phase: str, equiv: dict[str, str]) -> str:
    counts = {"行为守": 0, "字面守": 0, "无人守": 0, "无效": 0, "等价": 0}
    lines = [
        f"# 第一组（请求与配对会话）变异结论（{phase}）",
        "",
        f"- 范围：16 个函数，甲类（`model.字段` 写换 `void 0`）{sum(1 for r in results if r['kind']=='甲')} 条，乙类（条件 `C` 换 `!(C)`）{sum(1 for r in results if r['kind']=='乙')} 条，共 {len(results)} 条。",
        "",
        "| 编号 | 类 | 函数 | 第几次 | 定位原文 | 替换后原文 | 结论 | 第一条失败用例 |",
        "|---|---|---|---:|---|---|---|---|",
    ]
    equiv_notes = []
    for r in results:
        st = r["status"]
        if st == "无人守" and r["id"] in equiv:
            st = "等价"
            equiv_notes.append((r["id"], r["func"], equiv[r["id"]]))
        counts[st] = counts.get(st, 0) + 1
        loc = r["locate"].replace("\n", " ↵ ").replace("|", "\\|")
        rep = r["replace"].replace("|", "\\|")
        ff = f"`{r['first_fail']}`" if r["first_fail"] else "—"
        lines.append(f"| {r['id']} | {r['kind']} | `{r['func']}` | {r['occur']} | `{loc}` | `{rep}` | {st} | {ff} |")
    lines.extend(["", "## 各类合计", ""])
    for k in ("行为守", "字面守", "无人守", "无效", "等价"):
        lines.append(f"- {k}：{counts[k]}")
    lines.append(f"- 总计：{len(results)}")
    if equiv_notes:
        lines.extend(["", "## 等价判定理由", ""])
        for mid, fn, reason in equiv_notes:
            lines.append(f"- **{mid}**（`{fn}`）：{reason}")
    return "\n".join(lines) + "\n"


def run_parallel(selected: list[tuple], workers: int) -> list[dict]:
    orig_lf = (REPO / APP_REL).read_text(encoding="utf-8").replace("\r\n", "\n")
    ranges = func_ranges(REPO / APP_REL)
    bmap = test_behavior_map()
    tmp_zip_dir = Path(tempfile.mkdtemp(prefix="phone_zip_"))
    zip_path = tmp_zip_dir / "repo.zip"
    try:
        create_archive_zip(zip_path)
        w = max(1, min(4, workers, len(selected)))
        chunks = [selected[i::w] for i in range(w)]
        merged = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=w) as ex:
            futs = [ex.submit(worker_chunk, zip_path, orig_lf, ranges, bmap, ch) for ch in chunks if ch]
            for fut in concurrent.futures.as_completed(futs):
                merged.extend(fut.result())
        order = {m[0]: idx for idx, m in enumerate(MUTATIONS)}
        merged.sort(key=lambda r: order[r["id"]])
        return merged
    finally:
        shutil.rmtree(tmp_zip_dir, ignore_errors=True)


def run_baseline() -> int:
    tmp_zip_dir = Path(tempfile.mkdtemp(prefix="phone_base_"))
    zip_path = tmp_zip_dir / "repo.zip"
    root = None
    try:
        create_archive_zip(zip_path)
        root = open_replica(zip_path)
        code, fails, skipped = run_unittest(root)
        print(f"Baseline: exit={code}, fails={len(fails)}, skipped={skipped}")
        return 0 if (code == 0 and skipped == 0) else 1
    finally:
        if root is not None:
            shutil.rmtree(root, ignore_errors=True)
        shutil.rmtree(tmp_zip_dir, ignore_errors=True)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="手机页第一组变异测试")
    ap.add_argument("--list", action="store_true", help="只列清单并核对定位")
    ap.add_argument("--baseline", action="store_true", help="跑未变异副本基线")
    ap.add_argument("--ids", default="", help="只跑指定编号（逗号分隔）")
    ap.add_argument("--workers", type=int, default=4, help="并行副本数（最大 4）")
    ap.add_argument("--phase", default="补测之前", help="报告阶段标题")
    ap.add_argument("--equiv-json", default="", help="等价判定 JSON 文件路径")
    ap.add_argument("--out", default="", help="输出 Markdown 路径")
    args = ap.parse_args(argv)
    if args.list:
        orig_lf = (REPO / APP_REL).read_text(encoding="utf-8").replace("\r\n", "\n")
        return list_mutations(func_ranges(REPO / APP_REL), orig_lf)
    if args.baseline:
        return run_baseline()
    wanted = {s.strip() for s in args.ids.split(",") if s.strip()}
    selected = [m for m in MUTATIONS if not wanted or m[0] in wanted]
    if not selected:
        print("没有匹配的编号", file=sys.stderr)
        return 1
    equiv = json.loads(Path(args.equiv_json).read_text(encoding="utf-8")) if args.equiv_json else {}
    results = run_parallel(selected, args.workers)
    md = format_report(results, args.phase, equiv)
    if args.out:
        Path(args.out).write_text(md, encoding="utf-8", newline="\n")
        print(f"Wrote {args.out} ({len(results)} mutations)")
    else:
        print(md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
