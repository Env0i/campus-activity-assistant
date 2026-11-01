# UI 问题记录：手机页与桌面高级功能（待 Codex 审阅后返修）

- 记录日期：2026-10-31
- 取证方式：用本机 Edge 通过 Playwright 按 iPhone 尺寸（390×844，deviceScaleFactor=2）渲染真实页面，注入假快照截图；截图存 `design/evidence/2026-10-31/`
- 结论先说：**业务逻辑是通的**（配对、会话、设备信任、重登、报名动作都已有测试覆盖），问题全在信息架构与视觉表达
- 本文只是问题清单与建议，**没有实施任何 UI 改动**；实施与否、怎么改由 Codex 定稿

## 一、手机页（`local/ui/m/`）

### 现状

一页到底、六张同权重白卡竖排，总高约 2700px（约 3 屏）：筛选 → 活动 → 重试设置 → 执行 → 日志 → 重新登录。

### 问题清单

| # | 现象 | 证据 | 影响 |
|---|---|---|---|
| M1 | 首屏约 40% 被筛选占掉（搜索框 + 两行 chips） | `2-main.png` 顶部 | 打开页面第一眼看不到"今天要参加什么" |
| M2 | 「重试设置」出现在手机主界面：尝试时长下拉 + 最多提交次数输入 | `2-main.png` 中部 | 这是桌面配置项，手机上改它没有意义；「0=不限」对普通用户是危险概念 |
| M3 | 「日志」区直接铺在页面上（"1. 已读取 3 条活动 / 2. 计划已排队，等待开放"） | `2-main.png` 下部 | 内部调试信息当正文，占屏且不可操作 |
| M4 | 「重新登录」整块在页面最底部，要滑约 3 屏才到 | `2-main.png` 最底 | 登录失效时用户看不到入口，只能靠公告文字 |
| M5 | 六张卡标题字号与权重一致（约 20px），没有主次 | 全图 | 读不出"哪个是我现在要做的事" |
| M6 | 「开始报名计划」是禁用态但没有任何说明 | `2-main.png` 执行区 | 用户不知道要先勾选活动 |
| M7 | 活动用浏览器原生 checkbox，触摸目标约 24px | `2-main.png` 列表 | 低于移动端 44px 触摸规范 |
| M8 | 顶部只有「这次报名 / 离线·未知 / 刷新」 | `2-main.png` 顶部 | 没有连接语义（是断网还是后台没跑）、没有"这是手机端"、没有书签提示 |
| M9 | 配对页一张卡贴屏幕顶端，下方约 700px 空白 | `1-pair.png` | 没说这是什么工具、谁在连、为什么值得连；也没有"扫码更快"的引导 |
| M10 | 视觉气质接近管理后台（灰底白卡蓝按钮），缺少"今天要办的事"的紧迫感 | 全图 | 与"人不在电脑旁、要快速确认"的使用场景不匹配 |

### 建议方向（供 Codex 取舍，不是定稿）

首屏只放"要做的事"：状态条（已连接 + 上次同步时间 + 刷新）→ 今天要参加（可勾选 + 直接「开始报名」）→ 即将开放 → 已报名（折叠）。筛选、日志、重试设置折成一行小入口，点开抽屉。登录失效时用顶部红条把人引到重登面板，而不是躺在页尾。配对页应说明用途并突出"扫二维码"这条更短的路径。

## 二、桌面帮助页 · 高级功能（`local/ui/views/phone.js` + `local/ui/index.html`）

