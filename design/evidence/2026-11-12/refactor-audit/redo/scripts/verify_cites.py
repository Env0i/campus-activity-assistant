#!/usr/bin/env python3
"""核对 redo/ 下全部 .cites.jsonl 引用条目（计划 20261113-refactor-audit-redo 的 F1、F2）。

用法（从仓库任意位置执行都行，脚本自己找仓库根）：
    py -3.12 -X utf8 design/evidence/2026-11-12/refactor-audit/redo/scripts/verify_cites.py
    py -3.12 -X utf8 .../verify_cites.py --self-test     # 三条故意写错的样例必须被拦下

口径（每一步在核什么）：
1. 每行一条 JSON，字段 id、file、start、end、excerpt、claim、kind；kind 不是「事实」时 missing 必填。
2. file 是仓库根起的路径（不以 / 开头、不含反斜杠和盘符、不含 ..），用 git show 7e2d31c:<file> 取基线内容。
3. start、end 是正整数闭区间，start <= end，跨度（end-start+1）不超过 15，end 不超过文件总行数。
4. excerpt 至少 12 个字符，并且在 start-end 这几行拼起来的文本里恰好出现一次（逐字，不做空白归一）。
5. kind 只能是 事实 / 推测 / 需测试定；claim 非空。
6. id 在全部文件中不能重复。
7. 范围只有 redo/ 顶层（不递归，子目录如 audit/、别的执行方的目录都不算）：顶层 *.cites.jsonl 与顶层 *.md。
   md 里写的 [[条目id]] 必须都存在；反引号里写的条目 id（如 `DSK-409g`）也必须存在；
   md 里不许出现裸行号：「文件.py:123」「`文件.py` 123」「文件.py 第 123 行」「文件.py 123」都算（README.md 讲格式处除外）。
8. 输出通过数、失败清单；有任何失败退出码为 1。
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

BASE = "7e2d31c"
KINDS = ("事实", "推测", "需测试定")
MAX_SPAN = 15
MIN_EXCERPT = 12
ID_RE = re.compile(r"\[\[([A-Za-z]+-\d+[A-Za-z0-9-]*)\]\]")
EXTS = "py|js|mjs|md|html|json|yaml|bat"
RAW_LINE_RES = [
    re.compile(r"[\w./-]+\.(?:%s):\d+" % EXTS),                       # 文件.py:123
    re.compile(r"[\w./-]+\.(?:%s)`?\s*[（(]?第?\s*\d{2,}" % EXTS),        # 文件.py 123 / `文件.py` 123 / 文件.py 第 123 行
]
BACKTICK_ID_RE = re.compile(r"`((?:DSK|PHN|RUL|GRB|PRE)-\d+[A-Za-z0-9-]*)`")
RAW_LINE_ALLOW = {"README.md"}

_cache = {}


def repo_root(start):
    out = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=start,
                         capture_output=True, text=True, check=True)
    return Path(out.stdout.strip())


def baseline_lines(root, rel):
    """取基线文件的行列表（按 \\n 切，去掉行尾 \\r）；取不到返回 None。"""
    if rel in _cache:
        return _cache[rel]
    p = subprocess.run(["git", "show", "%s:%s" % (BASE, rel)], cwd=root, capture_output=True)
    if p.returncode != 0:
        _cache[rel] = None
        return None
    text = p.stdout.decode("utf-8", errors="replace")
    lines = [ln.rstrip("\r") for ln in text.split("\n")]
    if lines and lines[-1] == "":
        lines.pop()  # 文件末尾的换行不算一行
    _cache[rel] = lines
    return lines


def check_entry(e, get_lines):
    """返回这一条的错误列表（空表示通过）。get_lines(file) -> 行列表或 None。"""
    errs = []
    for k in ("id", "file", "start", "end", "excerpt", "claim", "kind"):
        if k not in e:
            errs.append("缺字段 " + k)
    if errs:
        return errs
    f = e["file"]
    if not isinstance(f, str) or f.startswith("/") or "\\" in f or ".." in f.split("/") or re.match(r"^[A-Za-z]:", f):
        errs.append("file 必须是仓库根起的相对路径")
    s, t = e["start"], e["end"]
    if not (isinstance(s, int) and isinstance(t, int)) or isinstance(s, bool) or isinstance(t, bool):
        errs.append("start、end 必须是整数")
        return errs
    if s < 1 or t < s:
        errs.append("行号区间不合法 %s-%s" % (s, t))
    elif t - s + 1 > MAX_SPAN:
        errs.append("跨度 %d 超过 %d 行" % (t - s + 1, MAX_SPAN))
    if e["kind"] not in KINDS:
        errs.append("kind 不合法：%r" % (e["kind"],))
    elif e["kind"] != "事实" and not str(e.get("missing") or "").strip():
        errs.append("kind=%s 必须写 missing（缺的是哪一环）" % e["kind"])
    if not str(e["claim"]).strip():
        errs.append("claim 为空")
    ex = e["excerpt"]
    if not isinstance(ex, str) or len(ex) < MIN_EXCERPT:
        errs.append("excerpt 少于 %d 个字符" % MIN_EXCERPT)
    if errs:
        return errs
    lines = get_lines(f)
    if lines is None:
        return ["基线里没有这个文件：" + f]
    if t > len(lines):
        return ["行号越界：end=%d，文件共 %d 行" % (t, len(lines))]
    seg = "\n".join(lines[s - 1:t])
    n = seg.count(ex)
    if n == 0:
        errs.append("excerpt 不在 %d-%d 行里" % (s, t))
    elif n > 1:
        errs.append("excerpt 在 %d-%d 行里出现 %d 次，不能唯一定位" % (s, t, n))
    return errs


def load_entries(redo):
    """返回 [(来源文件, 行号, 条目或 None, 解析错误)]。"""
    out = []
    for p in sorted(redo.glob("*.cites.jsonl")):
        for i, raw in enumerate(p.read_text(encoding="utf-8").split("\n"), 1):
            if not raw.strip():
                continue
            try:
                out.append((p, i, json.loads(raw), None))
            except ValueError as ex:
                out.append((p, i, None, "JSON 解析失败：%s" % ex))
    return out


def run(redo, root):
    get = lambda f: baseline_lines(root, f)
    fails = []
    ok = 0
    seen = {}
    per_file = {}
    kinds = {}
    for p, i, e, perr in load_entries(redo):
        tag = "%s:%d" % (p.name, i)
        if perr:
            fails.append((tag, "?", [perr]))
            continue
        errs = check_entry(e, get)
        eid = e.get("id", "?")
        if eid in seen:
            errs.append("id 重复，另一处在 " + seen[eid])
        else:
            seen[eid] = tag
        if errs:
            fails.append((tag, eid, errs))
        else:
            ok += 1
            per_file[p.name] = per_file.get(p.name, 0) + 1
            kinds[e["kind"]] = kinds.get(e["kind"], 0) + 1
    # md 里的 [[id]] 与裸行号
    md_refs = 0
    used = set()
    for p in sorted(redo.glob("*.md")):
        txt = p.read_text(encoding="utf-8")
        if p.name not in RAW_LINE_ALLOW:
            for m in BACKTICK_ID_RE.finditer(txt):
                if m.group(1) not in seen and not m.group(1).endswith("xx"):   # DSK-1xx 这类是编号规律的说明，不是具体 id
                    fails.append((p.name, m.group(1), ["md 里反引号写的条目 id 不存在"]))
        for m in ID_RE.finditer(txt):
            md_refs += 1
            used.add(m.group(1))
            if m.group(1) not in seen:
                fails.append((p.name, m.group(1), ["md 引用了不存在的条目 id"]))
        if p.name not in RAW_LINE_ALLOW:
            for rx in RAW_LINE_RES:
                for m in rx.finditer(txt):
                    fails.append((p.name, m.group(0), ["md 里写了裸行号，应改成 [[条目id]]"]))
    unused = sorted(set(seen) - used)
    print("引用条目通过 %d 条，失败 %d 条；md 里的 [[id]] 引用 %d 处；未被 md 引用的条目 %d 条" % (
        ok, len(fails), md_refs, len(unused)))
    print("按文件通过数：" + "，".join("%s=%d" % kv for kv in sorted(per_file.items())))
    print("按 kind 通过数：" + "，".join("%s=%d" % kv for kv in sorted(kinds.items())))
    for tag, eid, errs in fails:
        print("失败  %s  %s  %s" % (tag, eid, "；".join(errs)))
    return 1 if fails else 0


def self_test(root):
    """三条故意写错的样例必须被拦下，再加一条正确样例必须通过。"""
    get = lambda f: baseline_lines(root, f)
    good_line = get("local/ui/state/time.js")
    assert good_line, "取不到样例文件"
    idx = next(i for i, ln in enumerate(good_line, 1) if "function esc" in ln)
    good = {"id": "T-1", "file": "local/ui/state/time.js", "start": idx, "end": idx,
            "excerpt": good_line[idx - 1].strip(), "claim": "样例", "kind": "事实"}
    bad = [
        ("原文不在这几行里", dict(good, excerpt="这段文字根本不在代码里 xyz123")),
        ("行号越界", dict(good, start=99999, end=99999)),
        ("推测没写 missing", dict(good, kind="推测")),
    ]
    all_ok = not check_entry(good, get)
    print("正确样例通过：", all_ok)
    caught = 0
    for name, e in bad:
        errs = check_entry(e, get)
        print("错误样例「%s」被拦下：%s  %s" % (name, bool(errs), errs))
        caught += 1 if errs else 0
    if all_ok and caught == 3:
        print("自检通过：3 条错误样例全部被拦下")
        return 0
    print("自检失败")
    return 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--redo", default=None, help="redo 目录，默认是本脚本的上一级")
    a = ap.parse_args()
    here = Path(__file__).resolve().parent
    root = repo_root(here)
    redo = Path(a.redo).resolve() if a.redo else here.parent
    if a.self_test:
        sys.exit(self_test(root))
    sys.exit(run(redo, root))


if __name__ == "__main__":
    main()
