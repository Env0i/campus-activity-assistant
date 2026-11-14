# -*- coding: utf-8 -*-
"""表 F：工程设施盘点（计划 decisions D8）；表 G：文档数字对账（decisions D9）。

表 F 只查「有没有」与文件名、行数，各给路径或「无」。
表 G 在 AGENTS.md、README.md、local/README.md、docs/ 下的 md 文件里，用本文件顶部的
正则找四类写了具体数字的句子：测试用例个数、Api 方法个数、决策记录篇数、某个源文件的行数。
每句给 文件:行号 与原文，再给当前实测值与量法；量不了的写「未量」。
原文含主机路径时替换为 <主机路径> 并在该行标注，其余字符不动（补充规则 6.7）。

从仓库根运行：
    python -B design/evidence/2026-11-13/refactor-endpoint/scripts/facilities.py
    python -B design/evidence/2026-11-13/refactor-endpoint/scripts/facilities.py --measure tests|api|decisions|lines --file <相对路径>
"""
import ast
import fnmatch
import os
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def _repo_root():
    """先按「脚本位置上推四级」定位仓库根；脚本被复制到别处时改问 git。"""
    cand = HERE.parents[4] if len(HERE.parents) > 4 else None
    if cand is not None and (cand / ".git").exists():
        return cand
    out = subprocess.run(["git", "rev-parse", "--show-toplevel"],
                         cwd=os.getcwd(), capture_output=True)
    if out.returncode == 0:
        return Path(out.stdout.decode("utf-8", "replace").strip())
    raise SystemExit("定位不到仓库根：请从仓库根运行本脚本")


REPO = _repo_root()

# ── 表 G 的四类正则（按 D9 写在顶部）──
RE_TESTS = re.compile(r"\d{3,}\s*(?:个)?\s*(?:例|用例)")
RE_API = re.compile(r"\d+\s*个?\s*(?:公开)?方法")
RE_DECISIONS = re.compile(r"\d+\s*篇")
RE_LINES = re.compile(r"\d{3,}\s*行")
RE_SRC_FILE = re.compile(r"[\w\-./]+\.(?:py|js|mjs)\b")
# 行号引用不算「源文件的行数」：第 N 行、文件:行号 这类写法排除。
RE_LINE_REF = re.compile(r"第\s*\d|[:：]\s*\d{2,}")

# ── 表 G 的「位置引用」排除清单（出处：计划 plan-20261114-refactor-endpoint-evidence-fix 的 decisions D2）──
# docs/superpowers/specs/2026-11-03-architecture-revision-design.md 第 39、121、194 行里的
# 「约 N 行」指「这个函数或常量在文件的第几行附近」，是位置引用，不是「这个文件有多少行」；
# 裁决：这三行都不属于 D9 的四类句子。正表不再输出第 39、121 行（原先被行数正则命中），
# 三行的原文与理由改在「已排除：位置引用」一节列出；行数正则与三位数下限照旧不改。
POSITION_REF_DOCS = (
    ("docs/superpowers/specs/2026-11-03-architecture-revision-design.md", 39),
    ("docs/superpowers/specs/2026-11-03-architecture-revision-design.md", 121),
    ("docs/superpowers/specs/2026-11-03-architecture-revision-design.md", 194),
)
POSITION_REF_SET = set(POSITION_REF_DOCS)

GLOBS_DOC_FILES = ["AGENTS.md", "README.md", "local/README.md"]
REQUIREMENT_GLOB = "requirements*.txt"

CONFIG_CANDIDATES = {
    "mypy": ["mypy.ini", ".mypy.ini"],
    "coverage": [".coveragerc"],
    "eslint": [".eslintrc.js", ".eslintrc.cjs", ".eslintrc.json", ".eslintrc.yml",
               ".eslintrc.yaml", ".eslintrc", "eslint.config.js", "eslint.config.cjs",
               "eslint.config.mjs"],
    "prettier": [".prettierrc", ".prettierrc.json", ".prettierrc.yml", ".prettierrc.yaml",
                 ".prettierrc.js", ".prettierrc.cjs", ".prettierrc.toml",
                 "prettier.config.js", "prettier.config.cjs"],
    "根配置": ["pyproject.toml", "setup.cfg", "package.json", ".editorconfig",
              ".pre-commit-config.yaml"],
}
SECTION_MARKS = {"mypy": "[tool.mypy]", "coverage": "[tool.coverage]"}


