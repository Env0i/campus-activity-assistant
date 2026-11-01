# 手机页自适应同步与过时提示收敛（2026-10-31）

本文件只记事实与判据：**自动化跑通了，但没有做真机验收**，不能当验收结论用。

## 一、起因

手机页在手上前台待着的时候，`/api/state` 差不多每秒被请求一次。原实现里
`poll()` 每次结束都无条件 `schedule()`，而成功分支把 `backoff` 重置到 1000，
于是「退避」只对失败生效——稳定在线时等于一秒一轮。`wire()` 在页面打开时也
直接排了定时器，未配对的页面同样会持续请求；收到 401 之后没有统一撤表的地方，
只能靠下一次失败再退避。

同时 `PhoneModel.staleAfterMs` 是 5000：一旦把空闲周期放长到 15 秒，正常空闲
就会被判成「过时」，写入口（开始报名、手机上重登）会无故被锁死。所以周期与
过时门禁必须一起改，不能只改一个。

## 二、这次改了什么

`local/ui/m/app.js`：

- `PhoneModel` 增加 `IDLE_SYNC_MS = 15000`、`ACTIVE_SYNC_MS = 2000`，
  `staleAfterMs` 由 5000 改为 30000（两个空闲周期），并新增纯函数
  `reloginBusy(flow)` / `isActive(model)` / `syncDelay(model)`。
- 活动态判定覆盖：`busy`（报名计划在跑）、未完成的 `pending`（开始请求待对账）、
  `reloginStarting` / `reloginSubmitting`、以及 `login_relay` 的
  `starting` / `waiting_code` / `verifying` 与 `submit_pending`。
- `schedule()` 成为唯一排期入口：先清旧定时器，然后后台（`document.hidden`）、
  未配对（`model.paired` 为假）、有请求在途（`model.flying`）三种情况都不排；
  失败退避优先，退避清零后按活动态选 2 秒或 15 秒。
- `model.paired`：`poll` 成功置真、`pair()` 成功置真、401 经 `onNeedPair()` 置假
  并清表；`wire()` 首屏只调一次 `probeExistingSession()`——只有页面上还留着
  `campus_phone_csrf` cookie（说明这台手机配过对）才发一次只读状态请求，
  没有 cookie 就停在配对页，不请求也不排期。
- 回前台与 bfcache 恢复仍按事件游标补一次（`poll(false)`，不重放写动作）。

`local/tests/test_phone_ui.py`：

- node vm 装置把 `setTimeout` / `clearTimeout` 换成**可观测 registry**（`__timers`、
  `__timerDelays()`、`__fireTimers()`），回调不自动执行，`fetch` 与
  `AbortController` 语义未动。
- 新增 `PhoneSyncPolicyTests` 9 条：空闲 15 秒、忙碌 2 秒、重登在途算活动、
  后台停表、未配对不发请求、401 停表、30 秒前不算过时、成功只清过时提示、
  手动刷新单飞且只留一个定时器。
- 原「后台恢复按事件游标补齐」用例补了一句 `paired = true`：新契约下未配对的
  页面本来就不该在回前台时请求，这条断言的前提变了，不是把断言放宽。

`setBanner(text, kind)` 带最小来源标签（`stale_action` / `error` / `info`）：

- 开始报名、手机上重登因「状态过时」被挡下时写 `stale_action`；
- 403、启动失败等写 `error`；
- 成功快照只清 `stale_action`——读到新状态不等于网络或服务端错误已经解决。

## 三、同步参数是怎么来的

- 空闲 15 秒：手机只当遥控器，活动列表本身变化很慢；15 秒足够让「即将开放」
  的时间显示不失真，也把前台请求量压到原来的十几分之一。
- 活动 2 秒：报名计划在跑、开始请求待对账、重登在走流程时，界面上的状态与按钮
  每秒都在变，慢了会让人重复点。
- 过时 30 秒：`staleAfterMs` 必须大于空闲周期，否则「一切正常但就是点不动」。
  取两个周期（30 秒）而不是一个（15 秒），是为了容忍一次 8 秒超时加一次重试。
  **这三个数都是产品参数推导，不是学校接口的实测值。**

