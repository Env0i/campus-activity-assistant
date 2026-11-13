# AA1 事实核对审计意见

- **计划**：`20261113-refactor-audit-redo` 的 AA1 任务（阶段二，事实核对）。
- **审计者**：AA1（Haiku 5.5 子智能体）。未看 AA2 的意见，未看主执行方过程记录，未读 `redo/zcode/`（另一执行方产物，不在审计范围内，只在核对脚本的输出里计数，不读内容）。
- **基线**：`7e2d31c`。读代码一律 `git show 7e2d31c:<路径>`。
- **被审文件**：`redo/` 顶层的 `desktop.md`、`phone.md`、`rules.md`、`grab.md`、`prereq.md`、`reconcile.md`，五份 `.cites.jsonl`，`scripts/`，`README.md`。均未改动。
- **中间文件**：只写了两个临时目录（见第 8 节），没有写进证据目录。

## 1. verify_cites.py 独立运行

1. 第一次运行（`redo/` 下尚无 `zcode/` 时）：`PYTHONIOENCODING=utf-8 py -3.12 -X utf8 -B .../verify_cites.py`，输出「引用条目通过 1060 条，失败 0 条；md 里的 [[id]] 引用 1493 处；未被 md 引用的条目 1 条」，按文件 desktop 424、grab 62、phone 292、prereq 194、rules 88，按 kind 事实 1056、推测 2、需测试定 2，退出码 0。
2. 审计中途 `redo/` 下出现了 `zcode/` 子目录。再次按原命令运行，脚本输出「通过 1758 条，失败 212 条，md 引用 3022 处」，退出码非 0。失败来自 `zcode/`，因为脚本用 `rglob` 递归。我没有打开 `zcode/` 看内容，只记了计数。
3. 为了按本轮范围核对，把 `redo/` 顶层的 6 份 md、5 份 cites、README 复制到一个新建的临时目录，用 `--redo <临时目录>` 复跑：通过 1060 条，失败 0 条，退出码 0，与第一次结果一致。
4. `--self-test`：三条故意写错的样例全部被拦下，退出码 0。

结论：顶层范围内 `verify_cites.py` 通过；全目录口径会被 `zcode/` 拖红，见意见 A2。

## 2. 脚本源码核对（F2）

逐条对照 `verify_cites.py` 源码：

- 字段齐全、`file` 为仓库根相对路径、行号为正整数闭区间、跨度不超过 15、不越界：`check_entry` 里都有，核实。
- `excerpt` 至少 12 字符，且在 `start..end` 拼起来的文本里恰好出现一次（`seg.count`）：核实。
- `kind` 只许三种值，非「事实」必须写 `missing`，`claim` 非空：核实。
- `id` 全目录唯一：`seen` 字典核实。
- md 里的 `[[id]]` 都必须存在：核实。

放水的地方（脚本没挡住，但 F2 的说法是「md 里不许出现裸行号」）：

- **裸行号检测只认「文件:行号」形式**（`RAW_LINE_RE`）。下面这些「文件 行号」形式逃过了检查：`desktop.md` 第 88 行（`views/login.js` 71）、`desktop.md` 第 211 行（`app.py` 2572）、`reconcile.md` 第 41 行（`views/login.js` 71）、`reconcile.md` 第 55 行（`app.py` 2572）。见意见 A1。
- **`rglob` 递归**：全目录口径会把子目录的 md 和 cites 一起算进去（见第 1 节第 2 点）。见意见 A2。
- **只核 `[[id]]` 形式**：`reconcile.md` 第 120–121 行用反引号写的区间 id（`DSK-409g` 到 `DSK-409j`、`DSK-231a` 到 `DSK-232b`）不在核对范围内。见意见 A10。
- 脚本只能证明「原文在这几行里」，证明不了「这一行真是这个意思」，也证明不了 md 里对 id 的用法（例如把推测条目写成事实）。这是设计范围内的，靠抽查和第 4 节的人工检查。

## 3. 抽查（代码语义）

