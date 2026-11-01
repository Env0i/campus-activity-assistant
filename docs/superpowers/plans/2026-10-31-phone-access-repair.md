# 手机远程控制台与重登体验返修 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox ( - [ ] ) syntax for tracking.

**Goal:** 把手机访问从“能连上”收敛为真正可用的电脑远程控制台，同时修复 D1 成功提示颜色、北京时间校时失败后的自动退避重试、桌面续登录入口、可选组件分发、窗口关闭与代理边界。

**Architecture:** 保留现有 local/ui → local/app.py → application/domain/infrastructure 分层。手机端只调用现有电脑动作白名单，活动选择、报名计划、停止、单场取消、查看结果和重登都由电脑端执行；手机不增加独立业务模型。Tailscale 是长期通道，Cloudflare Quick Tunnel 是临时通道；设备信任、配对码、校时和凭据继续沿用现有安全边界。

**Tech Stack:** Python 3.10+、标准库 unittest、pywebview/WebView2、HTML/CSS/JavaScript、Node vm 行为测试、Windows DPAPI、现有 cloudflared/组件包机制。

## Global Constraints

- 只服务当前用户本人账号；不增加多账号、批量占位或未明确指定活动的报名能力。
- 手机是电脑的远程控制台：手机发出的是电脑动作，电脑负责学校请求、报名执行和状态裁决。
- 远程产品入口只有 Tailscale 与 Cloudflare；不增加普通局域网、公网 IP 或 IPv6 入口。
- Tailscale 配对后的设备信任可跨程序/电脑重启恢复；Cloudflare Quick Tunnel 每次重启或重新开启都要重新配对。
- 手机控制与 ddddocr 是两个独立的可选高级功能；不自动安装、升级或移除组件。
- 没有 ddddocr 也允许保存账号密码；自动续登录需要凭据和 OCR，手机人工续登录只需要凭据。
- 验证码没有倒计时和提交次数上限；每次验证码提交必须防重复提交，错误由学校响应触发换图，不由客户端猜测次数。
- 校时失败绝不回退系统时间；首轮失败后按 5 秒、10 秒、20 秒、之后每 30 秒重试，成功后清除退避。
- P1 三处统一文案：“打开后建议加入手机书签，方便下次访问。”
- 关闭窗口采用“最小化 / 退出 / 以后都这样”三选，默认最小化；报名计划运行中每次都再次确认。不增加系统托盘、隐藏窗口或开机自启。
- 学校请求强制直连；更新与组件下载允许系统/环境代理；移除 tools/release.py 的本机硬编码代理；不新增代理编辑界面。
- 不引入新依赖；不修改 local/data、server/data、.venv、node_modules，不改变学校接口契约或登录态文件形状。
- 不把账号、密码、验证码、配对码、cookie 值或 token 写入日志、文档、提交信息或 UI 快照。
- 修改含中文的文件后执行严格 UTF-8 解码和乱码黑名单检查；保持既有行尾，不做全文件格式化。
- 本轮计划默认不提交 Git；构建、测试、真实手机验收和提交都在执行阶段分别获得授权。

## Confirmed decisions and assumptions

### 已拍板 P1–P9

1. P1：帮助页手机访问区、手机配对成功后的地址/复制区域、二维码下方都放统一书签提示；Cloudflare 旁边必须保留“临时地址、重启后要重新配对”的事实提示。
2. P2：手机页按“远程控制台”重做，首屏优先今天要参加的活动和可执行动作；筛选、重试策略、运行记录收进“更多”；视觉沿用桌面端候车厅/白色时刻表/黑底琥珀 LED 的主体风格。
3. P3：桌面帮助页合并为一张“电脑续登录”卡，显示整体状态、OCR 状态、凭据状态、最近使用时间/方式，并明确自动识别和手机人工输入两条路径。
4. P4：可选功能按需安装；手机控制组件带匹配版本的 cloudflared；组件独立校验、存放、移除，不自动安装或升级。
5. P5：保存凭据不再要求 ddddocr；自动续登录要求 OCR + 凭据，手机人工续登录只要求凭据。
6. P6：关闭窗口弹出“最小化 / 退出 / 以后都这样”，默认最小化；报名计划运行中始终再确认。
7. P7：学校请求强制直连；更新和组件下载跟随系统/环境代理；移除开发脚本硬编码代理，不增加代理设置 UI。
8. P8：Cloudflare 只做临时/应急通道，重启后重新开启并重新配对；Tailscale 是长期免重扫通道。
9. P9：校时失败按 5 秒、10 秒、20 秒、之后每 30 秒重试；成功后停止退避。