def exists_row(name, rels):
    found = [r for r in rels if (REPO / r).exists()]
    return name, (found[0] if len(found) == 1 else
                  ("；".join(found) if found else "无"))


def tracked_text_files():
    out = subprocess.run(
        ["git", "ls-files", "-z"], cwd=str(REPO), capture_output=True, check=True)
    exts = (".py", ".js", ".mjs", ".md", ".toml", ".cfg", ".ini", ".txt",
            ".yaml", ".yml", ".json", ".bat", ".ps1", ".sh", ".html")
    names = out.stdout.decode("utf-8").split("\0")
    return sorted(n for n in names if n and n.endswith(exts))


def requirements_files():
    out = []
    for dirpath, dirnames, filenames in REPO.walk():
        dirnames[:] = [d for d in dirnames if d not in (".git", "node_modules", "dist", "data")]
        for f in fnmatch.filter(filenames, REQUIREMENT_GLOB):
            out.append((dirpath / f).relative_to(REPO).as_posix())
    return sorted(out)


def table_f():
    rows = []
    for group, names in CONFIG_CANDIDATES.items():
        for n in names:
            rows.append(exists_row(n, [n]))
    for tool, mark in SECTION_MARKS.items():
        hit = "无"
        for cand in ("pyproject.toml", "setup.cfg"):
            p = REPO / cand
            if p.exists() and mark in p.read_text(encoding="utf-8", errors="replace"):
                hit = cand
        rows.append((f"{tool} 配置节（pyproject.toml / setup.cfg 内 {mark}）", hit))
    # requirements 文件与未锁版本行
    req_rows = []
    for rel in requirements_files():
        lines = (REPO / rel).read_text(encoding="utf-8", errors="replace").splitlines()
        specs = [ln.strip() for ln in lines
                 if ln.strip() and not ln.strip().startswith("#")]
        unlocked = [s for s in specs if "==" not in s.split(";")[0].split(" ")[0]]
        req_rows.append((rel, len(lines), len(specs), len(unlocked), unlocked))
    hooks = sorted(p.name for p in (REPO / ".githooks").iterdir()) if (REPO / ".githooks").exists() else []
    workflows_dir = REPO / ".github" / "workflows"
    workflows = sorted(p.name for p in workflows_dir.iterdir()) if workflows_dir.exists() else []
    check_py = REPO / "tools" / "code_shape" / "check.py"

    print("## 表 F：工程设施盘点")
    print()
    print("量什么：只查「有没有」。配置文件给路径或「无」；requirements 文件给行数与"
          "未锁到精确版本（没有 ==）的行数与行；.githooks、.github/workflows 给文件名；"
          "release.py 的 --prepare 与单元测试、ruff 的出现位置按字符串查找给 文件:行号。")
    print()
    print("### F1 配置文件有没有")
    print()
    print("| 项目 | 结果 |")
    print("|---|---|")
    for name, res in rows:
        print(f"| {name} | {res} |")
    print()
    print("### F2 requirements 文件")
    print()
    print("| 文件 | 总行数 | 非注释非空行数 | 未锁精确版本行数 | 未锁的行 |")
    print("|---|---|---|---|---|")
    for rel, total, specs, unlocked, unlocked_lines in req_rows:
        disp = "；".join(f"`{s}`" for s in unlocked_lines) if unlocked_lines else "—"
        print(f"| `{rel}` | {total} | {specs} | {unlocked} | {disp} |")
    print()
    print("### F3 hooks 与 CI")
    print()
    print(f"| .githooks 下的文件名 | {'、'.join(f'`{h}`' for h in hooks) if hooks else '无'} |")
    print(f"| .github/workflows 下的文件名 | {'、'.join(f'`{w}`' for w in workflows) if workflows else '无'} |")
    print()
    print("### F4 release.py 与测试、code_shape、ruff")
    print()
    rel_lines = (REPO / "tools" / "release.py").read_text(encoding="utf-8", errors="replace").splitlines()
    test_hits = [(i + 1, ln.strip()) for i, ln in enumerate(rel_lines)
                 if re.search(r"\bunittest\b|\bpytest\b|compileall", ln)]
    prepare_hits = [(i + 1, ln.strip()) for i, ln in enumerate(rel_lines) if "--prepare" in ln]
    print("tools/release.py 里含 unittest / pytest / compileall 的行（判断 --prepare 路径"
          "有没有调用单元测试就看这些行落在哪个分支）：")
    if test_hits:
        for ln, text in test_hits:
            print(f"- tools/release.py:{ln}")
    else:
        print("- 无")
    print()
    print("tools/release.py 里含 --prepare 的行：")
    for ln, _ in prepare_hits:
        print(f"- tools/release.py:{ln}")
    print()
    print(f"tools/code_shape/check.py 存在：{'是（tools/code_shape/check.py）' if check_py.exists() else '无'}")
    print()
    ruff_hits = []
    for name in tracked_text_files():
        try:
            text = (REPO / name).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for i, ln in enumerate(text.splitlines(), 1):
            if re.search("ruff", ln, re.I):
                ruff_hits.append(f"{name}:{i}")
    print(f"ruff 按字符串查找（git 已跟踪的文本文件，大小写不敏感），共 {len(ruff_hits)} 行：")
    for h in ruff_hits:
        print(f"- {h}")
    print()
    print("复跑命令：`python -B design/evidence/2026-11-13/refactor-endpoint/scripts/facilities.py`")


