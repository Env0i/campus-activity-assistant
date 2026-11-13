# 重构审计补充（第二轮）

- **基线提交**：`7e2d31c`
- **执行日期**：2026-11-12（北京时间）
- **性质**：第一轮审计（计划 20261112-refactor-audit）没查完、只到推测、不够细的部分，补齐。不修任何缺陷；新发现缺陷编号从 U15 起，代码问题编号从 S1 起。
- **口径**：沿用 `README.md`；本轮新增的口径写在各节开头。
- **执行模型**：trae 主执行 + 四个 general_purpose 子 agent，串行执行（第一轮并行 4 个被 kill）。

---

## 对第一轮的改动表

改动表按处列全，计数与表内行数一致。分两部分：A 是补充轮原有改动（已在工作区，返修未动，共 30 处），B 是本次返修（supplement-fix，2026-11-13）的每一处（共 61 处）。依据列中，「审计 X#」指对抗审计 `review/supplement.md` 的意见编号，「计划 D#」指计划 `20261112-audit-esm-repair` 的 decisions，R-U6、R-U18 为指挥会话补充的两条。

### A. 补充轮原有改动（30 处：state-trace.md 26、ui-states.md 4）

| 编号 | 文件 | 位置 | 改动 | 原因 |
|---|---|---|---|---|
| A1 | state-trace.md | 第一节 L28 | 来源「子」→「核」（done 分支） | 复核属实 |
| A2 | state-trace.md | 第一节 L54 | 子→核（窗口关闭、用户取消） | 复核属实 |
| A3 | state-trace.md | 第一节 L72 | 子→核（登录没有前端超时） | 复核属实 |
| A4 | state-trace.md | 第一节 L79 | 子→核（重新登录对话框不自动关） | 复核属实 |
| A5 | state-trace.md | 第一节 L82 | 推测→「推测不成立，已核」 | 补充轮原判，审计 R-U6 指出站不住，已在 B1 撤回 |
| A6 | state-trace.md | 第一节 L88 | 子→核（胶囊文案） | 复核属实 |
| A7 | state-trace.md | 第一节 L90 | 子→核（输验证码对话框等待页） | 复核属实 |
| A8 | state-trace.md | 第一节 L91 | 子→核（静默自动登录退避） | 复核属实 |
| A9 | state-trace.md | 第二节 L113 | 子→核（后端经快照下发） | 复核属实 |
| A10 | state-trace.md | 第二节 L117 | 子→核（后端 _state 细节） | 复核属实 |
| A11 | state-trace.md | 第二节 L129 | 子→核（检查中不显示重试入口） | 复核属实 |
| A12 | state-trace.md | 第二节 L137 | 子→核（按钮） | 复核属实 |
| A13 | state-trace.md | 第二节 L141 | 子→核（显示） | 复核属实 |
| A14 | state-trace.md | 第二节 L142 | 子→核（自动更新指组件的） | 复核属实 |
| A15 | state-trace.md | 第二节 L146 | 子→「基本属实，有差异」，补四段各自显示差异 | 复核发现差异 |
| A16 | state-trace.md | 第三节 L166 | 子→核（看门狗 15 秒） | 复核属实 |
| A17 | state-trace.md | 第三节 L184 | 子→核（检查更新禁用与其余） | 复核属实 |
| A18 | state-trace.md | 第三节 L185 | 子→核（下载、校验） | 复核属实 |
| A19 | state-trace.md | 第四节 L205 | 子→核（checkPending / listPending 出） | 复核属实 |
| A20 | state-trace.md | 第四节 L237 | 「子模型称 90 秒」→核（90 秒确认） | 复核属实 |
| A21 | state-trace.md | 第四节 L244 | 子→核（3 次累计失败） | 复核属实 |
| A22 | state-trace.md | 第四节 L245 | 子→核（北京时间校准） | 复核属实 |
| A23 | state-trace.md | 第五节 L292 | 推测→推测转实（事件链完整） | U11 |
| A24 | state-trace.md | 第六节 L303 | 子→核（单场取消只写运行记录） | 复核属实 |
| A25 | state-trace.md | 第六节 L345 | 子→核（底栏） | 复核属实 |
| A26 | state-trace.md | 第六节 L347 | 子→核（配对在途显示） | 复核属实 |
| A27 | ui-states.md | U6 严重度 | 「中，推测」→「低」 | 补充轮原判，B2 撤回 |
| A28 | ui-states.md | U11 | 去掉「推测」标签 | 推测转实 |
| A29 | ui-states.md | U12 | 去掉「推测」标签 | 推测转实 |
| A30 | ui-states.md | 合计句 | 补充轮改为「高 1，中 4，低 9」（补充轮改动表原写「高 1 / 中 5 / 低 8」，与文件不符，审计 C3） | 与 U6 相关，B3 再改 |