## 四、自动化结果（2026-10-31 晚）

| 检查 | 命令 | 结果 |
|---|---|---|
| 手机页行为 | `python -X utf8 -m unittest local.tests.test_phone_ui` | 73 tests OK |
| 全量本机 | `python -X utf8 -m unittest discover -s local/tests -p "test_*.py"` | 1379 tests OK（skipped=4） |
| Python 语法 | `python -X utf8 -m compileall local server` | exit 0 |
| 手机页语法 | `node --check local/ui/m/app.js` | exit 0 |
| 桌面页语法 | `node --check local/ui/app.js` | exit 0 |
| 空白/行尾 | `git -c core.whitespace=cr-at-eol diff --check` | exit 0 |

变异检查（脚本内联，逐条还原并核对文件字节一致）：

| 改动 | 结果 |
|---|---|
| `syncDelay` 固定返回 1000 | 「空闲 15 秒」变红 |
| 去掉 `schedule()` 的后台判断 | 「后台停表」变红 |
| 去掉 `onNeedPair` 里的 `paired = false` | 「401 停表」变红 |
| `clearStaleBanner` 改成清所有种类 | 「成功只清过时提示」变红 |
| 去掉 `poll` 的单飞判断 | 「手动刷新单飞」变红 |

文件编码：`local/ui/m/app.js`（846 行）、`local/tests/test_phone_ui.py`（1482 行）
均为严格 UTF-8、无 BOM、全 LF、无行尾空白、乱码黑名单 0 命中。

## 五、没有验证的部分

- **真机没跑**：手机锁屏、切后台、切 Wi-Fi/蜂窝、系统省电策略下的定时器行为
  都没有在真手机上观察过。桌面浏览器与 node vm 都无法代表 iOS/Android 的
  后台节流。
- 请求量下降的绝对幅度没有实测：只证明了「空闲时的延迟是 15000 毫秒」，
  没有在真机上数过一小时发出多少次。
- 学校当前没有可报名活动，报名/停止/取消这条主链路本轮仍未真机验证。
- 401 之后重新配对、再恢复自动同步的完整往返，只有单元测试覆盖。

## 六、复现方式

```bash
python -X utf8 -m unittest local.tests.test_phone_ui -v
python -X utf8 -m unittest discover -s local/tests -p "test_*.py"
node --check local/ui/m/app.js
git -c core.whitespace=cr-at-eol diff --check
```

## 七、真实手机验收清单

自动化结果不替代手机实测。此前未在真实手机上完成的刷新、后台、网络切换、重新配对和重登项目，统一收录在：

`mobile-ui-real-device-acceptance.md`

请优先执行其中的 A1、A2、A3、A4、B1、B2、B3、B4，并把结果填回该清单；学校没有真实活动时，报名、停止、取消项目记录为“暂缓”，不要伪造通过。

## 八、真机验收发现的四个缺陷与返修（同一日期，晚于上文）

第七节的清单在真机上跑过一轮之后暴露了四个问题。这一节只记录自动化证据与判据；
真机复验仍待用户执行。

### 8.1 现象与根因

| 编号 | 现象 | 根因 |
|---|---|---|
| E-1 | 每次打开手机页都显示「重登成功，正在刷新列表」 | 中继没有在途流程时返回上一场的结论快照，手机端拿 `state === "success"` 就当本次结果播报 |
| E-2 | 手机接管过一次之后，验证码就永远转到手机来输 | 自动重登把「中继 flow 被别的来源接管」记成一次失败，累计到阈值后判定为机器解决不了 |
| E-3 | 重登成功后桌面顶栏变了，「电脑续登录」卡片还是旧记录 | check 事件只刷新顶栏与列表，没有触发手机面板重取；且 check 被去重时这次刷新会被直接丢掉 |
| E-4 | Cloudflare 通道显示不可用，界面上却找不到任何安装组件包的入口 | 源码版 `feature_ready` 只看模块能否导入，segno 在就算 ready，于是「安装手机控制」按钮被隐藏，而通道要的是组件包 |

