# 文档硬伤与环境项复核（2026-11-02）

基线：本仓库 HEAD `a23b652`，工作区干净。以下每条都给了复现命令，行号以此基线为准。

## 1. 公开方法数：24 → 实际 49

`docs/ARCHITECTURE.md:176` 写 `Api 24 个公开方法`，实际 **49**。

```bash
python -c "
import ast
t = ast.parse(open('local/app.py', encoding='utf-8').read())
for n in t.body:
    if isinstance(n, ast.ClassDef) and n.name == 'Api':
        pub = [f.name for f in n.body
               if isinstance(f, ast.FunctionDef) and not f.name.startswith('_')]
        print(len(pub)); print(', '.join(pub))
"
```

49 个全部是 pywebview 桥接入口，从 `clock_snapshot` 到 `accept_terms`。文档停在了早期版本，不是统计口径差异（`Api` 类内非下划线方法，没有歧义空间）。

## 2. 决策篇数：三处口径互相不一致

| 位置 | 写的 | 实际 |
|---|---|---|
| `AGENTS.md:16` | 决策记录（14 篇） | 13 篇文件（001–013） |
| `AGENTS.md:82` | `design/decisions/`（14 篇） | 同上 |
| `design/decisions/README.md` | 索引 12 行（001–012） | 缺 013 |
| `CLAUDE.md` | **没有篇数声明** | 该条不成立 |

```bash
ls design/decisions/ | grep -c '^0'          # 13
grep -cE '^\| \[0[0-9]{2}\]' design/decisions/README.md   # 12
grep -rn '14 篇' AGENTS.md CLAUDE.md          # 只命中 AGENTS.md 两行
```

`CLAUDE.md` 全文只有「读 `design/decisions/` 里与本次改动相关的那篇」，没有任何篇数说法。修订表把 `CLAUDE.md` 一并列入「14 篇写错」，这条需要撤回；它的问题在别处（`只服务本人账号` 之类的表述），不在篇数。

真实状态是：**文件 13 篇、索引 12 行、文档写 14 篇**，三个数都不一样。013 已落盘但没进索引。

## 3. `.Codex/project-config.md`

- 文件存在，4,783 字节，最后修改 2026-10-30 16:14，内容是现行的（`protocol_revision: 2.2.1`、`Agent: gpt-6.1-sol`、任务入口策略与验收命令清单）
- **不在仓库**：`.gitignore:26` 是 `.codex/`，Windows 文件系统大小写不敏感，`.Codex/` 一并被排除；`git ls-files .Codex` 为空
- 结论：「仓库里不存在」成立（它是桌面端未跟踪配置，本共享副本也不含它）；「已废弃」不成立

```bash
git ls-files .Codex          # 空
git check-ignore -v .Codex/project-config.md
```

## 4. `scrub-share.ps1` 的位置

叫 `_bridge` 的目录是存在的，但在共享根目录下，里面只有 `plan-template.yaml` 和 `vm-bootstrap.ps1`，**没有** `scrub-share.ps1`。该脚本在工具目录的 `bridge/` 里，同目录还有 `scrub_inplace.py`。两处都是桌面端工具，不入库，因此这里不写具体盘符路径。收工步骤按「桌面端工具目录 → `bridge/` → `scrub-share.ps1`」定位；`_bridge` 不是它该在的地方。

> 修订（2026-11-03）：本节初稿写「`_bridge` 这个目录不存在」，表述过宽——共享根下确实有 `_bridge/`，只是里面没有这个脚本。现按实际目录结构更正。

## 5. 补充：本共享副本的边界

本副本是被净化过的交付树，因此以下内容按设计不在这里，核对时不要当成缺失：

- `local/data/`、`server/data/`、`server/reports/`（运行时生成）
- `.Codex/`（被 `.gitignore` 排除）
- 桌面端工具目录下的 `bridge/`（在仓库之外）