### 执行时采用的无歧义假设

- 不新增手机专用后端业务接口；继续使用现有 start_plan、stop_plan、cancel_task、save_retry_policy、phone_relogin_* 和状态快照。
- “最近使用时间/方式”只记录非敏感元数据（时间、auto_ocr 或 phone_manual），不记录账号、验证码或 token。
- “书签提示”是文案提示，不做浏览器无法可靠控制的自动加入书签按钮。
- Cloudflare 不增加看门狗自动重启；只检测退出、清空失效地址并提示重新开启。

## Design freeze（先评审，再写 UI）

这部分是执行前必须保持的视觉方向，所有 UI 代码都要遵守 frontend-design 技能与项目既有风格。

**Token：**沿用 local/ui/styles.css 的 --hall #e8ecef、--paper #fff、--ink #1a1f24、--blue #1e5a8c、--board #121513、--amber #ffb020、--ok、--warn、--bad；数字继续使用 Bahnschrift/Segoe UI，中文继续使用 Microsoft YaHei UI。手机 CSS 通过同名或等价变量继承这套颜色，不再使用当前手机页独立的亮蓝 SaaS 色板。

**Layout：**桌面帮助页维持窄卡片、细边线和工具行；手机页以单栏、44px 触摸目标、状态优先为准。主操作使用黑底/蓝色动作，琥珀只表示“即将开放/时间提醒”，红色只表示失败或会中断的动作。

**手机远程控制台线框：**

~~~text
┌──────────────────────────────┐
│ 校园活动        已连接  刷新 │
│ 上次同步 10:32   [书签提示]  │
├──────────────────────────────┤
│ 登录已失效：在手机上续登录   │
├──────────────────────────────┤
│ 今天要参加                    │
│ □ 活动名       开放 09:00    │
│ □ 活动名       开放 14:30    │
│              [开始报名计划]  │
├──────────────────────────────┤
│ 即将开放   1 场        查看   │
│ 已报名     2 场        展开   │
├──────────────────────────────┤
│ 更多                         │
│  筛选 · 重试设置 · 运行记录   │
└──────────────────────────────┘
~~~

**桌面“电脑续登录”卡线框：**

~~~text
┌──────────────────────────────────────────┐
│ 电脑续登录                    已准备 / 未准备 │
│ 账号密码只供这台电脑的重登流程使用。         │
│ 凭据  已保存：user***   最近使用：10:32       │
│ OCR    已启用 / 未安装                       │
│ 自动续登录   凭据 + OCR，电脑自动识别验证码   │
│ 手机人工     凭据即可，验证码在手机上输入      │
│ [填写账号密码] [保存到本机] [清除]            │
│ 清除确认： [先不清除] [确认清除]              │
└──────────────────────────────────────────┘
~~~

自我检查：没有增加顶层入口，没有把六个同权重卡片搬到手机上，没有引入渐变/大圆角卡片套件，也没有把内部日志或重试参数放在首屏。

---

### Task 1: 修复 D1 成功提示颜色并加静态守护

**Files:**
- Modify: local/ui/styles.css（.help-status 与 data-tone="warn" 相邻处）
- Test: local/tests/test_phone_ui.py 或 local/tests/test_ui_contract.py

**Interfaces:**
- Consumes: helpStatus(text, "info") 的现有数据属性。
- Produces: data-tone="info" 始终使用普通说明色，不再继承错误红色。

- [ ] **Step 1: 写失败断言**

~~~python
css = (LOCAL / "ui" / "styles.css").read_text(encoding="utf-8")
self.assertIn('.help-status[data-tone="info"] { color: var(--ink-2); }', css)
~~~

- [ ] **Step 2: 写最小 CSS 修复**

~~~css
.help-status[data-tone="warn"] { color: var(--warn); }
.help-status[data-tone="info"] { color: var(--ink-2); }
~~~

- [ ] **Step 3: 定向验证（执行阶段需测试授权）**

~~~powershell
python -X utf8 -m unittest local.tests.test_phone_ui local.tests.test_ui_contract -v
~~~