### 抽样方法

- 每份 `.cites.jsonl` 按 `k = max(15, ceil(0.2 × n))` 抽取，随机种子 `20261113`，`random.Random(20261113).sample(range(n), k)`。
- 样本数：desktop n=424、k=85；phone n=292、k=59；rules n=88、k=18；grab n=62、k=15（20% 为 12.4，取下限 15）；prereq n=194、k=39。合计 216 条。
- 每条都用 `git show 7e2d31c:<file>` 重读引用行，并在必要时看前后几十行的上下文，判断 claim 是否成立。

### 结果

| 文件 | 抽查数 | 对 | 对但引用不完整 | 错 |
|---|---|---|---|---|
| desktop | 85 | 81 | 2（DSK-134b、DSK-507a） | 2（DSK-409g 事实错，DSK-402b 引用不支撑） |
| phone | 59 | 59 | 0 | 0 |
| rules | 18 | 17 | 1（RUL-807） | 0 |
| grab | 15 | 15 | 0 | 0 |
| prereq | 39 | 39 | 0 | 0 |
| 合计 | 216 | 211 | 3 | 2 |

具体说明（只写有问题的；没问题的不列）：

- **DSK-409g**（desktop）：claim 写「无参数的前台刷新」，但 `plan-events.js:123` 是 `refresh(true)`，带了参数 `true`（`refresh(quiet, options)` 的 quiet）。见 A6。
- **DSK-402b**（desktop）：claim「挂 130 秒兜底」为真，但引用的 `refresh.js:189` 只有 `setTimeout(() => {`，`130000` 在 `refresh.js:202`，不在引用范围内。见 A7。
- **DSK-134b**（desktop）：claim「校验结论为 unknown 时胶囊文字」，实际条件是 `result === "unknown" && ok === false`（`views/login.js:55`），claim 漏了 `ok === false`。见 A8。
- **DSK-507a**（desktop）：claim「只有以 stopped 结束才放回勾选」，引用的 `plan-events.js:17–25` 只有 if 分支，「只有」没有 else 分支的引用支撑。见 A9。
- **RUL-807**（rules）：claim「三个码带标题和提示」为真，但引用的 `refresh.js:377` 只有 `const RUNTIME_ERRORS = {`，三条内容在 378–380 行，不在引用范围内。见 A11。

抽查中的三处「看起来像错、实际没错」（记录，不计入意见）：

- `PHN-024` 的 `setClock` 归属：`write` 在 `setClock` 函数内（`m/app.js:294–302`），看起来在 `drift` 下面，是 naive 脚本的误判。
- `PHN-041`、`PHN-074`、`PHN-085`、`PHN-148`、`PHN-223` 的 `reselectFailed` 归属：`reselectFailed` 在 `m/app.js:2850`，naive 脚本漏判了。
- `PHN-253` 的 `toggleWhy`：`m/app.js:410–411` 确认。

### 手机页的函数归属与第一次读取

对 phone.cites.jsonl 里全部「写入：X =（函数）」和「X 的第一处读取（函数）」条目，用脚本对 `local/ui/m/app.js` 做了一次交叉检查：写入行和首次读取行都对得上，除上面列出的 naive 误判外，没有错。

## 4. 推测与需测试定条目，以及 md 里的推测

四条非「事实」条目（DSK-113a 推测、PRE-911 推测、DSK-810a 需测试定、GRB-130 需测试定）：