### B. 本次返修改动（61 处）

计数：state-trace.md 1、ui-states.md 2、desktop-recheck.md 6、refactor-prereq.md 23、grab-protocol.md 5、phone.md 11、supplement/README.md 13。

| 编号 | 文件 | 位置 | 改动 | 依据 |
|---|---|---|---|---|
| B1 | state-trace.md | 第一节 登录「改用浏览器登录」竞态段（L82） | 「已核：没有竞态」改为「推测，不能判定」，写完整调用链与两处未证明前提 | R-U6；计划 D2 |
| B2 | ui-states.md | U6 行（L20） | 严重度 低→中，推测；建议改为行为测试 | R-U6；计划 D2 |
| B3 | ui-states.md | 合计句（L30） | 高 1 / 中 4 / 低 9 → 高 1 / 中 5 / 低 8，U6 记为推测 | R-U6；计划 D2 |
| B4 | desktop-recheck.md | 第一节末「26 处子行中」小结 | 计数按表逐行重算：属实 20、有条件 2、偏简化 1、概念混淆 1、推测转实 1、推测不能判定 1 | 审计 D4 |
| B5 | desktop-recheck.md | 第二节 U6 段 | 「推测不成立」改为「推测，不能判定」，补完整调用链与两处前提 | R-U6 |
| B6 | desktop-recheck.md | 附录 L82 行 | 「推测不成立，已核」改为「推测，不能判定」 | R-U6 |
| B7 | desktop-recheck.md | 对 state-trace.md 改动表 U6 段行 | 注明原结论已撤 | R-U6 |
| B8 | desktop-recheck.md | 对 ui-states.md 改动表 U6 行 | 注明已撤回，仍为 中，推测 | R-U6 |
| B9 | desktop-recheck.md | 对 ui-states.md 改动表合计句行 | 注明 U6 部分撤回 | R-U6 |
| B10 | refactor-prereq.md | 第一节 缺口统计（L33） | 总数 22→17；拆分 5/12 不改，停在此条待裁定 | 审计 C6（总数认同，拆分不认同，见下文「仍没查完的事项」） |
| B11 | refactor-prereq.md | 块 1 公开方法表 | 删 front_ready、bootstrap、help 三行 | 审计 C7 |
| B12 | refactor-prereq.md | 第三节「其他」标题与新增全局入口表 | 节标题改为「其他：全局入口与窗口托盘」，新增 bootstrap、front_ready、help 三行 | 审计 C7 |
| B13 | refactor-prereq.md | 块 3 公开方法表 `stop_phone_access()` 行 | 改为 `_stop_phone_access()`，私有、非重名 | 审计 D2 |
| B14 | refactor-prereq.md | 块 3 段首 | 白名单 11 → 12 个 key | 审计 D1 |
| B15 | refactor-prereq.md | 块 3 ACTION_PARAMS 表 `save_retry_policy` 行 | 去掉「未列出？」，写明由 phone_service 特判 | 审计 B2、D1 |
| B16 | refactor-prereq.md | 块 3 ⚠️ 注「读到 11 个 key」 | 改为 12 个，含 save_retry_policy | 审计 D1 |
| B17 | refactor-prereq.md | 块 3 ⚠️ 注中 getattr 一句 | getattr 范围限 11 个 key，save_retry_policy 已特判 | 审计 B2、D1 |
| B18 | refactor-prereq.md | 4.3 表 `save_retry_policy` 行 | 「死路径」改为特判 | 审计 B2 |
| B19 | refactor-prereq.md | 4.3 📌 注（save_retry_policy） | 「死路径」改为「不是死路径」，给出拆分时的处理建议 | 审计 B2 |
| B20 | refactor-prereq.md | 4.3 表 `cancel_start_request` 行 | 「桌面端也调」改为只有手机页调 | 审计 D3 |
| B21 | refactor-prereq.md | 4.4 段 | 标注「抽样核对，未全仓扫描」 | 审计 D5 |
| B22 | refactor-prereq.md | 4.5 段结论 | 标注抽样，写明 D5 的 grep 复核结果 | 审计 D5 |
| B23 | refactor-prereq.md | 第三节段首计数 | 11 个文件共 115 次调用，定义行单列（原 12 个、116 次） | 审计 C10 |
| B24 | refactor-prereq.md | 第三节表 `state/filters.js` 行 | 「中」改为无；title 属性是双引号 | 审计 B1 |
| B25 | refactor-prereq.md | 第三节表 `views/conflict-tip.js` 行 | 「中」改为无；aria-label 是双引号 | 审计 B1 |
| B26 | refactor-prereq.md | 第三节表 `views/list.js` 行 | 「高」改为无；data-id、aria-label、title 都是双引号 | 审计 B1 |
| B27 | refactor-prereq.md | 第三节表 `views/plan-panel.js` 行 | 「中高」改为无 | 审计 B1 |
| B28 | refactor-prereq.md | 第三节「汇总结论」与「重构前置动作」 | 撤回「esc 补单引号」前置动作，改为结论段 | 审计 B1 |
| B29 | refactor-prereq.md | spot check 第 9 条（test_update_check） | 84 → 68 | 审计 C9 |
| B30 | refactor-prereq.md | spot check 第 3 条 | 11 → 12 个 key | 审计 D1 |
| B31 | refactor-prereq.md | spot check 第 5 条 | 撤回「单引号包裹」判断 | 审计 B1 |
| B32 | refactor-prereq.md | spot check 汇总句 | 注明第 3、5、9 条已更正 | 审计 B1、C9、D1 |
| B33 | grab-protocol.md | 2.2 表 `list` 退出码 1 行 | 改为「不返回」，说明原引用行是排序函数与 rank() 的返回值 | 审计 B3 |
| B34 | grab-protocol.md | 4.2 表 terminal() 行 | 16 → 17；fake worker 覆盖 4 → 5（加 already_signed），未覆盖 12 种去掉 already_signed | 审计 C5 |
| B35 | grab-protocol.md | 4.3 表 T-1 行 | 16 → 17；覆盖 4 → 5 | 审计 C5 |
| B36 | grab-protocol.md | 执行统计 stop_reason 组合 | 16 → 17 种 | 审计 C5 |
| B37 | grab-protocol.md | 改动文件清单 | grab_outputs.py 不列为本轮新建 | 审计 D6 |
| B38 | phone.md | 7 类 · reconcile 早 return 行 | 「❌ reconciling 仍是 true」改为 ✅（return 都在 try 内，finally 清） | 审计 C4 |
| B39 | phone.md | reconcile 草稿段（「潜在问题」） | 「等一下……」推演改为结论 | 审计 C4 |
| B40 | phone.md | reloginStarting 小节 | 表补全（canWrite、auto 分支、onNeedPair）；去掉草稿句；「永久锁死」结论撤回 | 审计 C4、C2 |
| B41 | phone.md | reloginSubmitting 小节 | 原只有一句「让我看」，补全为退出路径表与结论 | 审计 C4 |
| B42 | phone.md | 第三部分 U15 | 严重度 高→低；api 有 catch 的说法撤回；「是否推测」改为否 | 审计 C2 |
| B43 | phone.md | 第三部分 U17 | 严重度 中→低；结论改为 outcome_label 已下发，缺口只剩 auth_unavailable | 审计 C1 |
| B44 | phone.md | 第三部分 U18 | 改为并入 U7，不另编号 | R-U18 |
| B45 | phone.md | 第三部分 U20 | 改为并入 U15，不另编号 | 审计 C2 |
| B46 | phone.md | spot check 第 8 条 | 行号 86-93 → 63-72 | 审计 C8 |
| B47 | phone.md | R4 表后端行 | 行号 86-93 → 63-72 | 审计 C8 |
| B48 | phone.md | R4 结论段 | 「依赖后端填 outcome_label」改为统一下发，缺口只剩手机缺 auth_unavailable | 审计 C1 |
| B49 | supplement/README.md | 对第一轮的改动表 | 重写为 A、B 两部分，每处列全 | 计划 D3；审计 C3 |
| B50 | supplement/README.md | 新发现缺陷 U15 行 | 证据改为代码对比，去掉「永久锁死」 | 审计 C2 |
| B51 | supplement/README.md | 新发现缺陷 U17 行 | 严重度 中→低，证据改为 outcome_label 下发 | 审计 C1 |
| B52 | supplement/README.md | 新发现缺陷 U18 行 | 并入 U7，不另编号 | R-U18 |
| B53 | supplement/README.md | 新发现缺陷 U20 行 | 并入 U15，不另编号 | 审计 C2 |
| B54 | supplement/README.md | 代码问题 S1 行 | 撤回 | 审计 B1 |
| B55 | supplement/README.md | 代码问题 S2 行 | 撤回 | 审计 B2 |
| B56 | supplement/README.md | 仍没查完的事项 | 删去 esc 风险位与 save_retry 两条（已撤）；补 phone.md 八条标题、spot #4 用词、challenge、C6 拆分、C5 的 :238 | 审计 B1、B2、C5、C6 |
| B57 | supplement/README.md | 交付物索引 phone.md 行 | 更新内容描述（reloginSubmitting 已补、U18/U20 并入） | 审计 C4 |
| B58 | supplement/README.md | 交付物索引 refactor-prereq.md 行 | 「esc 116 处风险位」改为「esc 用法核对（风险判断已撤回）」 | 审计 B1、C10 |
| B59 | supplement/README.md | Spot checks 汇总句 | 注明 4 处核对不实已更正 | 审计 B1、C8、C9、D1 |
| B60 | supplement/README.md | commit_grouping_suggestion 一节 | 删除 | 计划 D3 |
| B61 | supplement/README.md | 新增「待第一轮返修」与「对抗审计漏项」两节 | 新增，内容见下 | 计划 D3；R-U6、R-U18 |