预期：D1 静态断言通过，既有帮助页行为断言不下降。

---

### Task 2: 为 BusinessClock 增加 5/10/20/30 秒退避状态机

**Files:**
- Modify: local/business_clock.py（BusinessClock.__init__、sync()、_background_loop()、snapshot()）
- Test: local/tests/test_business_clock.py
- Test: local/tests/test_business_clock_wiring.py（只在需要验证 Api 快照字段时修改）

**Interfaces:**
- Consumes: 现有 tick_fn、可注入 transport、_wakeup 和三源 SNTP 采样。
- Produces: snapshot() 新增无凭证字段：

~~~python
{
    "sync_status": "pending|syncing|succeeded|failed",
    "sync_round": 3,
    "retry_attempt": 2,
    "retry_in_s": 10.0,
    "last_failure_source": "ntp.aliyun.com",
    "last_failure_reason": "timeout",
}
~~~

- [ ] **Step 1: 写假时钟/假 transport 测试**

测试使用同一个 FakeTick，不调用真实 UDP：

~~~python
class FakeTick:
    def __init__(self):
        self.value = 0.0
    def __call__(self):
        return self.value

def test_failed_rounds_schedule_5_10_20_then_30_seconds(self):
    tick = FakeTick()
    attempts = []
    def transport(source, packet, timeout):
        attempts.append((source, tick.value))
        raise OSError("timeout")
    clock = BusinessClock(
        sources=["a", "b", "c"], tick_fn=tick, transport=transport,
        snapshot_dir=self.tmp.name, owner_id="retry-test",
        per_source_cooldown_s=0, background=False,
    )
    self.assertEqual(clock.sync(), "unavailable")
    self.assertEqual(clock.snapshot()["retry_in_s"], 5.0)
    tick.value = 5.0
    self.assertEqual(clock.sync(), "unavailable")
    self.assertEqual(clock.snapshot()["retry_in_s"], 10.0)
    tick.value = 15.0
    self.assertEqual(clock.sync(), "unavailable")
    self.assertEqual(clock.snapshot()["retry_in_s"], 20.0)
    tick.value = 35.0
    self.assertEqual(clock.sync(), "unavailable")
    self.assertEqual(clock.snapshot()["retry_in_s"], 30.0)
    tick.value = 65.0
    self.assertEqual(clock.sync(), "unavailable")
    self.assertEqual(clock.snapshot()["retry_in_s"], 30.0)
    self.assertTrue(attempts)
~~~

实际实现必须让“未到 retry_at 的后台循环”不发起新轮；不能只断言字段数字而让 sync() 手动绕过调度门禁。

- [ ] **Step 2: 写成功后停止退避的测试**

使用可切换 fake transport：前几轮抛 OSError，之后返回现有测试中的合法一致 NTP 样本。断言：

~~~python
snap = clock.snapshot()
self.assertEqual(snap["sync_status"], "succeeded")
self.assertEqual(snap["retry_attempt"], 0)
self.assertEqual(snap["retry_in_s"], 0.0)
self.assertEqual(snap["last_failure_source"], "")
~~~

- [ ] **Step 3: 记录安全的源和原因**

在 _one_source() 异常分支只记录来源和白名单原因（timeout、dns_error、bad_packet、peer_mismatch、transport_error），不记录原始异常文本、IP、凭据或请求内容。三源失败时保留最多三条摘要，snapshot() 对外只给最近一条作为顶栏文案来源。

- [ ] **Step 4: 接入后台循环**

采用以下确定规则，不能用系统墙钟：

~~~python
def _retry_delay_s(failure_count):
    if failure_count <= 0:
        return 0.0
    return (5.0, 10.0, 20.0)[min(failure_count - 1, 2)] \
        if failure_count <= 3 else 30.0
~~~

失败后把 retry_at_tick = self._tick() + _retry_delay_s(failure_count)；成功后把 failure_count、retry_at_tick 和失败摘要清零。_background_loop() 等待 min(resync_interval_s, retry_in_s)，被 request_resync() 唤醒时允许立即发起一次手动重校。已有 300 秒正常重校保持不变。

- [ ] **Step 5: 运行定向测试（需测试授权）**

~~~powershell
python -X utf8 -m unittest local.tests.test_business_clock local.tests.test_business_clock_wiring -v
~~~

