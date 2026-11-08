# 夜班交接（2026-11-08）

2026-11-08 夜班的交接文件。八层产出的逐层台账见 `LEDGER.md`，NEEDS-HUMAN 逐条清单见 `DEFERRED.md`。

## 开工三数核对

- **路径**：夜班副本仓库根（本项目仓库的本夜班工作副本；按仓库文档规范，本文件不写主机绝对路径）。主树只读，唯一允许的主树操作是本文档「回传记录」所列的两批复制与只读 status。
- **在途改动**：`git status --porcelain | wc -l` = **43**（开工复测；L2/L3 报告各自开工时亦实测 43，口径一致）。这 43 项是主树复制来的待评审内容（含 conflict-cancel 在途块），夜班未动、不回滚、不清理。
- **基准提交**：`a85209e`（`docs(ui): 设置抽屉规范同步，附成对截图`）——各报告的代码基准与开工 HEAD；夜班 6 层提交依次落其上。原型行号基准为工作区在途版 Main.dc.html（2498 行）/ Phone.dc.html（950 行），a85209e 版为 2283/842 行，详见各报告开头更正。

## 每层一句结论

| 层 | 一句结论 | 差异数 | NEEDS-HUMAN | 补丁 |
|---|---|---|---|---|
| L1 C2 登录与详情卡 | 登录弹窗宿主与详情卡键值行是最大缺口，缺失 28 项集中在画板 1/2/3/6/7 的宿主 | 109 项（86 行中 79 行计入） | 9 | 0 |
| L2 对话框与横幅 | 关窗/更新/引导/条款/迁移五组，整块缺失在 CloseHidden、FirstUse、迁移横幅、更新进度条 | 76 计次（54 行） | 8 | 0 |
| L3 手机页 | sheet 外壳、LED 板、任务卡、结果页等共用件全缺，「需后端先补」明确落 4 行 | 77 计次（52 行） | 6 | 0 |
| L4 主窗口 | 核心链路 34 行已一致，缺失集中在 SecondRun、Slept 的 missed 统计、dock 分支、折叠抽屉、窗口内 toast | 64 计次（52 行） | 7 | 0 |
| L5 文案真源比对 | 462 条一致率 86%，规格侧 4 议题（9 条）待裁决「改规格还是改代码」 | 不一致 22＋代码没有 4 | 4 议题（9 条） | 0 |
| L6 文档路径引用 | 194 条唯一路径，39 条死链全部是 docs/README.md 迁移对照表旧路径列，有意保留 | 死链 39＋有意 12 | 0 | 0 |
| L7 测试卫生 | `<tmp>` 6 处全部不出补丁（唯一会执行处是被测非法输入）；tests 内时钟风险 3；全量 1911 例通过 1906（失败 1 系他人在途改动所致） | 风险 3＋unittest 失败 1 | 1 | 0 |
| L8 无障碍名称 | 名称覆盖全绿（0/129、0/30），唯一实质问题 #tour-card 空标题（P1） | aria-labelledby 无效 1 | 0 | 0 |

## 报告路径清单（均在 design/evidence/2026-11-08/ 下）

- L1 `c2-login-gap.md`、L2 `c3-dialogs-gap.md`、L3 `phone-page-gap.md`、L4 `main-window-gap.md`
- L5 `copy-audit.md`、L6 `doc-refs.md`、L7 `test-hygiene.md`、L8 `a11y-names.md`
- `PATCHES/README.md`（补丁判定汇总）
- 夜班汇总：`LEDGER.md`、`DEFERRED.md`、`HANDOFF.md`（本文件）

## 本夜班提交哈希列表（git log -8 --oneline 核对）

```
7e2f3c2 docs(evidence): L7 L8 测试卫生与无障碍      ← L7/L8
41e86aa docs(evidence): L5 L6 文案与死链盘点        ← L5/L6
5a05f65 docs(evidence): L4 主窗口对账表             ← L4
c72ee93 docs(evidence): L3 手机页对账表             ← L3
5959569 docs(evidence): L2 对话框对账表             ← L2
ae981f6 docs(evidence): L1 登录与详情卡对账表        ← L1
a85209e docs(ui): 设置抽屉规范同步，附成对截图        ← 开工基准
423acd6 feat(ui): 设置抽屉三组照原型对齐              ← 夜班之前
```

另：本文件与 LEDGER/DEFERRED 的汇总提交、及其后的交接补记提交，在本清单之后产生，以 `git log` 为准。

## PATCHES = 0 说明

- 本夜班补丁合计 **0**：8 层全部是只读对账/盘点/收录，不改代码、不改测试、不改规格。`PATCHES/` 目录仅含 README.md，逐层判定如下。
- L6：39 条死链全部是迁移对照表旧路径列，右列即新路径，删改破坏对照功能——不建补丁。
- L7：唯一候选 `local/tests/test_component_builder.py:25`（一行 2 处 `<tmp>`）是被测非法输入样本（断言 `assertRaises(ValueError)`），改 `tempfile.gettempdir()` 会破坏测试意图——不出补丁；其余 4 处为 docstring/注释。
- L8：静态审计问题清单供排期，本轮不改 UI。

## 未验证事项汇总（各层「无法验证清单」归并）