def measure(kind, file_rel=None):
    if kind == "tests":
        counts = {}
        for top in ("local/tests", "server/tests"):
            n = 0
            for p in (REPO / top).rglob("*.py"):
                tree = ast.parse(p.read_text(encoding="utf-8", errors="replace"))
                for node in ast.walk(tree):
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        if node.name.startswith("test_"):
                            n += 1
            counts[top] = n
        print(f"local/tests {counts['local/tests']}；server/tests {counts['server/tests']}；"
              f"合计 {sum(counts.values())}")
    elif kind == "api":
        src = (REPO / "local" / "app.py").read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(src)
        total = public = 0
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == "Api":
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        total += 1
                        if not item.name.startswith("_"):
                            public += 1
        print(f"总数 {total}；非下划线 {public}")
    elif kind == "decisions":
        d = REPO / "design" / "decisions"
        files = [p.name for p in d.glob("*.md") if not p.name.startswith("README")]
        print(len(files))
    elif kind == "lines":
        p = REPO / file_rel
        if not p.exists():
            print("文件当前不存在")
        else:
            text = p.read_text(encoding="utf-8", errors="replace")
            print(len(text.replace("\r\n", "\n").rstrip("\n").split("\n")))
    else:
        raise SystemExit("未知 --measure：" + str(kind))


HOST_PATTERNS = [
    re.compile("(?<![A-Za-z0-9+.-])[A-Za-z]:[\\\\/]"),
    re.compile("(?i)[\\\\/]users?[\\\\/]"),
    re.compile("(?i)appdata[\\\\/]local[\\\\/]temp"),
    re.compile("%" + "TEMP" + "%", re.I),
    re.compile("%" + "USERPROFILE" + "%", re.I),
]


def sanitize(text):
    out = text
    for pat in HOST_PATTERNS:
        out = pat.sub("<主机路径>", out)
    return out


def doc_files():
    names = [n for n in GLOBS_DOC_FILES if (REPO / n).exists()]
    docs = REPO / "docs"
    if docs.exists():
        names += sorted(p.relative_to(REPO).as_posix() for p in docs.rglob("*.md"))
    return names