预期：旧时钟契约、worker ClockClient 契约和新增退避测试全部通过；任何失败都不得返回系统 time.time() 作为业务时间。

---

### Task 3: 把校时退避状态接到桌面顶栏和详情浮层

**Files:**
- Modify: local/app.py（clock_snapshot()、sync_clock()、事件载荷）
- Modify: local/ui/index.html（顶栏时钟增加可访问的重试提示节点）
- Modify: local/ui/state/clock.js
- Modify: local/ui/views/clock.js
- Modify: local/ui/views/clock-pop.js
- Modify: local/ui/controllers/clock.js
- Test: local/tests/test_ui_contract.py

**Interfaces:**
- Consumes: Task 2 的 retry_attempt、retry_in_s、last_failure_source、last_failure_reason。
- Produces: 顶栏保留“北京时间”语义，失败时明确出现“正在重试”或“点这里重试”；详情浮层显示下一次重试倒计时、失败来源和安全原因。

- [ ] **Step 1: 固定状态文案**

~~~javascript
const CLOCK_COPY = {
  ready: { label: "已校准", explain: "报名时间和倒计时均以北京时间为准。" },
  syncing: { label: "正在校准…", explain: "正在获取网络时间。报名计划需在校准完成后启动。" },
  retrying: { label: "正在重试", explain: "时间服务暂时没有响应，工具会按 5 秒、10 秒、20 秒、每 30 秒重试。" },
  unavailable: { label: "时间校准失败", explain: "报名计划暂不可启动；点这里立即重试。" },
};
~~~

- [ ] **Step 2: 顶栏状态可点且不改变门禁**

顶栏继续使用现有 button#clock，只补 #clock-retry-hint 文案和 aria-label：当 sync_status === "failed" 且 retry_in_s > 0 时显示“正在重试（约 N 秒后）”；点顶栏仍打开详情，详情里的“重试校准”立即调用现有 sync_clock。不得在 UI 中用本机 Date 计算报名时间。

- [ ] **Step 3: 详情显示诊断而非堆栈**

clock-pop.js 在“最近校准”旁增加“下一次重试”“最近失败来源”“最近失败原因”。缺字段显示“暂无记录”；不得显示异常对象、DNS 地址、代理凭据或请求正文。

- [ ] **Step 4: 加 UI 契约断言**

静态测试至少断言以下文本和字段存在：正在重试、点这里重试、retry_in_s、last_failure_source、last_failure_reason；同时断言 CLOCK_COPY 没有系统时间兜底路径。

- [ ] **Step 5: 运行前端检查（需测试授权）**

~~~powershell
node --check local/ui/app.js
node --check local/ui/state/clock.js
node --check local/ui/views/clock.js
node --check local/ui/views/clock-pop.js
python -X utf8 -m unittest local.tests.test_ui_contract -v
~~~

---

### Task 4: 合并桌面“电脑续登录”卡并解除保存凭据的 OCR 前置条件

**Files:**
- Modify: local/app.py（advanced_features_state()、save_relogin_credentials()、prepare_phone_relogin()、_begin_auto_relogin()、成功回执）
- Modify: local/application/login_relay_service.py（安全传递 origin/方法）
- Modify: local/application/auto_relogin.py（状态快照补充最近自动使用信息）
- Modify: local/ui/index.html（合并后的卡片和确认行）
- Modify: local/ui/views/phone.js（卡片状态投影、保存/清除确认）
- Modify: local/ui/styles.css
- Test: local/tests/test_phone_ui.py
- Test: local/tests/test_login_relay_service.py
- Test: local/tests/test_auto_relogin.py
- Test: local/tests/test_credential_store.py

**Interfaces:**
- advanced_features_state() 的 credential 快照至少提供：

~~~python
"credential": {
    "store_available": True,
    "saved": True,
    "username": "只显示脱敏账号",
    "ocr_ready": False,
    "automatic": {"state": "waiting", "failures": 0, "retry_in": 0},
    "last_used": {"at": 0.0, "method": "auto_ocr|phone_manual", "label": "自动识别|手机人工输入"},
}
~~~

available 可暂时作为 store_available 的兼容别名，但 UI 不再把它解释为 OCR 是否安装。

- [ ] **Step 1: 先写后端边界测试**

~~~python
with mock.patch.object(app._advanced_features, "feature_ready", return_value=False), \
     mock.patch.object(app._credential_store, "save") as save:
    result = api.save_relogin_credentials("user", "secret")
