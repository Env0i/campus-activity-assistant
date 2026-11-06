# CLAUDE.md

@AGENTS.md

项目规则、命令、提交格式都在 `AGENTS.md`。本文件只补 Claude 侧的作业方式。

## 共享主工作区

- 当前工作区就是共享目录下的 `share/code/campus-activity-assistant`，不同协作者可能同时看到同一份文件。
- 开工前和收工后都检查 `git status --short`；发现不是自己改的文件，不要 reset、clean、回滚或覆盖。
- Git 操作可以正常使用，包括 status、diff、branch、pull 和 commit；commit、push、force-push、历史改写、删除 refs、merge 或 reset 等有副作用操作必须先取得用户授权或由 `/plan-execute` 计划明确要求。
- 真实站点地址只通过运行环境的 `SCHOOL_ORIGIN` 提供，不创建或复制真实 `local/config.json`、`server/config.json`。
- 每轮结束用 `pwsh -NoProfile -File scrub-share.ps1` 运行共享桥接目录的脚本，因为 `.claude/` 内容对共享工作区可见。

## 开工前

1. `git log --oneline -5` + `git status --short`，先看清当前状态再动手。
2. 读 `design/decisions/` 里与本次改动相关的那篇。决策已经拍过的事，不要重新设计。
3. 需求有歧义时才问；能自行判断的，写进提交正文的「放弃了什么」。

## 不碰的东西

| 路径 | 原因 |
|---|---|
| `server/config.json` | 本机凭据，这里没有也不需要。要跑就 `cp server/config.example.json server/config.json` |
| `server/data/`、`local/data/` | 运行时数据（登录态、日志、状态）。目录不存在是正常的，程序自己会建 |
| `dist/`、`reports/` | 构建产物与运行产物，不入库 |
| `.git/config`、`.git/hooks` | 共享配置。改坏了同一台机器上的其他工作区也会受影响 |
| `origin` 远端 | push 需要用户审核；未经授权不得 push 或改写远端历史 |

## 不要跑的命令

`git reset --hard`、`git checkout --`、`git clean -xdf`、`git gc --prune=now`、`git filter-repo`、`git push`。

这些会丢别人未提交的工作，或改写共享对象库。

## 这个工作区可能有别人在用

同一个目录可能同时有别的 agent 在改文件。

- **不要 `git add -A`**。只 `git add` 你自己动过的文件。
- **不要替用户提交**。改完停下，把「改了哪些文件、为什么、怎么验证」写清楚交回去。
- 发现工作区里有你没改过的脏文件，不要清理、不要回滚，在报告里列出来即可。

## 测试

```bash
python -m unittest discover -s local/tests -p "test_*.py" -v
python -m pytest server/tests
```

测试临时目录一律放在 `tempfile.gettempdir()` 下面（server 测试也可以用环境变量 `CAMPUS_TEST_ROOT` 指定）。`<tmp>` 只是文档里的占位符，不是路径：夹具里出现 `<tmp>` 字面量就是缺陷，改成 `tempfile.gettempdir()` 不算「改测试路径凑绿」（用户 2026-11-06 定）。

除此之外，**不要**为了变绿去改断言、加 skip 或改测试路径。测试因为环境原因跳过或报错（例如没装 webview 被跳过）时，如实写进报告。

## 收尾

```bash
git bundle create ../handover.bundle --all
```