一条日志侧证：`local/data/phone.log` 中同一时段既有 `GET /api/state 200`，也有连续
`POST /api/action 403 bad_csrf`——「读得通、写不通」是当时 CSRF 令牌没跟着 cookie 换
的表现（已在第九节修掉），与本轮四个缺陷无关。

### 8.2 修法

- 中继公开状态新增 `live`：只有「这一场还在跑」才为真；终态（含刚收到的 success）
  与历史快照一律为假。手机端只按 `live` 播报成功/结束，历史结论写成「上次重登已完成 /
  上次重登未完成：原因」，且不再自动触发刷新。
- 「该不该把验证码交给手机」只在 `live` 流程里看 `attempts`；历史残留的尝试次数不再参与判定。
- 自动重登的 flow_id 变化分两种：中继里存在别的来源的进行中流程——释放槽位、不计失败；
  自己的流程消失——仍计失败。退避上限与成功清零不变。
- check 被去重时置「本轮结束后再查一次」，`_do_check` 收尾补跑一次（只补一次）；桌面
  `check` 事件末尾让手机面板重取一次快照，失败静默。
- 「安装手机控制」按钮的显隐改为：组件 ready 且通道没有报组件缺失才隐藏；通道报
  `cloudflared_missing` 时文案改成「安装/更换组件包」。

### 8.3 自动化判据

定向用例：

```bash
python -X utf8 -m unittest local.tests.test_login_relay_service local.tests.test_application_services -v
python -X utf8 -m unittest discover -s local/tests -p test_auto_relogin.py -v
python -X utf8 -m unittest local.tests.test_phone_ui local.tests.test_ui_contract -v
```

新增/改写的用例：

- `RelayLiveTests`：进行中的流程 live 为真、归档的 success 不是本次、无流程为假。
- `PhoneReloginTakeoverTests`：历史 attempts 不把手机锁进人工模式、已结束的流程 phone 端不是 live、
  历史快照不算「正在跑」所以点重登会真的开一场。
- `MonitorTests`：被别的来源接管不计失败；自己的流程消失仍计失败。
- `PhoneReloginRecoveryTests`：历史成功不重播、历史失败写成「上次重登未完成」。
- `DocAndCopySyncTests`：组件缺失时安装入口仍然可见、`check` 事件会刷新续登录卡、`PhonePanel` 显式挂到 window。

变异检查（改坏一处 → 对应用例必须变红，跑完按字节还原）：

| 变异 | 结果 |
|---|---|
| `live` 恒为真 | `RelayLiveTests` 红 |
| `attempts` 不再看 `live` | 历史失败用例红 |
| 接管仍记成失败 | 接管用例红 |
| 历史成功又播报成「重登成功」 | 历史成功用例红 |
| 组件包入口又藏起来 | 安装入口用例红 |

### 8.4 仍然没有验证的部分

- Cloudflare 通道的完整往返（装组件包 → 新地址 → 重新扫码）仍未真机跑过；组件包需要用户
  手动选择 ZIP 安装，本轮没有替代路径。
- 重登成功后桌面卡片刷新只在自动化里验证「会调用刷新」，真机上「最近一次登录」文案是否
  确实变了还要人看一眼。
- 报名/停止/取消主链路仍受「学校当前没有可报名活动」限制，记为暂缓。

### 8.5 本轮全量回归

```bash
python -X utf8 -m unittest discover -s local/tests -p "test_*.py"
```

- 第一次：`Ran 1392 tests` → `FAILED (errors=1, skipped=4)`。唯一的错误是
  `test_signup_plan.WorkerStopLifecycleTests.test_stop_kills_tree_cancels_task_and_emits_single_plan_done`
  里读假 worker 的 pidfile 得到空串（`ValueError: invalid literal for int() with base 10: ''`），
  发生在 `_start_and_wait_worker` 等 pidfile 的窗口里；该用例单独连跑 3 次全过（1.2–1.4 秒），
  判定为整包并发下的既有竞态，与本轮改动的四个文件无关。
- 第二次（同一工作区、未改任何文件）：`Ran 1392 tests` → `OK (skipped=4)`，退出码 0。

