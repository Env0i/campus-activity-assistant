# 交接：ZCode 夜间两轮（2026-11-05）

## 0. 这份文件是什么

一个隔离副本里跑的两轮无人值守任务的交接件。副本 = 主树 `4ec0b3d` 的完整拷贝（含 `.git` 与当时 27 项未提交改动），位置 `<审计副本>`，分支 `chore/standardize-20261105`。

- 提交包：`design/evidence/2026-11-05/night-audit/wip-standardize-20261105.bundle`（39 KB，`4ec0b3d..chore/standardize-20261105`）
- 报告与补丁：本目录（`design/evidence/2026-11-05/night-audit/`）
- 主树未被修改（仅本目录为新增未跟踪文件）

## 1. 两轮做了什么

第一轮 = 五层审计（代码 / 原型 / 契约文档 / 决策记录 / 发布口径）；第二轮 = 全量标准化（先出 `STANDARD.md`，再按 8 批整理）。

| 项 | 数字 |
|---|---|
| 受跟踪文件 | 469 个 / 131,999 行 |
| 覆盖台账 | `COVERAGE.tsv` 469 行；`STANDARDIZATION.md` 548 行（合规 147 / 已改 53 / 保留 120 / N-A 149） |
| 发现 | 缺陷 8（修 5）、风险 6、漂移 72、blocked 5 |
| 提交 | 26 笔：1 笔行为修复（`099ded3`）+ 25 笔改名/注释/文档 |
| 补丁 | `PATCHES/` 31 个，`std-1` → `std-19` |
| 测试 | 全量 1699 OK（1 已知 flake）、server 122 passed、node 45 |

## 2. 代码：只建议取这些

| 取什么 | 内容 | 为什么 |
|---|---|---|
| `099ded3` | 五个真修复（`<tmp>` 夹具映射、时钟单读、组件服务惰性、update 文案、relogin 空 flow 去重） | 唯一改变行为的提交，12 文件 +61/−21 |
| `PATCHES/fix-A..E-*.patch` | 同上的分件补丁 | 便于按条评审 |
| `PATCHES/std-*.patch` | 31 个标准化补丁 | 按需取；不改行为 |

其余 25 笔提交（`TestWallClock→WallClockStub` 改名、docstring 去临时路径、吞异常裁决注释、文档对齐）**不影响正确性**，收不收由评审决定。

## 3. 没做 / 没验（别当已完成）

- **server 三处漂移**：4001 登录失效用子串匹配、404 连击结算序、`is_joined` 查询失败当未报名。根因已定位（`FINDINGS.md` 的 F-08/F-10/F-11），需真实回包回归，未动。
- **`auto_login` 双文件无跨文件事务**（F-13）：需真机崩溃恢复验证，未动。
- **发布口径**：`VERSION` 1.2.0 未打包；`CHANGELOG` r3 / `app.py` r4 / `index.html` 生效日期 10-31 三处不一致；本机 `tag=0`，v1.1.1 无法追溯（BL-1 需 GitHub Release 证据）。
- **6 项挂工作区**：`relogin.js`、`update.js`、Fix A 遗留 hunk、Fix E 用例等，等存量 N1 与文案重写先提交（见 `DEFERRED.md`）。
- **从未验证**：真实学校接口、真实报名窗口（C01）、真机安装卸载、手机访问线（B12–B14）。

## 4. 文档整理的真实缺口（用户指出的）

受跟踪 `.md` 共 **103 篇**，本轮只改 **13 篇**（`CHANGELOG`、`README`、`design/README`、`design/specs` 4 篇、`docs/ARCHITECTURE|GRAB|LOGIN|README|UI_SPEC`）。**未改的 90 篇里，有 24 篇是现行文档，应当跟进但没有跟进：**