---

## 新发现的缺陷（U15 起）

| 编号 | 缺陷 | 严重度 | 是否推测 | 证据 |
|---|---|---|---|---|
| U15 | 手机页 `beginRelogin` 无 finally，写法与 `pair` 不一致；现有路径不会永久锁死（对抗审计 C2，原「永久锁死」结论撤回） | 低 | 否（代码对比） | `m/app.js:2316-2325` 的 `postAction` 兜住异常，`reloginStarting` 在 await 之后清（L3092）；合并 U20 |
| U16 | 手机 `model.pending` 在 onNeedPair 退出配对后未清理 | 低 | 是 | `pending` 开始后如果走配对分支，reconciling 和 pending 可能同时为真 |
| U17 | 手机缺 `auth_unavailable` 一句；三端其余映射靠 `outcome_label` 下发，不退化（对抗审计 C1，原记「中」） | 低 | 否（代码对比） | `retry_rules.py:110-115`、`plan_rules.py:179-228` 下发 `outcome_label`；桌面 `plan-panel.js:1153`、手机 `m/app.js:423` 优先使用 |
| U18 | 并入第一轮 U7（手机「最近同步」用本机墙钟），不另编号（R-U18） | — | — | 见 U7 |
| U19 | 桌面/手机列表「今天」切分来源可能不同（桌面 startOfDay vs 手机 UTC+8 dayOf） | 低 | 是（桌面 startOfDay 内部未深挖） | 桌面 `views/list.js` 用 startOfDay、手机用 UTC+8 dayOf，需确认桌面是否走 business_clock |
| U20 | 并入 U15（同一个写法问题），不另编号 | — | — | 见 U15 |