- **渲染/运行时类（L1/L3/L4/L8）**：断行与字体渲染、像素级排版、动画、LED 点阵——需 Edge/WebView2 实测；未运行 `python local/app.py --demo`、未起 pywebview 桥、未连学校站点；L8 的 JS 运行时填充名称与 #settings 焦点边界需动态核验。
- **后端回包/字段类（L1/L2/L3/L4）**：`login`/`relogin_*`/`sync_clock`/`clock_snapshot`/`phone_*`/`check`/`update_*` 等载荷真实结构按 UI 消费侧静态认定；打码账号字段、更新回包体积字段、`pc_list_error`、pair 锁定结构化回包、`state.activities` 字段全集均未确认——多为「需后端先补」行。
- **原型侧类（L1/L2/L4）**：DC 画板连线/跳转、a85209e 版原型行号换算（仅抽样 6 处偏移）、引导第 3 步原型全文、Running/PreWarn 两薄壳画面细节、原型合成数值未渲染核对。
- **测试类（L7）**：风险判定为静态推断（枚举已复现）；未跑 server 全量、不跑 `test_dedup.py`（纪律）；生产侧时钟可疑 Top 5 未动代码。
- **漂移类（全部）**：所有 file:line 为 2026-11-08 工作区在途版口径，在途改动合入或回退后行号漂移，引用时以逐字原文为准。

## 给白天计划的指引

- **四份对账表按层直接可用**：C2（`c2-login-gap.md`）、C3（`c3-dialogs-gap.md`）、手机页（`phone-page-gap.md`）、主窗口（`main-window-gap.md`），每行给了差距类型、后端信号（有/需补）与建议列（照原型改/保留并说明/需后端先补/需用户定/不动），可按行切片派工。
- **行号口径 = 工作区在途版**：Main.dc.html 2498 行、Phone.dc.html 950 行、local/ui 按磁盘现状；合入在途后先复核行号，逐字原文不受影响。
- **先过 DEFERRED.md**：35 个条目（41 条计数）里 L1-1（登录宿主形态）与 L3-1（sheet 化）是方向性裁决，先定它们，其余行才有落点；L5 四议题决定改规格还是改代码。
- **L7 遗留**：tests 内时钟风险 3 处（test_session_persistence.py:334/438、server/tests/test_watchlist_safety.py:164）与 server/scripts 可疑 Top 5 可排专项；unittest 失败 1 例随 conflict-cancel 在途块合入后需复跑确认。
- **L8**：P1（#tour-card 空标题）可单独切片修掉；P2-P4 三行 aria-modal="false" 是低风险增强。

## 回传记录（第 4 步执行后回填）

- **主树回传清单**：`design/evidence/2026-11-08/` 全部 12 项（8 份报告＋`PATCHES/README.md`＋LEDGER/DEFERRED/HANDOFF 三汇总）；bundle 导出一份到主树仓库根（该文件不入库）（16,057,298 字节，与源一致）。cp 为合并语义，未删除主树已有文件；除这两批复制与只读 status 外未动主树任何文件。
- **主树 `git status --porcelain | wc -l`（第 4 步回传后）**：**45**。
- **bundle 来源**：由副本仓库导出（该文件不入库）；`git bundle verify` 通过——okay，含 5 个 refs（main=2f2944a、wip-night-audit=189bf27、origin/main、origin/HEAD、HEAD），完整历史。
- **回传后核对**：`ls` 主树 evidence 目录含全部报告＋`PATCHES/`＋三汇总，与源目录一致；主树根 bundle 字节数一致。
- **说明**：本段回填即第二次提交；随后 bundle 覆盖重建并按同路径重拷主树（覆盖同一文件，主树不新增条目），第 5 步复核计数见本次交接的最终报告，如与 45 不符以最终报告为准。

## 对抗审阅阶段（2026-11-08 补充任务）

- 八层对抗审阅全部完成：每层由未参与产出的两名角色交叉反证（机械核验＋实质反证，互盲），8 个对抗提交落成链 ff45306→3b2707a（L1–L8 各一），逐层合并报告见 `ADVERSARIAL-L1.md`…`ADVERSARIAL-L8.md`。
- 总表与逐层要点统一收录 `ADVERSARIAL.md`（总条数 1084、站得住 1030、部分站不住 44、推翻 9、红牌 33、报告已改 138＋补漏 1），此处不重复数字。
- 推翻合计 9 条：L1 两条（空态「已一致」、「多出 loginWarn」）、L4 两条（分组序引反、unknown 勾选门禁反转）、L5 三条（注释/否定式提及误归一致）、L7 两条（gettempdir 破坏断言不成立、server/tests 实测滤 0 行）。
- 红牌 33 张全部处置或关闭：L1 6（全关闭）、L3 10（弯引号 8＋无行号 2）、L4 ≈13（实质 4＋行号 9）、L7 4（全处置）；L2/L5/L6/L8 为 0。
- **身份披露**：L5–L8 的技术文档工程师即该四层原分析者，只承担机械项，全部实质判定由未参与原分析的前端开发者独立承担（各 ADVERSARIAL-Ln.md 开头如实记录）；L1–L4 双反证方均未参与产出，无此张力。
- 分母以实际全量为准、全部超出或等于任务书：L5 实际 463（含补漏）vs 预期 151、L6 194 vs 167、L7 94 判定＋6 tmp＋4 skip vs 约 100、L8 170 对上。
- `DEFERRED.md` 的 DEFERRED-L7-1 已按对抗结论改写：`<tmp>` 系被测非法输入样本、夹具规则不直接适用，替换可行且测试仍绿、可补 root==temp 边界覆盖；仍 NEEDS-HUMAN，倾向「不改但如实告知可改」。
- 残余风险：在途改动合入后行号漂移需重核（逐字原文不受影响）；L5 漏条已补为 463。