- **DSK-113a**（推测，缺席结论「handoff、autoLogin 不在 store.js 的 S 字面量里」）：我用 `git show 7e2d31c:local/ui/state/store.js` 全文搜索 `handoff|autoLogin|recovering|relogin:|editing:`，命中 0 处。missing 写的「需全文搜索」是对的，缺席结论成立。
- **PRE-911**（推测，单引号属性为 0）：missing 写的是「脚本启发式分类，看不到跨语句拼接」，这个限制是真的，我没有独立重做全文搜索，不再下结论。
- **DSK-810a**（需测试定，pywebview 的调用先后）：missing 写「源码不在本仓库」。核实：`local/requirements.txt` 里有 `pywebview>=5.0`，基线树里没有 pywebview 源码。缺失环节成立。
- **GRB-130**（需测试定，行首时间戳是否在中途被去掉）：missing 说「没有核对中间是否有未读到的环节去掉时间戳」。我核对过了，中间没有：`plan_service.py` 的读线程只做 `line.rstrip("\r\n")`（基线第 178 行），之后直接把原行交给 `parse_retry_line`（第 276 行）；`grab.py` 的 `log()` 用 `print(line)` 把带时间戳的整行打到 stdout（第 286、299 行）。missing 里提到的那一环，读代码就能定。见 A12。

md 里的推测写成事实：

- desktop 1.22「没有发现没清的路径」标「属实」，依据是「前端每条出口见 1.01；后端 DSK-121a 在 finally 里」。这是对全部出口的缺席结论，引用只覆盖了一部分。见 A13。
- grab W7（标「事实」）「selftest 没有任何测试和解析方，退出码没有读取方」是全仓缺席结论，引用只有 GRB-128，没有全仓搜索的依据。见 A14。

## 5. 计数核对

