# -*- coding: utf-8 -*-
"""把五份清点脚本的输出汇成 inventory.md 的正文，打到标准输出。

从仓库根运行（inventory.md 就是这条命令的输出，可以直接比对）：
    py -3.12 design/evidence/2026-11-12/refactor-audit/scripts/build_inventory.py > <临时目录>/inventory.md

不写仓库。各脚本的口径见上一级目录的 README.md。
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REL = "design/evidence/2026-11-12/refactor-audit/scripts"

PARTS = [
    ("一、大小分布（C1 ③）", [sys.executable, str(HERE / "measure.py")], f"py -3.12 {REL}/measure.py"),
    ("二、后端跨层 import（C1 ② 后端）", [sys.executable, str(HERE / "py_layers.py")],
     f"py -3.12 {REL}/py_layers.py"),
    ("三、Python 隐式状态（C1 ④）", [sys.executable, str(HERE / "py_state.py")],
     f"py -3.12 {REL}/py_state.py"),
    ("四、app.py 再导出与测试补丁（C3）", [sys.executable, str(HERE / "app_reexports.py")],
     f"py -3.12 {REL}/app_reexports.py"),
    ("五、前端全局依赖、跨层引用与可变全局（C2、C1 ② 前端、C1 ④）",
     ["node", str(HERE / "globals.mjs")], f"node {REL}/globals.mjs"),
]

HEADER = """# 清点结果（inventory）

- **基线提交**：`{head}`。所有行号以它为准。
- **执行日期**：2026-11-12（北京时间）。
- **性质**：只有脚本数出来的事实，不下判断。判断在 `code-issues.md` 和 `ui-states.md`。
- **口径**：见 `README.md`。每一节开头给了复跑命令，都从仓库根执行。
- **本文件怎么来的**：`py -3.12 {rel}/build_inventory.py` 的标准输出，原样保存。复跑后逐字相同才算一致。

## 读数前要知道的

1. **「产品」两个字只表示「不是测试」**。`tools/` 下的发版和 QA 脚本、`local/build/` 下的打包脚本、`server/scripts/dev/` 都算在「产品 Python」里。定大小参考值时主要看「本机版 Python」和「本机版前端」两行。
2. **函数行数是物理行**，含空行、注释和文档字符串；嵌套函数既单独算，也计入外层。
3. **JS 的表达式体箭头函数没有计入**，所以 JS 的 P50 偏大；带花括号体的回调（`forEach(x => {{ … }})`）计入了，名字是 `<anonymous@行号>`。
4. **前端的「引用」按名字匹配**，已经排除了被函数参数或局部变量遮住的同名标识符，但没有做完整的作用域分析。
5. **`Api` 属性的写入点要把第三节的两张表加起来看**：`Api` 自己的方法里的赋值，加上应用层服务从外面的赋值。
6. **测试对 `app` 模块和 `Api` 实例的用法是按变量名认的**（`app`、`local_app`、`api` 等），夹具换了名字就数不到。
"""


def demote(text: str) -> str:
    """把子脚本输出里的标题降一级，好放进总文件的二级标题下面。代码块里的 # 不动。"""
    out = []
    fenced = False
    for line in text.splitlines():
        if line.startswith("```"):
            fenced = not fenced
        if not fenced and line.startswith("#"):
            line = "#" + line
        out.append(line)
    return "\n".join(out)


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", newline="\n")
    head = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True,
                          text=True, check=True).stdout.strip()
    print(HEADER.format(head=head, rel=REL))
    for title, cmd, shown in PARTS:
        proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", check=True)
        body = demote(proc.stdout.rstrip("\n"))
        # 子脚本自己的一级标题降级后是二级，和这里的节标题重复，去掉第一行。
        lines = body.split("\n")
        if lines and lines[0].startswith("## "):
            lines = lines[1:]
        print(f"## {title}\n")
        print(f"复跑：`{shown}`")
        print("\n".join(lines).rstrip("\n"))
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