| # | 现象 | 证据 | 影响 |
|---|---|---|---|
| D1 | **必修**：成功提示是**红色**（"账号信息已准备好。"） | `local/ui/styles.css:361` 基础色为 `var(--bad)`，只给 `[data-tone="warn"]` 覆盖了颜色，`info` 未定义；`helpStatus` 默认 tone 为 `warn` | 成功被读成错误；条款弹窗单独覆盖了 info 色，说明这是遗漏 |
| D2 | 「填写账号密码」与「保存到本机」语义重叠 | 用户截图 | 前者只是展开输入框，后者才是动作，但按钮主次不分 |
| D3 | 缺用途说明 | 用户截图 | 应写清「只用于电脑上无人值守重登；手机端永远看不到」 |
| D4 | 缺「最近使用时间」 | 用户截图 | 存了到底有没有用上完全看不出来 |
| D5 | 「清除已保存」没有二次确认 | `local/ui/index.html` 凭据区 | 误点即丢 |
| D6 | 「无人值守重登」与「账号与登录」两个同级标题 | 用户截图 | 看起来是两件事，实际是同一件事的两个前置条件，应合并成一张卡 |
| D7 | 保存凭据被 `feature_ready(RELOGIN_OCR)` 挡住（`local/app.py:992`） | 代码 | 不装 ddddocr 连账号都不能保存；而人工输码的手机重登并不需要 ddddocr |
| D8 | 缺「上次重登是否走了自动识别」回执 | 代码：`login_relay_service.py:377-386` 识别成功即自动提交，界面无提示 | 用户只能靠"没看到输入框"来推断 OCR 是否生效 |

### D1 的修法（一行 CSS，风险极低）

`local/ui/styles.css` 在 `.help-status[data-tone="warn"]` 旁边补一条：

```css
.help-status[data-tone="info"] { color: var(--ink-2); }
```

验收方式：`PhonePanel.saveCredentials()` 成功路径的提示文字颜色不再是 `var(--bad)`；
`local/tests/test_phone_ui.py` 已有断言覆盖「成功 / 失败」两种文案，颜色不参与断言，
所以建议同时加一条 `LayoutStaticTests` 静态断言（`styles.css` 含 `[data-tone="info"]`），
避免以后再被忽略。

## 三、本轮已实施的代码改动（已登记，不属于上述返修范围）

计划 `20261031-phone-access-channel` 结束之后，因用户真机反馈与要求，又做了以下改动，均已写入 `.claude/results/20261031-phone-access-channel-result.yaml` 的 `post_plan_changes`：

1. `local/infrastructure/tunnel_manager.py`：新增 `resolve_tailscale()`（Windows 安装包不写 PATH，探测永远 missing）。
2. `local/domain/phone_rules.py` + `local/infrastructure/phone_http.py`：`hosts_allowed()`/`origins_allowed()` + 按 scheme 分档的 `_allowed_hosts()`（帮助页承诺的 100.x 备用地址原先被 403 bad_host）。
3. `local/app.py` + `local/infrastructure/phone_http.py` + `local/application/phone_service.py`：`local/data/phone.log` 请求级日志（不记配对码、cookie 值、账号密码验证码）。
4. `local/application/phone_service.py` + `local/app.py` + `local/ui/{index.html,styles.css,views/phone.js}`：`pair_code_status()`（seq/reason/expires_in）、面板 5 秒轮询、换码提示、二维码按地址缓存。
5. `local/ui/views/phone.js` + `local/tests/test_phone_ui.py`：开启/关闭加进行中状态（`pending`；按钮显示「启动中…」「关闭中…」并禁用；启动中禁止改通道；连点只发一次请求）。
6. `local/infrastructure/tunnel_manager.py` + `.gitignore`：`cloudflared` 固定版本下载到 `local/bin/`（`local/bin/` 入 gitignore），公网链路 16 项验收全 PASS。

## 五、待 Codex 拍板的文案与交互（用户已认可方向，未实施）

| # | 待定项 | 现状 | 建议 |
|---|---|---|---|
| P1 | 「存书签」三处提示 | 只有帮助页第 4 步提到「重启不用重新扫码」，没告诉用户怎么做到 | ①帮助页第 4 步改成「扫码或手输地址 → 输配对码 → **把这个地址加入书签**」；②手机页配对成功后页头提示「已配对，分享 → 添加书签，下次直接打开」；③二维码旁小字「扫码只在首次用」 |
| P2 | 手机页信息架构 | 见 M1–M10 | 见第一节建议方向 |
| P3 | 账号与登录面板 | 见 D2–D8 | 合并成一张卡 + 用途说明 + 最近使用时间 + 清除二次确认 |
| P4 | 用户自主安装组件包 | 本轮由我下载 `cloudflared` 到 `local/bin/`；打包与用户自行安装方式未定 | 用户明确：**交给 Codex 决策** |