| md 中的计数 | 核对结果 |
|---|---|
| desktop「第一至七节 143 行：属实 113、有条件属实 28、不属实 1、需测试定 1」 | 一致。逐行统计：1–6 节 132 行加第 7 节 11 行，合计 143；属实 113、有条件 28、不属实 1、需测试定 1，与「十、统计」表一致 |
| desktop 3.02「`S.update.requestId` 含标识符 19 行，其中赋值 5、比对 9、读取 5」 | 19 行一致，赋值 5 一致。但 md 的「计数说明」写「赋值行 6、读取或比对 13」，与行内数字矛盾。见 A4 |
| desktop 4.09「全仓 refresh(true) 的调用点（不含后台那一处）共 8 处，另有启动时的一次」 | 基线实际共 9 处（含启动的那一处）。md 列出的 8 条（409c–j）不含启动那一处，所以「共 8 处」与「另有启动时的一次」合起来应为 9，口径不清。见 A5 |
| reconcile 汇总「一致 48、重做推翻 22、补充轮漏 8、重做漏 2，合计 80」 | 一致。逐行统计 80 行，类别 48/22/8/2 |
| phone「55 个字段、写入点 148（136+3+9）、别名写 6」 | 一致。`phone_model_fields.mjs` 输出：字段 55，写入 148（直接赋值 136、容器改 3、内部写 9），别名 6；md 字段表 55 行 |
| prereq「Api 公开方法 60 个」「esc 调用点 115 处，39 个脚本，11 个文件」「api(\"…\") 字面量 44 个」 | 一致。`api_methods.py`：公开方法 60；md 2.1 表 60 行。`esc_sites.mjs`：115 处，落点 文本节点 83、双引号属性 22、其他 8、标签内其他 2；`string_names.py`：api 静态名 44，全部是 Api 公开方法 |
| grab「输出调用 187 处，log→stdout 62，print→stdout 84，嵌套 return 109」 | 一致。`grab_outputs.py`：输出调用 187，log→stdout 62，print→stdout 84，嵌套函数 return 109 |
| rules「九条规则」 | 一致（rules.md 第 1–9 节） |
| esc「没有任何落点是单引号属性」 | 脚本分类里没有单引号属性这一类，但「其他」8 处和「标签内其他」2 处没有逐条复核。这是缺席结论，见第 4 节和 prereq 的声明，记为依脚本启发式，不另列意见 |

## 6. 三处重点复核

### 6.1 grab.md W6（判断：结论成立；标签可以升级）

- 代码事实：`log()` 把时间戳拼在前面再 `print`（`grab.py:276–299`）。`parse_retry_line` 要求 `text.startswith("[retry] ")`（`retry_rules.py:34–37`），`ATTEMPT_RE` 要求行首锚定（`retry_rules.py:25`）。`parse_checkpoint_line` 用 `find`（`worker_lines.py:22`）。
- 中间没有剥时间戳的地方：`plan_service.py` 读线程只做 `rstrip("\r\n")`（第 178 行），解析前没有任何 strip 或正则替换（全文只有 `rstrip` 与 `strip` 两处，都是别的用途）。
- 纯函数验证：我在 `tempfile.mkdtemp()` 新建的临时目录里 `git archive 7e2d31c local/domain` 导出，然后 import `domain.retry_rules` 与 `domain.worker_lines`，结果如下：
  - 带时间戳的 `[retry] attempts=…`：`parse_retry_line` 返回 None；
  - 不带时间戳：返回字典；
  - 带时间戳的 `[i] 第 2 次提交：…`：`ATTEMPT_RE` 不匹配；不带时间戳：匹配；
  - 带时间戳的 `[checkpoint] {…}`：`parse_checkpoint_line` 正确返回 `('page_opened', 1.5)`。
- 结论：「计划模式下 `[retry]` 终态行和「第 N 次提交」行应该都认不出来，而 checkpoint 认得出」在读代码层面成立，且代码已经能定。md 把它标「需测试定」比较保守，建议下一版升级，同时保留那条最小测试作为确认。这是判断的标签问题，不是结论错误，见 A12。

### 6.2 desktop.md 5.12「不属实」（判断：成立）

- 「窗口恢复时 bootstrap 只对账 busy 和计划状态，不改 S.stopping」：不成立。`app.js:639` 调用 `ingestBootstrapPlan`；`refresh.js:60` 起的这个函数在终态快照时（`refresh.js:92`）调用 `presentPlanDone(…, false)`；`plan-events.js:10` 在该函数里写 `S.stopping = false`。
- md 说「第一句是 S.stopping = false 也不准，清它在函数中部」：也对，`plan-events.js:10` 前面还有 `doneGen`、`S.plan.id`、`S.plan.status` 三句。
- 结论：5.12 的「不属实」判断站得住。

### 6.3 reconcile.md 重做推翻的抽查（至少 8 条，实际 10 条）

| 条目 | 核对结果 |
|---|---|
| RC-01（preLoginSnapshot 行号） | 成立。失败分支清空在 `plan.js:477`（`handleDone` 内），成功分支在 `plan.js:466`，原文 457/468 确实是别的行 |
| RC-04、RC-06（对话框步骤名 result） | 成立。`relogin.js:199` 的步骤清单没有 `result`，失败进的是 `msg`（`relogin.js:418`） |
| RC-07（auto_relogin_service.py 文件名） | 成立。基线只有 `local/application/auto_relogin.py`，退避秒数在第 107 行 |
| RC-19（取消超时 90 秒的行号） | 成立。`CANCEL_WORKER_TIMEOUT_S = 90` 在 `app.py:2521`，不在 2572 |
| RC-22（5.12 的 bootstrap 链） | 成立，见 6.2 |
| RC-27（relay terminate 等待） | 成立。`process_tree.py:235–237` 的文档字符串写明 `TerminateJobObject` 后先等父进程最多 1 秒，与补充轮「只发信号、不 wait」矛盾 |
| RC-40（桌面时区） | 成立。`clock.js:241`、`time.js:2` 固定 `Asia/Shanghai`（未追到 startOfDay 的完整调用链，只核了时区写死这一半） |
| RC-42（session_expired 是死条件） | 成立。基线全树没有把 `session_expired` 设为真的赋值。`m/app.js:137` 的确把「没有会话」和 `session_expired` 并成一个判断 |
| RC-70（refresh.js 清空语句的行号） | 成立。`refresh.js:479–481` 与 DSK-409a/b 一致 |
| RC-43（缺开放时刻的手机归类） | **依据错**，见 A3 |

## 7. 意见

格式：原文说什么 / 代码实际是什么 / 被审条目 id 与基线 文件:行号 / 类别 / 严重度。阻断意见：**无**。

### A1 裸行号检测漏判（重要）

- 原文：`verify_cites.py` 的文档字符串写「md 里不许出现裸行号」。
- 代码实际：`RAW_LINE_RE` 只匹配 `文件:行号`；`desktop.md:88`（`views/login.js` 71）、`desktop.md:211`（`app.py` 2572）、`reconcile.md:41`、`reconcile.md:55` 是「文件 行号」形式，全部通过了检查。
- 被审条目与位置：`verify_cites.py` 的 `RAW_LINE_RE`；被审 md 为 `desktop.md:88`、`desktop.md:211`、`reconcile.md:41`、`reconcile.md:55`。
- 类别：漏项（脚本漏检）。
- 严重度：重要。这些行号是对第一轮的引述，不是本轮引用，但门禁的承诺打了折扣。

### A2 核对脚本范围过宽（重要）

- 原文：`verify_cites.py` 说「读取 redo/ 下全部 .cites.jsonl」。
- 代码实际：`load_entries` 与 md 扫描都用 `rglob`，会把 `redo/` 子目录也算进去。现在 `redo/zcode/` 存在，全目录运行结果变成「通过 1758、失败 212、退出码非 0」；顶层范围内是 1060/0/0。
- 被审条目与位置：`verify_cites.py` 的 `load_entries`（`rglob("*.cites.jsonl")`）与 `run` 里的 `rglob("*.md")`。
- 类别：漏项（范围口径）。
- 严重度：重要。门禁的结果会随着别的目录变化，不可复现。建议改成非递归的 `glob`，或者明确给出文件清单。

### A3 RC-43 的手机归类依据错（重要）

- 原文（reconcile.md RC-43）：「开放时刻缺失时桌面和后端归立即，手机归预报名」。
- 代码实际：
  - `local/ui/m/app.js:557`：`stOf` 在 `open` 解析不出（为 0）时返回 `"unknown"`（待公布），不是 `"pre"`；只有 `open > 0` 才返回 `"pre"`。
  - `local/ui/m/app.js:885`：待办列表的「等待开放 / 准备报名」分支用的是后端的 `signup_mode`，缺 `sign_start` 时后端给的是 `instant_signup`，手机也就归为「准备报名」。
  - 所以手机对缺开放时刻的活动，分组里是「待公布」，单条文案是「准备报名」，两者都不是「预报名」。
  - `RUL-207`（`m/app.js:49`）的「解析不出按 0」是对的，但它本身不推出「归预报名」。
- 被审条目与位置：reconcile.md RC-43（引用 RUL-201、RUL-203、DSK-622a、RUL-207）；基线 `local/ui/m/app.js:548–557` 与 `:885`。
- 类别：事实错（重做推翻的依据写错了）。
- 严重度：重要。「桌面与手机不同」这个结论仍成立，但依据要改。

### A4 3.02 计数说明与行内数字矛盾（次要）

- 原文（desktop.md 3.02 行）：「赋值 5 行、比对 9 行、其余读取 5 行」；「计数说明」：「grep -c 得 19 行；其中赋值行 6、读取或比对行 13」。
- 代码实际：`controllers/update.js` 中 `S.update.requestId` 共 19 行；单等号赋值 5 行（第 37、54、64、99、132 行）。行内数字与代码一致，「计数说明」的 6/13 不对。
- 被审条目与位置：`desktop.md` 3.02 行与其「十、统计」下的计数说明段。
- 类别：计数不符。
- 严重度：次要。

### A5 4.09 的 refresh(true) 调用点数口径不清（次要）

- 原文（desktop.md 4.09）：「全仓 refresh(true) 的调用点（不含后台那一处）共 8 处，除这四处外还有 [[DSK-409g]]…[[DSK-409j]]；另有启动时的一次」。
- 代码实际：基线里非后台的 `refresh(true)` 调用共 9 处：`app.js:84`（启动）、`app.js:641`、`cancel.js:52`、`plan-events.js:123`、`plan.js:471`、`refresh.js:456`、`terms.js:354`、`terms.js:414`、`relogin.js:438`。md 列的是 409c–j 共 8 条，启动那一处单列，所以「共 8 处」应为 9，或者「共 8 处」应注明不含启动。
- 被审条目与位置：desktop.md 4.09 行；DSK-409c–j；基线 `local/ui/app.js:84` 等。
- 类别：计数不符。
- 严重度：次要。

### A6 DSK-409g 事实错（次要）

- 原文（DSK-409g）：「单场失败后的复查是无参数的前台刷新」。
- 代码实际：`plan-events.js:123` 是 `setTimeout(() => { S.recheckPending = false; refresh(true); }, 400);`，带了参数 `true`（`refresh` 的 quiet 参数）。它没有 `{background: true}`，所以「前台」这个说法大体对，「无参数」不对。
- 被审条目与位置：DSK-409g（`local/ui/controllers/plan-events.js:123`）；desktop.md 4.09 行里「都是无参数的 refresh(true)」的说法与之相同。
- 类别：事实错。
- 严重度：次要。

### A7 DSK-402b 引用不支撑（次要）

- 原文（DSK-402b）：「挂 130 秒兜底」，引用 `refresh.js:189`。
- 代码实际：`refresh.js:189` 只有 `S.round.listTimer = setTimeout(() => {`；`130000` 在 `refresh.js:202`。claim 的事实对，但引用范围没有覆盖证据。
- 被审条目与位置：DSK-402b（`local/ui/controllers/refresh.js:189`）；证据行在 `refresh.js:202`。
- 类别：事实错（引用不支撑）。
- 严重度：次要。应把引用范围改成 189–202。

### A8 DSK-134b 条件不完整（次要）

- 原文（DSK-134b）：「校验结论为 unknown 时胶囊文字」。
- 代码实际：`views/login.js:55` 的条件是 `S.login.result === "unknown" && ok === false`，claim 漏了 `ok === false`。
- 被审条目与位置：DSK-134b（`local/ui/views/login.js:58`）。
- 类别：事实错（条件遗漏）。
- 严重度：次要。

### A9 DSK-507a 的「只有」缺引用（次要）

- 原文（DSK-507a）：「只有以 stopped 结束才放回勾选；S.editing 保留」。
- 代码实际：`plan-events.js:17–25` 只有 `if (S.editing && S.plan.status === "stopped")` 分支；「只有」需要 else 分支或其他路径的引用，未引；「S.editing 保留」在引用范围内没有直接的写入或不写入的证据。
- 被审条目与位置：DSK-507a（`local/ui/controllers/plan-events.js:17–25`）。
- 类别：事实错（条件未引证）。
- 严重度：次要。

### A10 反引号形式的区间 id 不在脚本核对范围（次要）

- 原文（reconcile.md 第 120–121 行）：「新增引用条目 `DSK-409g` 到 `DSK-409j`」「新增条目 `DSK-231a` 到 `DSK-232b`」。
- 代码实际：脚本只核对 `[[id]]` 形式，这些反引号形式的 id 与区间写法没有被核对，它们是否存在也没有人查。
- 被审条目与位置：`reconcile.md:120–121`；`verify_cites.py` 的 `ID_RE`。
- 类别：漏项。
- 严重度：次要。

### A11 RUL-807 引用不支撑（次要）

- 原文（RUL-807）：「桌面组件缺失三个码带标题和提示」，引用 `refresh.js:377`。
- 代码实际：`refresh.js:377` 只有 `const RUNTIME_ERRORS = {`；三个码的 title 与 hint 在 378–380 行。事实对，引用不覆盖。
- 被审条目与位置：RUL-807（`local/ui/controllers/refresh.js:377`）；证据在 378–380。
- 类别：事实错（引用不支撑）。
- 严重度：次要。

### A12 W6 标签可以升级（次要）

- 原文（grab.md W6）：标「需测试定」，缺的一环是「有没有未读到的环节去掉时间戳」。
- 代码实际：中间没有去掉时间戳的环节（`plan_service.py:178` 只 rstrip，`:276` 直接解析），纯函数验证结果与 W6 的结论一致（见第 6.1 节）。读代码就能定。
- 被审条目与位置：grab.md W6；GRB-130；`local/application/plan_service.py:178、276`；`local/domain/retry_rules.py:25、34`。
- 类别：判断站不住（标签偏保守，缺的那一环已经可以读代码闭合）。
- 严重度：次要。W6 的结论本身成立，建议升级为事实，并保留最小进程测试作为确认。

### A13 desktop 1.22 的缺席结论标「属实」（次要）

- 原文（desktop.md 1.22）：「没有发现没清的路径」，标「属实」，依据「前端每条出口见 1.01；后端 DSK-121a 在 finally 里」。
- 代码实际：这是对全部出口的缺席结论，引用只覆盖了一部分（后端一处 finally、前端靠 1.01）。1.01 本身也只列了部分出口。
- 被审条目与位置：desktop.md 1.22；DSK-121a。
- 类别：推测当事实。
- 严重度：次要。建议改成「有条件属实」，或补全出口清单的引用。

### A14 grab W7 的缺席结论标「事实」（次要）

- 原文（grab.md W7）：「`selftest` 子命令没有任何测试和解析方，退出码没有读取方」，标「事实」。
- 代码实际：这是全仓缺席结论。引用只有 GRB-128（安装批处理调用 selftest），没有测试目录与全仓解析方的搜索依据。
- 被审条目与位置：grab.md W7；GRB-128。
- 类别：推测当事实。
- 严重度：次要。

## 8. 开工与收工

- 开工 `git log --oneline -3`：`7e2d31c fix(component): 导入装好后收掉旧的下载失败`、`e0054c4 docs(proposals): 前端采用 ES Modules 并留样机`、`5d95f34 docs(proposals): 工程化重构提案`。
- 开工 `git status --short`：`M design/proposals/engineering-refactor.md`、`?? .workbuddy/`、`?? design/evidence/2026-11-12/esm-verify/`、`?? design/evidence/2026-11-12/refactor-audit/`（与已知改动一致）。
- 中间文件：
  - 临时目录 `tempfile.mkdtemp()` 新建一个（W6 纯函数验证用），内含 `local/domain` 导出。
  - 另建一个临时目录（范围副本，`mkdir -p`，不是 mkdtemp）。这一个路径不符合「只用 mkdtemp 新建」的要求，我已在收工时删除。
  - 审计过程中我曾误把一份基线 `app.py` 写到 `$TMPDIR`，违反了「中间文件只放 mkdtemp 目录」的规则。已在发现后删除，内容未用于结论。
- 收工 `git status --short`（写入本文件前运行）：
  - `M CHANGELOG.md`
  - `M design/proposals/engineering-refactor.md`（已知）
  - `M local/application/login_service.py`
  - `M local/application/plan_service.py`
  - `M local/domain/plan_rules.py`
  - `M local/domain/worker_lines.py`
  - `?? .workbuddy/`（已知）
  - `?? design/evidence/2026-11-12/esm-verify/`（已知）
  - `?? design/evidence/2026-11-12/refactor-audit/`（已知，本轮 `redo/` 下的 `audit/` 与 `zcode/` 都在其中）
  - `?? local/tests/test_worker_line_stamp.py`
- **范围外改动**：收工时 `CHANGELOG.md`、`local/application/login_service.py`、`local/application/plan_service.py`、`local/domain/plan_rules.py`、`local/domain/worker_lines.py` 和 `local/tests/test_worker_line_stamp.py` 出现了改动，开工时没有。我没有打开这些文件的内容，也没有改动它们。它们与 W6（时间戳前缀）的修补看起来有关，但本审计的结论全部按基线 `7e2d31c` 下的代码作出，不反映这些未提交改动。如需对照，应由指挥会话另行核对。
