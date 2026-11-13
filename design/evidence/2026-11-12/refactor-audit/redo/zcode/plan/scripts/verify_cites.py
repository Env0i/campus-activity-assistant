#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""F1/F2 引用条目核对脚本（20261113 zcode 重做轮）。

用法（在仓库内任意目录执行均可，git show 会自动定位仓库）:
  python verify_cites.py <a.cites.jsonl> <a.md> [<b.cites.jsonl> <b.md> ...]
      逐条核对 .cites.jsonl；.md 与它前面最近的一个 .cites.jsonl 配对，
      核对 md 里 [[id]] 引用的条目是否都存在。
  python verify_cites.py --selftest
      自检：一条正确样例 + 三条故意写错的样例（原文不在 / 行号越界 /
      推测缺 missing），三条都必须被拦下才算自检通过。

可选参数:
  --baseline-root <目录>   用 git archive 7e2d31c 导出的基线树读文件；
                           缺省用 git show 7e2d31c:<路径>。

核对规则（计划 decisions F1/F2）:
  - 必填字段: id, file, start, end, excerpt, claim, kind
  - id 同一文件内唯一
  - file 在基线 7e2d31c 中存在
  - start/end 为正整数, start<=end, 跨度 end-start+1<=15
  - excerpt >=12 字符; 在基线全文中恰好出现一次（可唯一定位）,
    出现位置的起止行都落在 start..end 闭区间内
  - kind ∈ {事实, 推测, 需测试定}; kind 不是"事实"时 missing 必须是非空字符串
  - md 里 [[id]] 引用的条目必须存在; 条目未被 md 引用只记提示不判失败