## 六、运行期发现（2026-10-31 10:05 真机）

| # | 现象 | 原因 | 建议 |
|---|---|---|---|
| R1 | 顶栏显示「北京时间 未校准」，活动区「活动加载失败」，运行记录只有「待校准 [OK] 已复用本机登录状态」 | 启动时一轮校时三个 NTP 源全部无响应（当时网络/代理在切换）→ `ClockUnavailable: 本轮没有可用的时间源响应`；程序按设计**拒绝在校时不可信时加载活动与开始报名** | 首轮校时失败后**自动退避重试**（建议 5s / 15s / 40s），而不是永远等人点「重新校时」；顶栏那条也建议做成可直接点的按钮并说明「点这里重试」 |
| R2 | 手机面板接口抛 `ClockUnavailable`（pywebview 回调 traceback，面板整块打不开） | 我新增的 `pair_code_status()` 直接调 `self._now()`，校时不可用时异常外泄到界面回调 | **已修**（见 post-008）：时钟不可用时返回 `{"code":"", "expires_in":0, "seq":…, "reason":"clock_unavailable"}` 降级，不阻塞面板 |
| R3 | 代理从没被产品显式处理，但事实上所有 `urllib` 请求都会跟随系统代理（含**学校接口与报名提交**） | `local/update_check.py:118`、`local/updater.py:85`、`local/grab.py:336/368/404/1050` 都用 `urllib.request.urlopen` 默认 opener；Windows 下会读注册表 `ProxyEnable/ProxyServer`。失败只说「连接超时 / 下载超时」，不提示「可能是代理」 | 建议按请求类型分层：学校接口/报名**强制直连**，更新与组件下载**允许代理**；详见交接材料 9.2（未实施，等 Codex） |
| R4 | 开发工具里硬编码了本机代理 | `tools/release.py:61` `PROXY = "http://127.0.0.1:7897"`，`:601` 写进 `HTTPS_PROXY` 环境变量 | 换成读环境变量或参数；只影响发版流程，不影响产品运行 |

## 四、未验证

- 手机页只在桌面 Edge 的移动模拟下渲染过，**没有在真实 iPhone Safari 上做视觉核对**（真机只验证了配对与恢复链路）。
- M 系列问题是信息架构判断，不是缺陷断言；是否需要重做由 Codex 与用户决定。
- D1 是确定缺陷（CSS 缺 `info` 分支），其余 D 系列属设计问题。

## 五、用户验收当场提出的新需求与处理（2026-10-31 下午）

| # | 用户诉求 | 处理 | 证据 |
|---|---|---|---|
| U1 | 「关闭应用界面但是可以后台运行」——原三选只有最小化/退出 | **已实现**：关窗四选（先不关 / 隐藏到后台运行 / 最小化到任务栏 / 直接退出）；隐藏后进程继续跑（手机访问、报名计划、校时都在），托盘图标可唤回，手机页「更多 → 显示电脑窗口」也能唤回；勾「以后都这样」把 `hide` 记进 `ui.json` 的 `window.close_action` | result `post-001`；托盘用 pythonnet + WinForms `NotifyIcon`（无新 pip 依赖），建不起来只降级、不影响主程序 |
| U2 | 关窗弹窗点出来后窗口「未响应」 | **已修**：`closing` 回调在 UI 主线程里调 `evaluate_js` 会抢 pywebview 内部锁；改为 `defer_close_action` 把界面动作挪到工作线程（amendment-009） | 真机复现 + 5 条回归测试 `WindowCloseHandlingTests` |
| U3 | Tailscale 探测每 5 秒闪一次 cmd | 已修（post-003）：`_hidden_window_kwargs()` 加 CREATE_NO_WINDOW；探测频率与语义不变 | 真机复测无闪窗 |

托盘图标当前用 `SystemIcons.Application`（仓库里没有 .ico 资源）。要做成有辨识度的图标，需要先放一个 `local/ui/icon.ico`，再在 tray_icon 里改用 `Icon(path)` —— 这一条留给 Codex 决定要不要做。