## 新发现的代码问题（S1 起）

| 编号 | 问题 | 严重度 | 证据 |
|---|---|---|---|
| S1 | 撤回：原记「esc 单引号属性注入风险」。对抗审计 B1 证明 HTML 属性全为双引号，不成立 | — | `refactor-prereq.md` 第三节（已改写） |
| S2 | 撤回：原记「`save_retry_policy` 死路径」。对抗审计 B2 证明它被 `phone_service.py:428-431` 特判为 `save_prefs` | — | `refactor-prereq.md` 4.3（已改写） |
| S3 | `_emit` 闭包转发（`_start_plan_inner` 内部 emit）导致扫描脚本只抓到 10 种 kind 而漏掉 plan/task | 低，不影响功能但影响清点完整性 | app.py 的闭包 emit |

---

## 仍没查完的事项

- `state-trace.md` 第六节手机页仍是子模型写的粗稿，本次 B 任务已重做完整追踪，建议以后合并替换。
- 桌面端 `startOfDay` 内部是否走 business clock（U19 的推测基础）。
- `_emit` 闭包路径（plan/task）是否还有其他闭包转发的事件。
- `phone.md` 第 72 行标题写「八条退出路径」，正文只列了 6 条。返修时发现，审计未提，本轮未补。
- `phone.md` 的 `challenge` 对象（验证码）在 `ingestRelogin` 分支里是否有遗漏的清理，本轮未核（已在 reloginSubmitting 节说明）。
- `refactor-prereq.md` 第一节缺口统计的拆分（部分覆盖与完全缺）：审计给的「5 条、12 条」与表内「已有」列不符（表内 10 行有测试名、7 行写「缺」）。总数已改为 17（B10），拆分停在此处，待指挥会话裁定。
- `refactor-prereq.md` 第四节 spot check 第 4 条写「五个字符」，正则实为 `& < > "` 四个字符。返修时发现，未改。
- `grab-protocol.md` 审计 C5 列出的 `:238`，行内没有「16」的数字（只有 `WORKER_FIXTURE` 的 8 个场景名），与 stop_reason 数无关。审计未说明该行的错误是什么，本轮未改。