两次结果都留在 `%TEMP%` 下的日志里，按日期与结论引用；结论是「全量通过，但这条 worker 用例
在机器负载高时可能偶发空 pidfile」。

## 九、组件与通道：选文件、当场自检、再安装

第八节的修复让「安装/更换组件包」的入口重新可见，但点下去什么都不发生：源码版的
`install_advanced_feature` 走的是 `pip install`，既没有文件框也没有回执。更根本的问题是
Cloudflare 通道只认两种来源——「手机控制」组件包，或用户亲自选过并通过校验的一份
cloudflared——而源码版没有第一种，第二种入口此前不存在，于是通道永远不可用。

这一节记录换成「组件与通道」对话框之后的实现与判据。

### 9.1 界面口径

一个对话框，三行，每行只说一件事：

- 手机控制 · Cloudflare 通道：需要官方 `cloudflared.exe`（打包版也可导入
  `phone_control-*.zip`）。可以「选择文件…」或直接粘贴路径，然后「自检」，
  自检通过「安装这份」才可点。
- 无人值守重登 · 验证码识别：打包版需要 `relogin_ocr-*.zip`；源码版走 ddddocr，
  选 ZIP 不会生效，会直接说明。
- Tailscale：只读检测，不接收任何文件。它是系统软件，装法不该由本程序代管。

选错文件不回错误码，而是说清楚它是什么：「这是 Tailscale 的程序，不是 cloudflared」、
「这是「手机控制」的组件包，不是这里要装的「无人值守重登」」、「这个 ZIP 里没有组件清单
（manifest.json）」。程序不联网下载组件，也不猜路径。

### 9.2 落盘位置与校验

- 用户选定的 cloudflared 收进受管目录 `data/advanced/cloudflared/`，manifest 记
  `version` 与 `sha256`；`stored_cloudflared()` 每次使用前核版本 + 哈希 + 再跑一次
  `--version`，任一不符就当没有。
- `cloudflared()` 的查找顺序变成：组件包优先，受管二进制兜底；两条都不通过才返回空串。
- 复制之后重新 probe 一次：选文件时的结论不能代表落盘后的那一份，落盘后版本不符就回滚。

### 9.3 自动化判据

```bash
python -X utf8 -m unittest local.tests.test_component_packages -v
python -X utf8 -m unittest local.tests.test_application_services -v
python -X utf8 -m unittest local.tests.test_ui_contract -v
python -X utf8 -m unittest discover -s local/tests -p "test_*.py"
```

新增用例：`inspect_cloudflared` 五种结论（缺失、非 exe、版本不符、Tailscale、读不出）+
识别成功；`install_cloudflared` 收好并写清单、拒绝 Tailscale、落盘后被篡改则失效；
`inspect_archive` 认得出「别的组件的包」与「不是组件包」；`Api` 层自检选错 exe 会点名
Tailscale、选对则安装并刷新通道路径、源码版选 ZIP 返回 `source_build`；
界面契约锁住「安装按钮默认不可点」「帮助页两个安装按钮只打开对话框」「Tailscale 行没有选文件按钮」。

本轮全量：`Ran 1406 tests / OK (skipped=4)`。

### 9.4 一处排版返工

第一版用两列网格排每一行（左标题、右说明），结果说明文字把标题列挤成一字一行，
按钮也缩到左侧窄条里——真机截图一眼就能看出不成形。改成单列：标题+状态一行、
说明一段、路径输入与「选择文件…」一行、动作按钮一行，正文区自己滚动。
当时在 Chrome 中渲染 `ui/index.html`（760×940）取证；原始截图含本机路径，仅保留本地，不入库。

### 9.5 没有验证的部分

- 真机上「选择文件…」弹的是 Windows 文件框，本轮只用替身验证了取值与分支；
  真机弹框、被占用文件、路径含空格与中文都还要人手点一遍。
- 装好 cloudflared 之后 Cloudflare 通道真正跑通（出临时域名、手机重新扫码）仍需真机往返。
- 打包版的 ZIP 导入路径本轮没有重新验证（构建产物与上一轮相同）。