self.assertTrue(result["ok"])
save.assert_called_once()
~~~

再断言：没有 OCR 时 prepare_phone_relogin() 能从已保存凭据准备手机人工路径；_auto_relogin_eligible() 仍要求 OCR 和凭据同时满足。

- [ ] **Step 2: 改后端条件，不改自动路径门禁**

save_relogin_credentials() 只检查 DPAPI 凭据存储是否可用和账号密码是否非空；删除 feature_ready(RELOGIN_OCR) 的前置判断。prepare_phone_relogin() 读取已保存凭据时不再检查 OCR。_begin_auto_relogin() 和 _classify_captcha() 保留 OCR 门禁。

- [ ] **Step 3: 记录最近使用方式**

LoginRelayService 在成功回调中传递安全 origin：auto 映射为 auto_ocr，phone 映射为 phone_manual。Api 只把业务时间（可用时）和方法写入现有偏好；不写账号、验证码或 token。兼容现有无参回调测试，更新测试后确保成功回调仍只触发一次。

- [ ] **Step 4: 写桌面卡 UI**

新增稳定 DOM id：

~~~text
#relogin-card
#relogin-overall-status
#relogin-ocr-status
#relogin-credential-status
#relogin-last-used
#relogin-auto-path
#relogin-phone-path
#relogin-clear-confirm
#btn-relogin-clear-cancel
#btn-relogin-clear-confirm
~~~

卡片必须直接写清：自动续登录是“保存凭据 + ddddocr，电脑自动识别验证码”；手机人工续登录是“凭据即可，验证码在手机上输入”；密码只用于本机重登流程，手机端永远看不到。保存成功使用 data-tone="info"；清除先显示确认行，只有确认按钮才调用 clear_relogin_credentials。

- [ ] **Step 5: 更新行为测试**

覆盖：OCR 与凭据状态互不串台、没有 OCR 仍能保存、清除未确认不发请求、自动和手机人工最近方式文案正确、失败时清空密码输入框。

- [ ] **Step 6: 运行定向测试（需测试授权）**

~~~powershell
python -X utf8 -m unittest local.tests.test_phone_ui local.tests.test_login_relay_service local.tests.test_auto_relogin local.tests.test_credential_store -v
~~~

---

### Task 5: 将手机页重构为电脑远程控制台并落地三处书签提示

**Files:**
- Modify: local/ui/m/index.html
- Modify: local/ui/m/styles.css
- Modify: local/ui/m/app.js
- Modify: local/ui/index.html（桌面帮助页书签文案和二维码下方提示）
- Modify: local/ui/views/phone.js（配对成功/地址复制区域的提示）
- Modify: local/ui/styles.css
- Test: local/tests/test_phone_ui.py
- Test: local/tests/test_ui_contract.py

**Interfaces:**
- 继续使用现有 PhoneUI/PhoneModel 和 /api/state、/api/action；不新增手机独立数据模型。
- 保留现有请求 ID、事件游标、单飞轮询、后台恢复只读补齐、写操作不自动重放、验证码无倒计时和重复提交保护。

- [ ] **Step 1: 先写关键结构断言**

静态/行为测试断言以下节点存在且由现有 API 驱动：

~~~text
#conn
#last-sync
#login-expired-banner
#today-items
#btn-start
#upcoming-items
#signed-summary
#more-panel
#filter-panel
#retry-panel
#logs-panel
#relogin-panel
#bookmark-hint
~~~

行为测试至少断言：勾选活动后 start_plan 的 args.items 来自电脑快照；停止、取消和重登调用现有 action；状态快照中的 plan 和 login_relay 能恢复到对应卡片；旧 request_id 不会重复发起报名。

- [ ] **Step 2: 重排手机首屏**

index.html 顺序固定为：连接状态/最近同步 → 登录失效引导 → 今天要参加 → 即将开放 → 已报名折叠 → 更多抽屉。筛选、尝试时长、最大提交次数和日志不再首屏铺开；“开始报名计划”只有选择可执行活动后启用，禁用时说明“先选择可报名活动”。

- [ ] **Step 3: 增强手机活动卡**

活动行使用整行触摸目标至少 44px，保留可报名/已报名/已截止/时间待确认状态；点击选择只影响本机计划选择，不直接提交学校请求。计划运行中显示电脑端真实状态、提交次数、停止入口和未确认提示。

