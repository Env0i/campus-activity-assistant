# 计划栏标题区的分支清单（动手前先列一遍）

对象是 `local/ui/features/plan/view.js` 的 `paintSelected`（124 行）。它先做三件固定的事——`box.className = "b-title"`、清空 `#selected-meta` 的 innerHTML、清空 `#board-text` 的 textContent——再按下面的先后落进其中一个分支就 `return`。

标签一律经 `setBoardTag(text, tone, dot)` 写：`#board-tag` 的 `dataset.tone`、`dataset.dot`（`false` 才写字符串 `"false"`，否则 `"true"`）、`#board-tag-text` 的 textContent。标题写 `#selected` 的 textContent；副行写 `#board-text`，除「时间待校准」那一支用 innerHTML，其余都是 textContent；地点时间那一行只写 `#selected-meta` 的 innerHTML，且只有「下一场 / 开放中」两支写。

| # | 进入条件（原文） | 阶段 | 标签 / 色调 / 圆点 | 标题 | 副行 | 地点时间 |
|---|---|---|---|---|---|---|
| 1 | `!S.busy && S.login.present === false && !S.runtime.error` | `first_use` | 首次使用 / off / 有 | 登录后开始 | text：活动会在登录完成后自动加载。 | 不写 |
| 2 | `S.login.loginPending` | `logging_in` | 登录中 / amber / 有 | 正在打开登录窗口 | text：在浏览器里登完再回来；中途关掉窗口会保留原来的登录状态。 | 不写 |
| 3 | `resultMode()` | `result` | `resultView().tag` / `resultView().tone` / 有 | `resultView().title` | text：`resultView().text` | 不写 |
| 4 | `termsHold && !items.length`，`termsHold = !S.busy && termsLocked() && S.login.present !== false` | `terms_hold` | 已暂停 / off / 有 | `S.terms.unknown ? "重新确认条款后才能报名" : "同意条款后才能报名"` | text：unknown 时「登录、活动列表和报名计划暂时停用。帮助和设置照常可用。」，否则「登录、活动列表和报名计划都停用了。帮助和设置照常可用。」 | 不写 |
| 5 | `!S.busy && S.runtime.error && S.listState !== "ready"` | `broken` | 不可用 / red / 有 | 暂时不能报名 | text：程序组件缺失，处理办法在顶部提示里。 | 不写 |
| 6 | `!S.busy && S.listState === "error" && !S.items.length` | `list_error` | 需重试 / red / 有 | 活动暂时没加载 | text：具体原因看左边列表的提示。 | 不写 |
| 7 | `!S.busy && S.listState === "loading" && !items.length` | `list_loading` | 加载中 / off / 有 | 活动列表正在加载 | text：先等这一次加载结束。 | 不写 |
| 8 | `S.busy` 且 `view.phase` 是 `submitting` / `arming` / `waiting` | `run_target` | `runTagText(view)` / submitting 时 red，否则 amber / 有 | `view.item ? view.item.name : "这一场活动"` | text：`runCaption(view)` | 不写 |
| 9 | `S.busy` 且其余，`view.phase === "settling"` | `run_settling` | 汇总中 / amber / 有 | 正在汇总结果 | text：每一场都结束了，正在汇总这一轮的结果。 | 不写 |
| 10 | `S.busy` 且其余，`view.phase` 不是 `settling` | `run_preparing` | 准备中 / amber / 有 | 正在准备报名 | text：计划已经接管，正在核对每一场的开放时间。 | 不写 |
| 11 | `!items.length` 且 `next` 且 `stateOf(next) === "open"` | `next_open` | 开放中 / amber / 无 | `next.name` | 不写（清空） | innerHTML：`boardMetaHtml(next)` |
| 12 | `!items.length` 且 `next` 且 `stateOf(next) !== "open"` | `next_upcoming` | 下一场 / amber / 有 | `next.name` | 不写（清空） | innerHTML：`boardMetaHtml(next)` |
| 13 | `!items.length` 且没有 `next`，`S.listState === "ready" && !S.items.length` | `school_empty` | 暂时没有 / off / 有 | 学校当前没有活动 | text：稍后刷新再看。 | 不写 |
| 14 | 同上且 `S.listState === "ready" && bnowS() === null && !S.demo` | `clock_pending` | 时间待校准 / amber / 有 | 时间待校准 | innerHTML：「校准北京时间后才能判断哪些场次可以报名。」+ 一个 `data-open-clock` 按钮 | 不写 |
| 15 | 同上且 `S.listState === "ready"`（其余） | `none_eligible` | 暂时没有 / off / 有 | 没有可报名的场次 | text：列表里的活动已报名、已截止或还没公布报名时间。 | 不写 |
| 16 | 同上，`S.listState` 不是 `ready` | `none_upcoming` | 暂时没有 / off / 有 | 近期没有要开放的活动 | text：可能还没公布报名时间，也可能都报过了。过一会儿点「刷新」看看。 | 不写 |
| 17 | `items.length` 且 `termsHold` | `selected_paused` | 已暂停 / off / 有 | `"已选 " + items.length + " 场"` | text：`selectionSummary(items)` | 不写 |
| 18 | `items.length` 且非 `termsHold` 且 `S.editing` | `editing` | 修改中 / amber / 有 | `"已选 " + items.length + " 场"` | text：`selectionSummary(items)` | 不写 |
| 19 | `items.length` 且非 `termsHold` 且非 `S.editing` | `selected` | 报名计划 / amber / 有 | `"已选 " + items.length + " 场"` | text：`selectionSummary(items)` | 不写 |

## 判断先后（改结构时必须逐条保住）

1. 首次使用最先，但它要求「没在跑 + 从没登录过（`present === false`）+ 组件没坏」。
2. 登录中第二，压过结果页与后面一切——登录尝试期间 `S.busy` 也是真，不能画成报名计划。
3. 结果页第三，压过条款暂停、组件坏、列表态与草稿态。
4. 条款暂停只压「没选活动」这一侧；选了活动要落到 17 而不是 4。
5. 组件坏 / 列表失败 / 加载中三支都要求「没在跑」，且后两支还要求手上一场也没有（`!items.length`）。
6. 在跑的三支压过下面所有空态与草稿态。
7. 没选活动时，「有下一个目标」压过四种「暂时没有」；四种「暂时没有」内部按 `listState === "ready"` 分成两半，再按「学校 0 场 / 没可信现在 / 其余」排。
8. 选了活动时，条款暂停 > 修改中 > 报名计划。

## 与代码逐字对应的一处细节

`paintSelected` 在分支之前就算好了 `items`、`next`、`view`，并把 `#selected-meta` 与 `#board-text` 清空。这四件事在新结构里仍然放在查表之前，写 DOM 的方式（`className`、`innerHTML`、`textContent` 的区别）逐字保留。

原分支里那几段注释（运行中以 `executionView()` 为唯一目标、登录尝试期间 `S.busy` 也为真、结果页不写地点时间、加载态与有没有选中无关、运行中三个阶段分开说、选了活动的标题一律「已选 N 场」）在改结构时原样挪到样子表对应那一项旁边，一字不改。

## 一处已知现状（这一批不改，写进文档）

浏览器登录时 `S.busy` 也为真：`boardPlanState` 因此给外框 `data-plan-state=running`（运行色），而标题区这一支写「登录中」。外框随登录、开始请求的确认中与结果未确认、停止没成功、修改中并入草稿这些画板上的新转移，留给第二小批。
