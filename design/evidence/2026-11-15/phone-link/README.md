# 手机连接状态：抽屉 chip、顶栏标识与手机详情卡（2026-11-15）

组件状态机三小批的最后一批，做的是手机访问「开着以后连没连」。改前界面只分两档：
开着且「配过对或有活动会话」就是「手机已连接」，否则「等手机连接」。配过一次对之后手机走了，
界面照样说「手机已连接」——这就是这批要修的地方。

## 改了什么，为什么

| 转移 | 界面上现在长什么样 | 为什么这么改 |
|---|---|---|
| 后端说已断开（`link = disconnected`） | 抽屉 chip 与顶栏标识写「已断开 · N 分钟前」，标识不带 `is-ok`；详情卡小 chip「已断开」、大字同上一句 | 手机两分钟没来还写「已连接」，用户会以为推得进去 |
| 已断开 → 手机又来了 | 三处回到「手机已连接」，标识重新带 `is-ok` | 这是同一台机器的正常来回，不该要用户重开一次访问 |
| 开着但手机还没来过（`waiting`） | 三处「等手机连接」，提醒语气 | 原来这档只在「没配过对」时出现，现在按后端的事实说 |
| 后端没给 `link` 或给 `unknown` | 退回旧的两档规则（配过对或有活动会话即「手机已连接」） | 老快照与时钟不可用的情况下界面一字不变，不给用户一个没结论的状态 |
| 配过对、手机走了 | 说明行、配对码区、绿条、「再配一台」、详情卡的配对行**一个字不变** | 「配过对没有」是长期事实，「现在连着没有」是当下的状态，两件事不能混 |

做法上分开了两件事：`features/phone-access/state-link.js` 新加一份纯函数推导 `phoneLinkView`
（只回答「现在连着没有」，四种状态 `off` / `waiting` / `connected` / `disconnected`），
`state.js` 里原来的 `phoneLinkedNow` 继续回答「配过对没有」。顶栏那份重复的连接规则删掉，
顶栏标识与详情卡改调同一份推导（经 `legacy-globals.js` 挂回两个名字给普通脚本用）。
另外两台状态机各导出一份冻结的状态清单（`COMPONENT_STATES` / `COMPONENT_PROBES`、
`PHONE_LINK_STATES`），测试按清单核对推导只会返回清单里的值。

## 不变区（证明「配过对没有」那条线没有被动过）

`scripts/link_grid.py` 沿用上一批 `component-transitions/scripts/unchanged_grid.py` 的沙箱写法：

- 网格 192 格 = 手机访问开着与否 2 × `paired_count` 0/1 × `live_session` 真假 × `link` 六档
  （没有该字段、`unknown`、`off`、`waiting`、`connected`、`disconnected`）×
  `last_contact_ago_s` 四档（`null`、30、150、4000）。每格把设置抽屉与顶栏都画一遍（详情卡用
  `S.statusCard = {kind:"phone", pinned:false}` 打开），每格读 7 类属性
  （hidden / disabled / textContent / className / dataset.state / style.width / aria-valuenow）。
- 旧方：开工提交 `0621e98`（`git archive` 导出），新方：工作区。
- **配对类**（55 个元素：抽屉里除 chip 以外的手机访问元素 + 详情卡的配对行）：全部 192 格都参与比对，
  55 × 7 × 192 = **73920 条比对，不同 0 条**。
- **连接类**（6 个元素：抽屉 chip、顶栏标识与其文字、详情卡小 chip 与其文字、详情卡大字）：
  只在不变区（160 格）比对，6 × 7 × 160 = **6720 条比对，不同 0 条**。
- **变化区**：32 格（`waiting` 12 + `connected` 4 + `disconnected` 16），这 32 格里连接类元素全部确实变了，
  脚本按每种 `link` 打印样例（旧「手机已连接」→新「等手机连接」、旧「等手机连接」→新「手机已连接」、
  旧「等手机连接」→新「已断开」）。
- 自检（旧方与旧方自己比）：同样的 192 格，配对类 73920 条、连接类 6720 条都不同 0 条，
  变化区 0 格——说明这套比对不会把差异吃掉，也不会凭空造出差异。

复跑（仓库根）：

```
python -B design/evidence/2026-11-15/phone-link/scripts/link_grid.py --base-ref 0621e98
python -B design/evidence/2026-11-15/phone-link/scripts/link_grid.py --base-ref 0621e98 --new-ref 0621e98
```

## 变化区由谁守着

- `local/tests/test_phone_link.py`（新增，9 条）：等手机连接、已连接、已断开带分钟数、已断开但没有秒数、
  手机又来了、没开、后端没给 `link` 与给 `unknown` 的退回规则、配对块不跟连接状态走。
  每条都断言抽屉 chip、顶栏标识（含 `is-ok` 与 `data-link`）、详情卡小 chip 与大字这些用户看得到的结果。
- `local/tests/test_component_machine.py`（补 2 条）：两份组件清单与手机连接清单的输入网格断言
  （推导只会返回清单里的值，且清单里的每个值都真会出现）。

## 变异结论

`scripts/mutate_link.py` 在临时副本里一处一处改坏源码，再跑对应的用例（挂回那一行改由模块图守卫守）：

- 共 28 条变异，**全部变红，存活 0 条**，没有一条红在语法或导入上。
- 覆盖：`phoneLinkView` 的每条判断（没开、三种照用、退回规则、秒数是不是数字）、四处文字与两处语气、
  抽屉 chip 的取字/语气/`data-link`、顶栏标识的显隐/`is-ok`/文字/`data-link`、
  详情卡小 chip 与大字的取字与 `data-tone`、详情卡配对行改用的配对判断、三份状态清单的内容。
- 挂回那一行（`window.phoneLinkView = phoneLinkView;`）删掉后，普通脚本引用了模块里的名字却没有挂回，
  模块图守卫报 `unattached_module_names` 不为空——这一处**故意**不用界面用例守：测试夹具把模块函数直接
  变成全局名字，漏挂在界面测试里看不出来，只有真窗口会报 `ReferenceError`。
- 第一轮「详情卡配对行改成看活动会话」这条没红：当时的用例只比了「连着」与「走了」两格，两格里配对行
  都按同一个错误规则写，所以相等。补了「配对行要写已配对」的断言之后才变红——不是等价变异。

复跑：

```
python -B design/evidence/2026-11-15/phone-link/scripts/mutate_link.py
```

## 代码形状

- `paintPhoneAccess` 仍是 219 行（记录值没有变大，`tools/code_shape/baseline.json` 这一批不动）；
  新增文件 `state-link.js` 与新增函数都在 60 行以内。
- `ui_modules_expect.json` 重新生成后只多两个挂回名（`phoneLinkView`、`phoneLinkedNow`），五类问题为空；
  分层白名单没有加项。

## 与计划的偏差

- 计划说「必要时挂回 `phoneLinkedNow`」：实际挂了，因为详情卡的配对行原来是文件内的
  `phoneLinked(src)`，删掉那份重复规则后只能调挂回的名字，否则普通脚本拿不到模块作用域。
- `features/phone-access/state.js` 第 39 行有一句注释还写着「顶栏手机标识用同一条规则
  （views/status-cards.js phoneLinked）」，这句现在过时了；该文件不在本批可写范围，
  留给下一批顺手改，不影响行为。