- [ ] **Step 4: 把重登放到可见位置**

登录失效时在首屏红色状态条提供“在手机上续登录”；重登卡显示验证码图片、人工输入、提交、换一张图、取消和成功/失败结果。验证码错误或密码错误只由后端真实消息驱动刷新，不显示倒计时，不设置客户端次数上限。

- [ ] **Step 5: 统一三处书签提示**

原文必须逐字为：

~~~text
打开后建议加入手机书签，方便下次访问。
~~~

放置位置：帮助页手机访问状态区、手机配对成功后的 #bookmark-hint、桌面二维码容器下方。Cloudflare 区域紧邻显示临时地址警告，避免把临时域名误认为长期书签。

- [ ] **Step 6: 按桌面视觉基线重写手机 CSS**

使用桌面色板、Microsoft YaHei UI、黑底/琥珀状态提示和细边线；保留 44px 触摸尺寸、键盘焦点、prefers-reduced-motion。不引入图标字体、渐变背景或新的 UI 框架。

- [ ] **Step 7: 运行手机 UI 检查（需测试授权）**

~~~powershell
python -X utf8 -m unittest local.tests.test_phone_ui local.tests.test_ui_contract -v
node --check local/ui/m/app.js
node --check local/ui/views/phone.js
~~~

---

### Task 6: 固化可选组件与 Cloudflare 二进制的匹配分发边界

**Files:**
- Modify: local/infrastructure/component_packages.py
- Modify: local/infrastructure/tunnel_manager.py
- Modify: local/infrastructure/advanced_features.py
- Modify: local/app.py（高级功能状态中明确 cloudflared 缺失原因）
- Test: local/tests/test_component_packages.py
- Test: local/tests/test_component_builder.py
- Test: local/tests/test_tunnel_manager.py

**Interfaces:**
- phone_control 包的 manifest 必须声明匹配版本的 bin/cloudflared.exe；component_packages.cloudflared() 只返回通过完整 manifest/hash/helper probe 的路径。
- relogin_ocr 与 phone_control 独立校验、独立启用、独立移除；移除一个组件不删除另一个组件或 DPAPI 凭据。
- 组件导入只接受用户明确选择的 ZIP；不在启动、开启通道或检测状态时下载/安装/升级。

- [ ] **Step 1: 写 manifest 约束测试**

在现有 ZIP 替身中增加 bin/cloudflared.exe，断言缺文件、哈希不匹配、版本不匹配和 helper probe 失败时 Cloudflare 状态为不可用，且原组件保留。

- [ ] **Step 2: 固定版本来源**

沿用当前已批准的固定 cloudflared 版本（现有交付记录为 2026.10.7），版本值只出现在组件 manifest/构建输入中；运行期不访问下载地址，不执行自更新。

- [ ] **Step 3: 验证 UI 状态投影**

断言“手机控制已启用但 cloudflared 缺失”时只禁用 Cloudflare 通道并保留 Tailscale；不得把 ddddocr 状态串到手机控制状态。

- [ ] **Step 4: 运行组件定向测试（需测试授权）**

~~~powershell
python -X utf8 -m unittest local.tests.test_component_packages local.tests.test_component_builder local.tests.test_tunnel_manager -v
~~~

---

### Task 7: 实现窗口关闭三选与运行中计划的强制确认

**Files:**
- Modify: local/app.py（pywebview events.closing、关闭决策、request_window_close）
- Modify: local/ui/index.html（关闭选择对话框）
- Modify: local/ui/app.js 或新增 local/ui/controllers/window.js
- Modify: local/ui/styles.css
- Test: local/tests/test_ui_contract.py
- Test: local/tests/test_application_services.py

**Interfaces:**
- 偏好键：window.close_action，允许值 ask、minimize、exit；缺失值按 ask，对话框默认焦点为“最小化”。
- 关闭请求 API：request_window_close("minimize"|"exit"|"remember_minimize"|"remember_exit")；非法值不改变状态。
- plan 为 ready/running 或存在未收口 worker 时，忽略已保存的直接动作，始终先显示确认。

- [ ] **Step 1: 写关闭决策纯函数测试**

