# 审计快照（2026-11-04 22:2x）

## 副本位置

```
<审计副本>
```

## 基线（开工核对的三个数）

| 项 | 值 |
|---|---|
| HEAD | `4ec0b3d docs(evidence): A5 复核结论回填 + D9 新发现 N1-N3 入决策清单` |
| 分支 | `main`（== origin/main） |
| `git status --porcelain` 条数 | **27**（未跟踪 0） |
| `git diff --stat` | 27 files changed, +646 / −218 |
| VERSION | 1.2.0 |
| git tag | **0 个**（本机无 `v1.1.1` 标签，L5 只能记 blocked） |
| 体积 | 109 MB |

## 与主树的关系

副本的 `.git` 是**独立目录**（不是 `git worktree` 的 `.git` 文件），因此：

- 副本里 `git commit` **只写副本自己的对象库**，主树完全不受影响；
- 主树 `<主树>` 仍是 27 项未提交，一字节未动；
- 副本的 `origin` 仍指向 GitHub，但 `/goal` 已禁止 push。

## 复制时排除的东西（有意为之）

| 排除 | 原因 |
|---|---|
| `dist/`（1.1 GB） | 构建产物；含 60,026,666 字节的旧安装包，与本次五层审计无关 |
| `local/data/` | 运行时数据，含 `session.json` 明文 token——**复制等于多造一份凭据**，`/goal` 也禁止读取 |
| `server/data/` | 同上（本机本就不存在） |
| `.pytest_cache/` | 缓存 |

所以副本里**没有** `local/data`、`server/data`、`dist` 三个目录。若某一层确实需要真包（例如 L5 想跑 `--runtime-check`），对主树 `dist/` 做**只读**访问即可，不要在副本里补。

## 为什么不用 `git worktree add`

`git worktree add` 只能给出**已提交**的树，那 27 项未提交改动不在里面；要拿到它就得 `git stash` 一次——那会动到主树的工作区，属于未经授权的副作用。完整副本既含 `.git` 又含 27 项改动，行为上等同于一个独立可提交的 worktree，且零风险。
