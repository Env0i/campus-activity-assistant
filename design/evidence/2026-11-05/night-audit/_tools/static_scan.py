# -*- coding: utf-8 -*-
"""L1 third route: rule-based static scan over ALL tracked files.

Reads `git -c core.quotepath=false ls-files -z` on stdin, scans each text
file for the auditor-specified dangerous patterns, and writes:
  - reports/_tools/static_scan.tsv   one line per file: path, lang, lines, per-rule hit counts
  - reports/_tools/static_scan_hits.txt  detail lines: rule, path:line, matched text (trimmed)

Rules:
  R1 except_pass   py: except ...: pass  /  js: catch (...) {} empty
  R2 bare_except   py: `except:` without exception class
  R3 eval_exec     py: eval(/exec(   js: eval(
  R4 shell_true    py: shell=True
  R5 secret_lit    password/secret/token/api_key/access_key = "literal" (len>=6, triage needed)
  R6 open_no_with  py: `x = open(` assigned without with (heuristic, triage)
  R7 naive_dt      py: datetime.now()/utcnow()/today() without tz, time.localtime

Usage: git -c core.quotepath=false ls-files -z | python -I reports/_tools/static_scan.py
"""
import re
import sys
from pathlib import Path

BINARY_EXT = {".png", ".ico", ".jpg", ".jpeg", ".gif", ".pdf", ".woff", ".ttf", ".isl"}

RULES = [
    ("R1_except_pass", re.compile(r"except\s*(?:[A-Za-z_.]+(?:\s*,\s*[A-Za-z_]+))?(?:\s+as\s+\w+)?\s*:\s*\n\s*pass\b|except[^:\n]*:\s*pass\b|catch\s*\([^)]*\)\s*\{\s*\}")),
    ("R2_bare_except", re.compile(r"^\s*except\s*:")),
    ("R3_eval_exec", re.compile(r"\b(?:eval|exec)\s*\(")),
    ("R4_shell_true", re.compile(r"shell\s*=\s*True")),
    ("R5_secret_lit", re.compile(r"(?i)(?:password|passwd|pwd|secret|token|api[_-]?key|access[_-]?key|app[_-]?secret)\s*[=:]\s*[\"'][^\"']{6,}[\"']")),
    ("R6_open_no_with", re.compile(r"^\s*\w[\w.\[\]]*\s*=\s*open\(")),
    ("R7_naive_dt", re.compile(r"datetime\.now\(\)|datetime\.utcnow\(\)|datetime\.today\(\)|time\.localtime\(")),
]


def lang_of(path):
    p = path.lower()
    if p.endswith(".py"):
        return "py"
    if p.endswith(".js"):
        return "js"
    return "other"


def main():
    raw = sys.stdin.buffer.read().decode("utf-8")
    files = [f for f in raw.split("\0") if f]
    tsv = []
    hits = []
    summary = {}
    for f in files:
        p = Path(f)
        ext = p.suffix.lower()
        if ext in BINARY_EXT:
            tsv.append(f"{f}\tBINARY\t-\t" + "\t".join("NA" for _ in RULES))
            continue
        try:
            text = p.read_bytes().decode("utf-8", errors="replace")
        except OSError:
            tsv.append(f"{f}\tUNREADABLE\t-\t" + "\t".join("ERR" for _ in RULES))
            continue
        lines = text.splitlines()
        counts = [0] * len(RULES)
        for i, line in enumerate(lines, 1):
            for idx, (name, rx) in enumerate(RULES):
                if idx in (1, 4, 5) and lang_of(f) != "py":  # py-only rules
                    continue
                if idx == 0 and lang_of(f) == "js" and "except" in rx.pattern:
                    continue
                if rx.search(line):
                    counts[idx] += 1
                    snippet = line.strip()[:160]
                    hits.append(f"{name}\t{f}:{i}\t{snippet}")
        for idx, (name, _rx) in enumerate(RULES):
            if counts[idx]:
                summary[name] = summary.get(name, 0) + counts[idx]
        tsv.append(f"{f}\t{lang_of(f)}\t{len(lines)}\t" + "\t".join(map(str, counts)))
    out = Path("reports/_tools")
    out.mkdir(parents=True, exist_ok=True)
    (out / "static_scan.tsv").write_text("\n".join(tsv) + "\n", encoding="utf-8")
    (out / "static_scan_hits.txt").write_text("\n".join(hits) + "\n", encoding="utf-8")
    print("files_scanned", len(files))
    for name, _rx in RULES:
        print(name, summary.get(name, 0))


if __name__ == "__main__":
    main()