~~~python
self.assertEqual(resolve_close_action({}, plan_running=False), "ask")
self.assertEqual(resolve_close_action({"window": {"close_action": "minimize"}}, False), "minimize")
self.assertEqual(resolve_close_action({"window": {"close_action": "exit"}}, True), "ask")
self.assertEqual(resolve_close_action({"window": {"close_action": "bad"}}, False), "ask")
~~~

- [ ] **Step 2: 接入可取消 closing 事件**

window.events.closing 处理器先读取计划状态；需要询问时返回 False 并通过现有 UI 打开三选对话框。选择“最小化”调用 window.minimize()，选择“退出”进入现有 Api.shutdown() 收尾；设置“以后都这样”只写 ui.json，不创建托盘或隐藏窗口。

- [ ] **Step 3: 增加 UI 行为断言**

断言存在三项按钮、默认最小化文案、运行中确认文案和 window.close_action；断言没有 pystray、window.hide() 或开机自启入口。

- [ ] **Step 4: 执行关闭路径检查**

执行阶段授权后先做静态/单元检查，再由用户进行真实窗口验收：空闲时三选可用，选择最小化后任务栏仍可恢复，计划运行中每次 × 都再次确认。

---

### Task 8: 按请求类型拆分代理策略

**Files:**
- Modify: local/grab.py（学校请求 opener/调用点）
- Modify: local/update_check.py（保留系统/环境代理）
- Modify: local/updater.py（保留系统/环境代理）
- Modify: tools/release.py（移除硬编码 127.0.0.1:7897）
- Test: local/tests/test_signup_transport.py 或新增 local/tests/test_network_policy.py
- Test: local/tests/test_update_check.py
- Test: local/tests/test_updater.py

**Interfaces:**
- 学校请求统一走独立直连 opener：

~~~python
from urllib.request import ProxyHandler, build_opener

_SCHOOL_OPENER = build_opener(ProxyHandler({}))

def _school_urlopen(request, timeout):
    return _SCHOOL_OPENER.open(request, timeout=timeout)
~~~

- 更新检查和安装器下载继续使用默认 urlopen，从环境变量/Windows 系统代理读取代理。
- tools/release.py 只在环境中已经提供 HTTPS_PROXY 时沿用，不再写入任何本机固定地址。

- [ ] **Step 1: 先写代理隔离测试**

替换 opener.open() 为记录桩，断言学校登录、活动、报名请求都通过直连 opener；更新/下载测试断言仍调用默认 opener，不把学校 opener 全局安装到 urllib。

- [ ] **Step 2: 替换学校请求调用点**

逐个替换 local/grab.py 中学校接口的 urlopen 调用；保留请求头、超时、签名、重试和响应解析，不重写报名时序。

- [ ] **Step 3: 清理发布脚本代理**

删除 PROXY = "http://127.0.0.1:7897" 和无条件写入 HTTPS_PROXY 的逻辑，改为复制现有环境并让调用者自行决定是否提供代理。

- [ ] **Step 4: 运行网络策略定向测试（需测试授权）**

~~~powershell
python -X utf8 -m unittest local.tests.test_signup_transport local.tests.test_update_check local.tests.test_updater -v
~~~

---

### Task 9: 固化 Tailscale/Cloudflare 生命周期与真实验收入口

**Files:**
- Modify: local/application/phone_service.py（如需区分重启恢复与临时通道状态）
- Modify: local/infrastructure/phone_http.py
- Modify: local/infrastructure/tunnel_manager.py
- Modify: local/ui/views/phone.js
- Modify: local/ui/index.html
- Modify: docs/PHONE_ACCESS.md
- Modify: local/README.md（只补当前使用入口，不回改历史过程记录）
- Test: local/tests/test_phone_service.py
- Test: local/tests/test_phone_http.py
- Test: local/tests/test_tunnel_manager.py
- Test: local/tests/test_phone_ui.py

**Interfaces:**
- Tailscale：选择、开启、配对一次后，正常退出并重新启动程序/电脑，固定地址与设备信任恢复，手机不再要求配对码。
- Cloudflare：程序重启或隧道退出后地址清空；重新开启得到新域名，必须重新扫码和输入配对码。
- 关闭手机访问：撤销设备信任和当前会话；取消关闭确认不发停止请求。

- [ ] **Step 1: 写通道生命周期回归测试**