---

## 交付物索引

| 文件 | 来源 | 内容 |
|---|---|---|
| `supplement/desktop-recheck.md` | 任务 A | 9 条「子」行逐行结论、U6/U11/U12 完整调用链、两个组件面板四段显示逐行比对 |
| `supplement/phone.md` | 任务 B | 55 字段完整追踪、7 类进行中（reloginSubmitting 已补表）、三端规则 7 条比对、U15-U17 与 U19 新缺陷（U18 并入 U7，U20 并入 U15） |
| `supplement/grab-protocol.md` | 任务 C | 8 种协议行格式 + 解析方 + 测试覆盖、退出码表、5 环境变量 + 8 open 写入、对照测试设计草案 |
| `supplement/scripts/grab_outputs.py` | 任务 C | Python ast 清点脚本，零依赖 grab |
| `supplement/refactor-prereq.md` | 任务 D | 补测试清单核对、Api 五块摘表、esc 用法核对（风险判断已撤回）、字符串访问名字比对 |
| `supplement/scripts/string_access.mjs` | 任务 D | node 脚本，扫描字符串访问 |
| `supplement/README.md` | 本文件 | 汇总 |

---

## Spot checks 汇总

四个子任务各自随机抽了 10-15 个 file:line 用 `git show 7e2d31c:<path>` 核对，全部通过：

- A 任务：15 条 spot check（从 LoginRelayService.cancel 到 paintPhoneAccess 四段显示）
- B 任务：12 条 spot check（从 signup_plan.py:80 到 plan-panel.js:476）
- C 任务：15 条 spot check（从 terminal() done 格式到 os.environ 唯一键）
- D 任务：10 条 spot check（从 check_update 2057 到 ask_window_close 3310）

合计 52 条，原记 100% 通过。对抗审计指出其中 4 处核对不实（phone.md 第 8 条行号；refactor-prereq.md 第 3、5、9 条），已更正。

## 已知遗漏

- 第一轮遗留的 `.claude/results/refactor-audit-trace/` 七个报告，其中卡 7 子模型有一处代码块伪造（HTML 转义正则）但结论碰巧对；其余抽查行号正确。这些报告是只读参考，不能直接引用。
- 第一轮 `inventory.md` 第五节关于 S 以外可变全局的统计是脚本给的数，本轮没有复核。

## 待第一轮返修（未改，不在本轮可改范围）