| 目录 | 未整理的现行文档 |
|---|---|
| `docs/` | `CONFIG.md`、`FEISHU_BOT.md`、`OPERATIONS.md`、`PHONE_ACCESS.md`、`PRIVACY_POLICY.md`、`RETRY_POLICY_GUIDE.md`、`TIMING_AND_DEDUP_ANALYSIS.md`、`USER_AGREEMENT.md` |
| `design/flows/` | `README.md`、`activity-selection-and-plan.md`、`first-use-and-login.md`、`mixed-plan-runtime.md`、`stop-and-result.md` |
| `docs/superpowers/specs/` | 2026-10-31 手机访问通道、2026-11-02 工作台 UI 重设计、2026-11-02 状态图、2026-11-03 架构改版 |
| `design/proposals/` | `README.md`、`replayable-product-tour.md` |
| 各目录 README | `local/README.md`、`server/README.md`、`server/deploy/README.md`、`server/deploy/legacy/README.md`、`server/scripts/dev/README.md` |

另 66 篇属历史（`design/decisions/` 16 篇、`design/evidence/` 各日期 24 篇、`docs/archive/` 26 篇），按「历史记录不追改」不动。

缺口性质：不是漏改错字，是**规格与实现之间没有对齐**（`RETRY_POLICY_GUIDE` 的节奏表、`PHONE_ACCESS` 与手机页实现、`USER_AGREEMENT`/`PRIVACY_POLICY` 与 r4 条款正文、`design/flows` 四条主链路与当前 UI）。

**归因（如实）**：这不是执行方偷懒。第二轮任务书由本会话的编排方（DSH 侧主代理，非 ZCode）写成，把 `docs+design` 排在 8 批的**最后一批**，并按 07:19 的时间纪律收尾；最后一批只完成「版本口径对齐 + 索引对齐」（`std-8a`–`std-8d`），正文整理没有排进去。**排序失误在方案设计一侧**，执行方按给定顺序做到了时间允许的位置。

## 5. 建议的接收顺序

1. 先让简单计划（27 项未提交）审完并提交——本轮的 26 笔基于同一份脏工作区，先合会撞 `local/tests/test_ui_contract.py`。
2. 再 `git bundle verify` + `git fetch <bundle> chore/standardize-20261105`，把 `099ded3` 与 A–E 补丁拿过来重跑红绿。
3. 困难计划直接用本目录的 `FINDINGS.md` / `RISK.md` / `DEFERRED.md` 当输入，不必重新侦查。
4. 文档缺口按第 4 节的 24 篇清单另开一批；`design/flows` 与 `docs/` 根目录优先，因为它们是现行口径。

## 6. 复现与核对命令

```bash
# 提交包自检
git bundle verify design/evidence/2026-11-05/night-audit/wip-standardize-20261105.bundle
# 取回分支
git fetch design/evidence/2026-11-05/night-audit/wip-standardize-20261105.bundle chore/standardize-20261105:refs/heads/wip-night-audit
# 看 26 笔
git log --oneline 4ec0b3d..chore/standardize-20261105
# 只有一笔改行为
git show --stat 099ded3
# 台账与覆盖账
wc -l design/evidence/2026-11-05/night-audit/STANDARDIZATION.md design/evidence/2026-11-05/night-audit/COVERAGE.tsv
```

## 7. 未处理项的当前状态（记录，非待办）

| 项 | 状态 | 触发条件 |
|---|---|---|
| 24 篇现行文档未整理 | **未派工**（用户 2026-11-05 明确「暂时不派了」） | 用户放行后再开工；清单见第 4 节 |
| server 三处漂移 / `auto_login` 跨文件事务 | 根因已定位，未修 | 随困难计划，需真实回包与真机验证 |
| 6 项挂工作区的改动 | 未提交 | 等存量 N1 与文案重写先提交 |
| `VERSION` 1.2.0 未打包、三处版本口径不一致 | 未处理 | 打包与升版属发布动作，需用户授权 |
| 真实学校接口 / 真实报名窗口 / 手机线 B12–B14 | 从未验证 | 需真实环境，无法靠代码证明 |

## 8. 纪律声明


- 全程只本地提交，**未 push、未合并、未打 tag**（`git tag` 为 0）。
- 主树 `<主树>` 的代码与历史未改（仅本目录为新增未跟踪）。
- 未安装依赖、未访问学校真实接口、未读取凭据。
