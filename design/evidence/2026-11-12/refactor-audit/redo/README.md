# 重构审计补充轮重做（redo）

- **计划**：`20261113-refactor-audit-redo`（Plan Protocol 2.2.1）。重做补充轮的 A–D 四块，不重做第一轮的数字清点。
- **基线提交**：`7e2d31c`（tag v1.2.2）。本目录所有引用都以它为准，用 `git show 7e2d31c:<路径>` 取内容；不读工作区里的产品文件。
- **性质**：只读代码，不改产品代码，不改第一轮、补充轮、`review/` 的任何文件。

## 盲做规则

阶段一的 T1–T5 交付之前，不读 `supplement/**`、`review/**`、`.claude/results/` 里第一轮与补充轮的子模型报告和结果文件；只读产品代码与第一轮的 `README.md`、`state-trace.md`、`ui-states.md`、`code-issues.md`、`inventory.md`。T6 才打开它们对账。

## 引用条目格式（F1）

每份交付物的事实都放在同名的 `.cites.jsonl` 里，一行一条 JSON：

| 字段 | 含义 |
|---|---|
| `id` | 条目编号，全目录唯一，形如 `DSK-12`、`PHN-3` |
| `file` | 仓库根起的路径，不含盘符和主机路径 |
| `start`、`end` | 基线行号，闭区间，跨度不超过 15 行 |
| `excerpt` | 这几行里能唯一定位的一段原文，逐字照抄，至少 12 个字符 |
| `claim` | 这段代码说明了什么，一句话 |
| `kind` | `事实` / `推测` / `需测试定` |
| `missing` | `kind` 不是事实时必填：缺的是哪一环 |

样例（取自 `desktop.cites.jsonl` 的格式，字段值为示意）：

```json
{"id": "DSK-0", "file": "local/ui/controllers/bridge.js", "start": 6, "end": 6, "excerpt": "function api(name, ...args) {", "claim": "桥接入口 api 不带超时参数", "kind": "事实"}
```

md 交付物里引用事实时只写 `[[条目id]]`，不另写 `文件:行号`；`verify_cites.py` 会拦下 md 里的裸行号（本 README 讲格式处除外）。

## 核对脚本（F2）

```bash
# 从仓库任意位置执行；失败时退出码非 0
py -3.12 -X utf8 design/evidence/2026-11-12/refactor-audit/redo/scripts/verify_cites.py
# 三条故意写错的样例（原文不在、行号越界、推测不写 missing）必须被拦下
py -3.12 -X utf8 design/evidence/2026-11-12/refactor-audit/redo/scripts/verify_cites.py --self-test
```

脚本检查：字段齐全；`file` 是相对路径；行号区间合法且跨度不超过 15 行、不越界；`excerpt` 不少于 12 个字符且在该区间内恰好出现一次；`kind` 与 `missing` 齐全；`id` 不重复；md 里的 `[[id]]` 都存在。脚本只能证明「原文在这几行里」，「这一行真是这个意思」靠每个任务的抽查（见阶段结果文件的 `spot_checks`）。

## 三个阶段

| 阶段 | 任务 | 谁做 |
|---|---|---|
| 一、正常任务 | T0 脚本与格式，T1 桌面复核，T2 手机页，T3 三端规则，T4 grab.py 输出协议，T5 重构前置，T6 对账 | 主执行方 |
| 二、对抗审计 | AA1 事实核对，AA2 漏项审计 | 两个互相独立的 Haiku 子智能体，意见放 `audit/` |
| 三、审计返修 | T7 逐条处理意见，写最终结果 | 主执行方 |

## 编号规则

- 引用条目：`DSK-`（桌面）、`PHN-`（手机页）、`RUL-`（三端规则）、`GRB-`（grab.py）、`PRE-`（重构前置）。
- 新发现的界面缺陷从 `V1` 起，代码问题从 `W1` 起；第一轮的 U1–U14、补充轮的 U15–U20 和 S1–S3 不沿用，对应关系在 T6 的 `reconcile.md` 里写清。
- 结论分类：属实 / 不属实 / 有条件属实 / 需测试定。「需测试定」的条目必须写出要补的那条测试。

## 目录

| 文件 | 内容 |
|---|---|
| `scripts/verify_cites.py` | 引用核对脚本 |
| `desktop.md` | T1 桌面复核 |
| `phone.md`、`scripts/phone_model_fields.mjs` | T2 手机页状态追踪 |
| `rules.md` | T3 三端规则比对 |
| `grab.md`、`scripts/grab_outputs.py` | T4 grab.py 输出协议 |
| `prereq.md`、`scripts/esc_sites.mjs` | T5 重构前置清点 |
| `reconcile.md` | T6 对账 |

各阶段交付后在下面追加小结。

## 阶段小结

### 阶段一小结（T0 到 T6，主执行方）

- 交付：`desktop.md`、`phone.md`、`rules.md`、`grab.md`、`prereq.md`、`reconcile.md`，各带同名 `.cites.jsonl`（`reconcile.md` 只写对账，不带引用文件），脚本六个：`verify_cites.py`、`phone_model_fields.mjs`、`grab_outputs.py`、`esc_sites.mjs`、`api_methods.py`、`string_names.py`。
- `verify_cites.py` 通过 1060 条引用，失败 0 条（desktop 424、phone 292、prereq 194、rules 88、grab 62；事实 1056、推测 2、需测试定 2）。
- 需要优先处理的疑点：`grab.md` 的 W6（`[retry]` 与「第 N 次提交」的解析要求行首，而 worker 的 `log` 输出带时间戳），代码层事实已写成「事实」条目（审计 AA2-08 之后），只有端到端表现标「需测试定」，要补的最小验证见该文。
- 对账：补充轮与对抗审计共 80 条结论，一致 48、重做推翻 22、补充轮漏 8、重做漏 2（两处已回代码补做）。
- 阶段二（AA1 事实核对、AA2 漏项，两个 Haiku 独立执行）与阶段三（T7 返修）已完成：两份审计共 29 条意见全部已改，处理见 `audit/response.md`；返修后 `verify_cites.py` 通过 1096 条、失败 0 条。上面阶段一的计数是返修前的。

## 附：zcode/ 子目录

- `zcode/` 是另一执行方按同一计划做的第二份独立重做（含它自派的三道对抗审计与攻防辩），只作交叉参考，本目录的结论以顶层五份材料为准。
- 它的事实层可信：698 条引用指挥会话复跑校验 0 失败；AA3-03（成功报名后的有界刷新在基线零测试引用）与测试改造成本实测已被采纳。
- 它漏了 W6（带时间戳的结构行认不出）；`extra/` 下的 mikado 树、接缝方案与「依赖环 ≤3」「state/ 越层 0」两个目标值是它自拟的，未被采纳。
- 它的时间戳与额度口径按它自己的约定写，不作证据。