def table_g():
    print("## 表 G：文档数字对账")
    print()
    print("量什么：AGENTS.md、README.md、local/README.md、docs/ 下的 md 文件里，"
          "写了具体数字的四类句子（正则见脚本顶部）：测试用例个数（3 位以上数字+例/用例）、"
          "Api 方法个数（同一句含 Api）、决策记录篇数（数字+篇）、某个源文件的行数"
          "（3 位以上数字+行，且句里有 .py/.js/.mjs 文件名；「第 N 行」「文件:行号」式引用排除）。"
          "原文含主机路径时替换为 <主机路径> 并标注，其余字符不动。")
    print()
    print("| 文件:行号 | 类别 | 原文 | 实测值 | 量法 |")
    print("|---|---|---|---|---|")
    cmd = "python -B design/evidence/2026-11-13/refactor-endpoint/scripts/facilities.py --measure"
    for rel in doc_files():
        text = (REPO / rel).read_text(encoding="utf-8", errors="replace")
        for i, raw in enumerate(text.splitlines(), 1):
            line = raw.strip()
            if not line:
                continue
            if (rel, i) in POSITION_REF_SET:
                # 位置引用（清单在脚本顶部，出处为本计划 decisions D2）：不进正表，
                # 原文与理由在下方「已排除：位置引用」一节列出。
                continue
            hits = []
            if RE_TESTS.search(line):
                hits.append(("测试用例个数", "--measure tests"))
            if "Api" in line and RE_API.search(line):
                hits.append(("Api 方法个数", "--measure api"))
            if RE_DECISIONS.search(line):
                hits.append(("决策记录篇数", "--measure decisions"))
            if (RE_LINES.search(line) and RE_SRC_FILE.search(line)
                    and not RE_LINE_REF.search(line)):
                hits.append(("源文件行数", None))
            for cat, measure_flag in hits:
                note = ""
                if any(p.search(line) for p in HOST_PATTERNS):
                    note = "（原文含路径，已替换）"
                disp = sanitize(line).replace("|", chr(92) + "|")  # 转义符用 chr(92) 拼，防自检 UNC 规则自命中
                if cat == "源文件行数":
                    tokens = sorted(set(RE_SRC_FILE.findall(line)))
                    vals = []
                    for t in tokens:
                        vv = subprocess.run(
                            [sys.executable, "-B",
                             "design/evidence/2026-11-13/refactor-endpoint/scripts/facilities.py",
                             "--measure", "lines", "--file", t],
                            cwd=str(REPO), capture_output=True, check=True)
                        vals.append(f"`{t}` = {vv.stdout.decode('utf-8').strip()}")
                    val = "；".join(vals) if vals else "未量"
                    m = f"{cmd} lines --file <原文里的文件>"
                else:
                    out = subprocess.run(
                        [sys.executable, "-B",
                         "design/evidence/2026-11-13/refactor-endpoint/scripts/facilities.py",
                         "--measure", measure_flag.split()[-1]],
                        cwd=str(REPO), capture_output=True, check=True)
                    val = out.stdout.decode("utf-8").strip()
                    m = f"{cmd} {measure_flag.split()[-1]}"
                print(f"| `{rel}:{i}` | {cat} | {disp}{note} | {val} | `{m}` |")
    print()
    print("### 已排除：位置引用")
    print()
    print("量什么：docs/superpowers/specs/2026-11-03-architecture-revision-design.md 第 39、121、194 行里的"
          "「约 N 行」指「这个函数或常量在文件的第几行附近」，是位置引用，不是「这个文件有多少行」，"
          "按计划 plan-20261114-refactor-endpoint-evidence-fix 的 decisions D2，这三行不属于 D9 的四类句子。"
          "第 39、121 行原先被行数正则命中、在正表里，本节把它们移出正表；第 194 行的「约 61 行」低于"
          "三位数下限，原本就未进正表，也列入本节备查。行数正则（含三位数下限）照旧未改；"
          "排除清单写在脚本顶部注释。")
    print()
    print("| 文件:行号 | 类别 | 原文 | 排除理由 |")
    print("|---|---|---|---|")
    for rel2, ln2 in POSITION_REF_DOCS:
        line2 = (REPO / rel2).read_text(encoding="utf-8", errors="replace").splitlines()[ln2 - 1].strip()
        disp2 = sanitize(line2).replace("|", chr(92) + "|")
        print(f"| `{rel2}:{ln2}` | 位置引用 | {disp2} | "
              f"「约 N 行」指函数或常量在文件中的位置，不是文件总行数，不属于 D9 的四类句子 |")
    print()
    print("复跑命令：`python -B design/evidence/2026-11-13/refactor-endpoint/scripts/facilities.py` "
          "（表 G 段）；实测值复跑用上表「量法」列。")


def main():
    if "--measure" in sys.argv:
        kind = sys.argv[sys.argv.index("--measure") + 1]
        file_rel = None
        if "--file" in sys.argv:
            file_rel = sys.argv[sys.argv.index("--file") + 1]
        measure(kind, file_rel)
        return
    table_f()
    print()
    table_g()


if __name__ == "__main__":
    main()