覆盖：Tailscale restore_phone_access() 只在偏好选择 Tailscale 时调用；Cloudflare 不自动恢复；CloudflareTunnel.status() 发现进程退出后清空旧 URL；帮助页对两种通道显示不同的持久性说明。

- [ ] **Step 2: 保持地址与配对边界**

二维码只编码当前地址；配对码不进入二维码、URL、日志或 cookie；Tailscale MagicDNS 优先、100.x 备用；Cloudflare 永不发长期设备信任 cookie。

- [ ] **Step 3: 更新用户文档**

把“电脑常驻 + Tailscale 才能随时从外面打开”“Cloudflare 临时地址重启后要重新配对”“手机控制电脑活动报名/续登录”写入 docs/PHONE_ACCESS.md 与 local/README.md 的当前入口说明。文档只写日期、结论和复现命令，不写临时目录或本机绝对路径。

- [ ] **Step 4: 准备用户真机验收**

用户与 DS 按以下流程验收，Codex 不把自动化绿灯当作验收结论：

1. 电脑安装并启用手机控制，选择 Tailscale，手机扫二维码并输入配对码；确认手机看到“今天要参加”、已报名、执行结果和重登入口。
2. 手机选择一场明确要报名的活动，电脑端出现对应计划；手机停止/取消后电脑端状态同步，不能重复发起同一个请求。
3. 电脑关闭并重新启动；Tailscale 地址仍可打开且不再要求配对。
4. 改用 Cloudflare，关闭再开启；确认新域名出现，旧书签失效，手机必须重新扫码并输入配对码。
5. 未安装 ddddocr 时保存凭据并走手机人工验证码；安装 OCR 后再验自动续登录；两条路径都显示最近使用方式。
6. 点窗口 ×：空闲时看到三选；选择最小化后可从任务栏恢复；计划运行中每次都再次确认。

---

### Task 10: 统一回归、编码门禁和交付报告

**Files:**
- Test: local/tests/ 受本计划影响的测试文件
- Modify: design/evidence/2026-10-31/（只在用户真机验收后归档截图/结论）
- Modify: .claude/results/（执行阶段由计划执行器生成，不在本轮手写）

- [ ] **Step 1: 运行全套本机测试（需单独授权）**

~~~powershell
python -X utf8 -m unittest discover -s local/tests -p "test_*.py" -v
~~~

预期：既有 178 项基线不下降，新增校时、UI、组件、代理和关闭行为测试全部通过。

- [ ] **Step 2: 运行语法与构建检查（需单独授权）**

~~~powershell
python -X utf8 -m compileall local server
node --check local/ui/app.js
node --check local/ui/m/app.js
node --check local/ui/views/phone.js
node --check local/ui/state/clock.js
node --check local/ui/controllers/clock.js
~~~

预期：所有命令退出码为 0。

- [ ] **Step 3: 运行 diff/编码门禁**

~~~powershell
git diff --check
~~~

对所有本轮修改的中文文件做严格 UTF-8 解码，并执行项目规定的乱码黑名单检查；发现命中立即停止，不叠加修复。

- [ ] **Step 4: 审计范围和验收状态**

最终报告分开写：执行状态、自动化验证状态、用户真机验收状态、未验证范围、plan_amendments、是否提交。自动化通过不得写成“用户已验收”；本轮计划默认 git commit 为 false。

## Spec coverage self-review

- D1 成功提示颜色：Task 1。
- R1 5/10/20/30 秒自动重试、来源/原因、顶栏重试、假时钟+假源测试：Task 2–3。
- P1 三处书签提示：Task 5、Task 9。
- P2 手机远程控制台与桌面视觉基线：Design freeze、Task 5。
- P3 电脑续登录卡、OCR/凭据/最近方式：Task 4。
- P4 按需组件、匹配 cloudflared、独立校验/移除：Task 6。
- P5 保存凭据解除 OCR 前置、自动/人工条件区分：Task 4。
- P6 关闭三选、默认最小化、运行中强制确认：Task 7。
- P7 直连学校、代理更新下载、清理 release 硬编码：Task 8。
- P8 Tailscale 持久、Cloudflare 临时重配对：Task 9。
- P9 校时节奏：Task 2–3。
- 安全边界、编码、无新依赖、无提交：Global Constraints、Task 10。

计划中的接口名、DOM id、字段名和测试命令已在任务内给出；没有使用“优化一下”“适当处理”“以后补充”等占位描述。