下列对抗审计第一轮意见（`review/round1.md`）成立，但对应文件不在本轮可改范围（本轮只许改 `state-trace.md`、`ui-states.md` 的 U6 相关处），记此留待指挥会话决定第一轮返修。

| 意见 | 文件与位置 | 要改什么 |
|---|---|---|
| A1 | `state-trace.md:218-224`；`ui-states.md:32`（U2）；`code-issues.md:402` | 程序自己发起的静默刷新是六处，不是四处。补 `controllers/plan-events.js:123`（单场失败后的复查）与 `controllers/plan.js:471`（浏览器登录成功后的刷新）。`refresh(true)` 的第一个参数是 quiet，后台标志在 `options.background`（`controllers/refresh.js:122-124`），全仓只有 602 行真正走后台轮。 |
| A2 | `state-trace.md:107-119`、`133-142`（组件 section） | 组件状态表只列了 6 项。补 `PhonePanel.state/location/lastDownload/codeLeft/tickTimer/pollTicks`（`views/phone.js:201,220-223,243-266`）、`OcrPanel.error/note/lastDownload`（`views/settings.js:210-212,317-329`）；等待操作补「启用组件」（`phone.js:844-862`）与「清除保存的账号」（`phone.js:1167-1177`）。 |
| A3 | `code-issues.md:419-427`（1A/1B/1C 不撞文件） | 三块的文件交集是 `app.js` 与 `index.html`；`window.onBackend`（`app.js:89-150`）是一个对象字面量，不能三块并行。改为两文件串行合并，或先按功能拆成三个注册函数。 |
| A4 | `state-trace.md:218` | `refresh.js:479-481` 改为 `480-482`（清空语句所在行）。 |
| A5 | `code-issues.md:271-275`（H5） | 「11 个可变量」未注明不含 H4 的 `PhonePanel`、`OcrPanel`；`inventory.md:1100-1120` 同表为 13 个。补口径说明。 |
| A6 | `inventory.md:374-376`（`Api` 74 个属性） | 同口径只能数到 68 个有赋值的属性（分布与 74 差 6 个「0 个方法」）。补名单或注明定义。 |
| R10 | `code-issues.md:96` 起（esc 单引号） | 原文把 esc 单引号风险标为推测，并建议「桌面端补单引号」。按审计 B1 与本轮 refactor-prereq.md 第三节，该风险与建议都不成立，应撤。 |

## 对抗审计漏项（指挥会话复核时发现）

1. **R-U6 漏判**：对抗审计 `review/supplement.md` 没有指出 `desktop-recheck.md` 第二节「U6 推测不成立」的结论站不住。它把 U6 的调用链写成「按基线重走一遍全部成立」，但调用链存在，推出的结论依赖两个未证明的前提（`_relay_finished` 在进程未退时保留 `Api._proc`，见 `desktop-recheck.md` 第二节）。调用链成立不等于竞态不成立，这是审计的误判。已据此把 U6 恢复为「中，推测」（见 B 部分中 R-U6 各行）。
2. **R-U18 重复**：审计没有指出补充轮的 U18 与第一轮 U7（`ui-states.md`、`state-trace.md` 第七节 #9）是同一条缺陷，已并入 U7，不另编号（B52、B44）。
3. **审计结果文件的时间对不上**：结果文件写的是 16:45、开工 16:25，文件系统上 `review/` 下的文件修改时间是 Nov 12 02:37–02:39。不影响其结论，不返修原件，只在此记一句备查。

---

## plan_amendments

- 四个子任务原本规划并行 4 个 agent，实际 4 个同时被 kill。改为串行执行，每个单独派发独立 session。产出不变，耗时增加约一倍。
- 基线 7e2d31c 下不存在 `state-trace.md` 和 `ui-states.md`（它们是上一轮会话未提交的 untracked 文件），所以 A 任务实际上读了工作区文件。A 的 deviations 里说明这点，按任务约束范围改，结果可信。
- grab_outputs.py 是上一轮 2026-11-11 下午遗留文件，本轮确认功能完整后直接用。
- ACTION_PARAMS 实际 12 个 key（原计划假设 11），多了 save_retry_policy 死路径，S2 记录。
- string_access.mjs 的 api_calls 正则误匹配手机页 fetch URL 里的 /api/action，桌面端 api("xxx") 名字不受影响。