退出码: 0=全部通过; 2=有失败条目或引用缺失; 3=用法/IO 错误
"""

import argparse
import json
import os
import re
import subprocess
import sys

BASELINE_COMMIT = "7e2d31c"
KINDS = ("事实", "推测", "需测试定")
MIN_EXCERPT = 12
MAX_SPAN = 15
REF_RE = re.compile(r"\[\[([^\[\]\n]+)\]\]")


def norm(text):
    """统一换行符，excerpt 与基线正文都按此口径比较。"""
    return text.replace("\r\n", "\n").replace("\r", "\n")


class Baseline:
    """按需读基线文件，优先 archive 树，缺省 git show。"""

    def __init__(self, baseline_root=None):
        self.baseline_root = baseline_root
        self.cache = {}

    def read(self, rel):
        if rel in self.cache:
            return self.cache[rel]
        if self.baseline_root:
            path = os.path.join(self.baseline_root, *rel.split("/"))
            if not os.path.isfile(path):
                raise FileNotFoundError(rel)
            with open(path, "rb") as handle:
                data = handle.read()
        else:
            proc = subprocess.run(
                ["git", "show", "%s:%s" % (BASELINE_COMMIT, rel)],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if proc.returncode != 0:
                raise FileNotFoundError(rel)
            data = proc.stdout
        text = norm(data.decode("utf-8", errors="replace"))
        self.cache[rel] = text
        return text


def line_at(text, pos):
    return text.count("\n", 0, pos) + 1


def total_lines(text):
    return text.count("\n") + (0 if text.endswith("\n") or not text else 1)


def check_entry(entry, text):
    """核对单条条目，返回错误列表（空列表=通过）。"""
    errs = []
    if not isinstance(entry, dict):
        return ["不是 JSON 对象"]
    for field in ("id", "file", "start", "end", "excerpt", "claim", "kind"):
        if field not in entry:
            errs.append("缺字段 %s" % field)
    if errs:
        return errs
    if not isinstance(entry["id"], str) or not entry["id"].strip():
        errs.append("id 为空")
    if not isinstance(entry["file"], str) or not entry["file"].strip():
        errs.append("file 为空")
    elif "\\" in entry["file"] or entry["file"].startswith("/"):
        errs.append("file 应为仓库根起的相对路径（正斜杠）")
    for field in ("start", "end"):
        value = entry[field]
        if isinstance(value, bool) or not isinstance(value, int):
            errs.append("%s 不是整数" % field)
    if not errs:
        start, end = entry["start"], entry["end"]
        if start < 1 or end < 1:
            errs.append("行号必须从 1 起")
        elif start > end:
            errs.append("start 大于 end")
        elif end - start + 1 > MAX_SPAN:
            errs.append("跨度 %d 行，超过上限 %d" % (end - start + 1, MAX_SPAN))
    if not isinstance(entry["excerpt"], str) or len(entry["excerpt"]) < MIN_EXCERPT:
        errs.append("excerpt 缺失或不足 %d 个字符" % MIN_EXCERPT)
    if not isinstance(entry["claim"], str) or not entry["claim"].strip():
        errs.append("claim 为空")
    kind = entry["kind"]
    if kind not in KINDS:
        errs.append("kind 必须是 事实/推测/需测试定 之一")
    elif kind != "事实":
        missing = entry.get("missing")
        if not isinstance(missing, str) or not missing.strip():
            errs.append("kind=%s 却缺非空 missing" % kind)
    # 位置核对（前面有结构性错误时正文可能读不了，跳过）
    if any("file" in e or "行号" in e or "start" in e or "end" in e or "跨度" in e
           for e in errs):
        return errs
    try:
        text = BASELINE.read(entry["file"])
    except FileNotFoundError:
        errs.append("基线中不存在该文件")
        return errs
    excerpt = norm(entry["excerpt"])
    nlines = total_lines(text)
    if start > nlines or end > nlines:
        errs.append("行号越界：声明 %d..%d，文件共 %d 行" % (start, end, nlines))
        return errs
    count = text.count(excerpt)
    if count == 0:
        errs.append("原文不在基线中（excerpt 不是文件正文的连续子串）")
    elif count > 1:
        errs.append("excerpt 在全文出现 %d 次，不能唯一定位" % count)
    else:
        pos = text.find(excerpt)
        begin_line = line_at(text, pos)
        end_line = line_at(text, pos + len(excerpt))
        if not (start <= begin_line and end_line <= end):
            errs.append("excerpt 实际落在 %d..%d 行，不在声明的 %d..%d 内"
                        % (begin_line, end_line, start, end))
    return errs


def load_jsonl(path):
    entries, parse_errors = [], []
    with open(path, "rb") as handle:
        raw = handle.read()
    if raw.startswith(b"\xef\xbb\xbf"):
        raw = raw[3:]
    for idx, line in enumerate(raw.decode("utf-8", errors="replace").splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except ValueError as exc:
            parse_errors.append("第 %d 行不是合法 JSON: %s" % (idx, exc))
    return entries, parse_errors


def main(argv):
    if getattr(sys.stdout, "reconfigure", None):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="F1/F2 引用条目核对")
    parser.add_argument("paths", nargs="*", help=".cites.jsonl 与配对的 .md")
    parser.add_argument("--baseline-root", default=None)
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args(argv)

    global BASELINE
    BASELINE = Baseline(args.baseline_root)

    if args.selftest:
        return selftest()
    if not args.paths:
        print("用法: verify_cites.py <a.cites.jsonl> <a.md> ...  或 --selftest")
        return 3

    grand_total = grand_pass = 0
    failures = []
    last_entries = None
    last_name = None
    for path in args.paths:
        if path.endswith(".jsonl"):
            entries, parse_errors = load_jsonl(path)
            seen = {}
            file_fail = list(parse_errors)
            for idx, entry in enumerate(entries, 1):
                eid = entry.get("id") if isinstance(entry, dict) else None
                label = eid if isinstance(eid, str) and eid else "第%d条" % idx
                if isinstance(eid, str) and eid in seen:
                    file_fail.append("%s: id 重复（首次在第 %d 条）" % (eid, seen[eid]))
                elif isinstance(eid, str):
                    seen[eid] = idx
                errs = check_entry(entry, "")
                file_fail.extend("%s: %s" % (label, e) for e in errs)
            last_entries, last_name = entries, path
            total, passed = len(entries), len(entries) - len(
                [f for f in file_fail if not f.startswith("第")])
            grand_total += total
            grand_pass += max(0, total - len([f for f in file_fail]))
            print("== %s: 共 %d 条，失败 %d ==" % (path, total, len(file_fail)))
            for f in file_fail:
                print("  [FAIL] %s" % f)
                failures.append(f)
        elif path.endswith(".md"):
            if last_entries is None:
                print("== %s: 前面没有配对的 .cites.jsonl，跳过 id 核对 ==" % path)
                continue
            with open(path, "rb") as handle:
                md = norm(handle.read().decode("utf-8", errors="replace"))
            have = {e.get("id") for e in last_entries if isinstance(e, dict)}
            refs = REF_RE.findall(md)
            missing = sorted({r for r in refs if r not in have})
            unused = sorted(i for i in have if i not in refs)
            print("== %s（配对 %s）: 引用 %d 处，缺失 id %d，未被引用条目 %d =="
                  % (path, last_name, len(refs), len(missing), len(unused)))
            for mid in missing:
                print("  [FAIL] md 引用了不存在的条目 id: %s" % mid)
                failures.append("%s: 缺失 id %s" % (os.path.basename(path), mid))
            if unused:
                print("  [提示] 未被 md 引用的条目: %s" % ", ".join(unused[:20])
                      + (" ..." if len(unused) > 20 else ""))
            last_entries = None
        else:
            print("忽略无法识别的参数: %s" % path)

    print("---- 合计: %d 条，失败 %d ----" % (grand_total, len(failures)))
    return 2 if failures else 0


def selftest():
    """三条故意写错的样例都必须被拦下，一条正确样例必须通过。"""
    fake = norm("\n".join([
        "L1 alpha beginning",
        "L2 beta gamma",
        "L3 delta epsilon zeta",
        "L4 eta theta iota",
        "L5 kappa lambda mu",
        "L6 nu xi omicron",
        "L7 pi rho sigma",
        "L8 tau upsilon phi",
        "L9 chi psi omega",
        "L10 aa bb cc dd",
        "L11 ee ff gg hh",
        "L12 the final line",
    ]) + "\n")
    cases = [
        ("正确样例", {
            "id": "ok-001", "file": "fake.txt", "start": 3, "end": 4,
            "excerpt": "delta epsilon zeta\nL4 eta theta",
            "claim": "假文件第 3-4 行内容", "kind": "事实"}, 0),
        ("错误样例一：原文不在", {
            "id": "bad-001", "file": "fake.txt", "start": 1, "end": 2,
            "excerpt": "这句原文基线里根本不存在",
            "claim": "伪造的原文", "kind": "事实"}, 1),
        ("错误样例二：行号越界", {
            "id": "bad-002", "file": "fake.txt", "start": 99, "end": 100,
            "excerpt": "L1 alpha beginning",
            "claim": "行号超出文件行数", "kind": "事实"}, 1),
        ("错误样例三：推测缺 missing", {
            "id": "bad-003", "file": "fake.txt", "start": 5, "end": 6,
            "excerpt": "kappa lambda mu\nL6 nu xi",
            "claim": "推测却没写缺哪一环", "kind": "推测"}, 1),
    ]
    # 给自检注入假基线：check_entry 通过 BASELINE.read 拿正文
    BASELINE.cache["fake.txt"] = fake

    ok = True
    for name, entry, expect_min in cases:
        errs = check_entry(entry, "")
        passed = (len(errs) == 0) if expect_min == 0 else (len(errs) >= expect_min)
        print("[%s] %s -> %s" % ("PASS" if passed else "FAIL", name,
                                 "无错误，通过" if not errs else "; ".join(errs)))
        ok = ok and passed
    print("自检%s：三条故意写错的样例都被拦下、正确样例通过"
          % "通过" if ok else "自检失败")
    return 0 if ok else 2


if __name__ == "__main__":
    BASELINE = None  # main/selftest 里初始化
    sys.exit(main(sys.argv[1:]))
