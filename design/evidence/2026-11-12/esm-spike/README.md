# ES Modules 可行性验证 —— 样机结论

**日期**：2026-11-12
**样机位置**：`design/evidence/2026-11-12/esm-spike/`
**样机只做验证，产品代码零改动**

## 总判断：可行，建议迁移

V1–V6 六个检查项全部给出肯定结论。前端改用 ES Modules（`import`/`export` + `<script type="module">`）不碰到任何底层障碍。唯一需要注意的是 pywebview 6.x 的几个行为细节（内置 http_server 报错未留证据、见 V4，必须主线程调 `start()`），这些是 pywebview 使用层的约束，不是 ESM 本身的问题。

> 注意：样机用的是 pywebview 6.2.1。产品 `local/requirements.txt` 声明 `pywebview>=5.0`，实际运行版本需迁移时核对。

---

## V1–V6 逐项结论

### V1 桌面加载 —— 可行

**问题**：pywebview 窗口加载本地文件（`file://`）时，ES Modules 会不会被 WebView2 拦截？同时测试 HTTP server 模式。

**复现命令**：
```
python spike.py --scenario A   # file:// 直接加载
python spike.py --scenario B   # 样机自起的标准库 HTTP 服务
```

**结论**：产品同款的本地文件加载（场景 A）与样机自起 HTTP 服务（场景 B）两种方式下，`main.mjs → chain.mjs → leaf.mjs` 的 import 链都完整走通，所有模块顶层代码执行。

**关键证据**（场景 A、B 的 runOrder 一致）：
```
['legacy-top', 'leaf-top', 'chain-top', 'main-top', 'dom-load-fired', ...]
```

**重要发现**：场景 A 用的是与产品相同的加载方式（`create_window` 直接传本地 `index.html` 路径、不开 `http_server`），在这种方式下模块链能完整执行。样机没有记录 `location.protocol`，所以没有证明底层一定走 file:// 协议，只证明「产品现在的加载方式不需要额外起 HTTP 服务就能用模块」。`engineering-refactor.md` 第 73 行「WebView2 会拦截 file:// 下的模块脚本」的担心，在这个场景里没有出现。

### V2 桥接 —— 可行

**问题**：ESM 下 Python ↔ JS 双向桥接（`js_api` 和 `evaluate_js`）会不会受影响？`pywebviewready` 事件与模块执行的先后顺序？

**复现命令**：
```
python spike.py --scenario C
```

**结论**：
- Python → JS（`evaluate_js` 调模块暴露的 `window.apiBridgeMain.pongFromPython(...)`）：✅ 成功返回值
- JS → Python（`window.pywebview.api.ping(42)`）：✅ Python 端收到参数 42 并返回 84，但前端拿到的是 **Promise**

**顺序**：模块顶层代码在 `pywebview` bridge 注入 **之前** 就执行完了。runOrder 里 `main-top` 出现在 `pywebview-appeared-after-100ms` 之前，间隔约 100ms。如果模块顶层代码需要调 pywebview，要轮询等 `window.pywebview` 出现，不能假设它同步存在。

**注意**：前端调用 js_api 拿到的一直是 Promise；产品的 `local/ui/controllers/bridge.js` 的 `api()` 已经用 `Promise.resolve` 包装，所有调用点本来就按异步处理，这一条对迁移没有额外影响。

### V3 新旧混用 —— 可行

**问题**：同一页面里先放普通脚本、后放模块脚本，执行顺序如何？互相能不能调用？

**复现命令**：
```
python spike.py --scenario D
```

**结论**：
- 执行顺序：普通脚本先执行（DOM 解析阶段立即执行），模块脚本等 DOM 解析完 + 所有 import 下载完才执行。顺序稳定为 `legacy(0) < leaf(1) < chain(2) < main(3)`。
- 普通脚本调模块：模块挂 `window.apiBridgeMain = {...}`，普通脚本直接 `window.apiBridgeMain.callLegacyFoo()` ✅
- 模块调普通脚本：普通脚本挂 `window.legacyGlobal = {...}`，模块直接 `window.legacyGlobal.foo()` ✅

**对现有启动顺序的影响**：当前 `index.html` 按固定顺序加载 state/、views/、controllers/、app.js 的普通脚本。改 ESM 后入口只放一个 `<script type="module" src="app.js">`，app.js 内部 `import './state/xxx.js'` 等。执行顺序从"HTML 声明顺序"变成"模块拓扑顺序（叶子先、根后）"。对现有全局函数互相调用的代码，只要各模块顶层也把对外接口挂到 `window` 上（过渡期做法），调用关系不会变；完全模块化后可以逐步去掉 `window` 依赖。

### V4 内置 HTTP 服务 —— 可行（绕开 pywebview 内置）

**问题**：pywebview 内置 `http_server=True` 能不能用？监听地址是 127.0.0.1 还是 0.0.0.0？退出后端口是否释放？

**结论**：
- 场景 B、C、D 实际用的是样机自己起的标准库 HTTP 服务（`spike.py` 的 `_OwnHTTPServer`，运行日志里的 `[httpd] serving` 即它），**不是** pywebview 内置的 `http_server`。
- pywebview 内置 `http_server=True` 的 Bottle 报错（`BottleServer.asset() missing 1 required positional argument: 'file'`）是样机运行时的观察，本目录日志里没有留下原始输出，记为「未留证据的观察」，不作为已验证结论。
- 既然场景 A 已证明产品现有加载方式可用，桌面端迁移不需要内置 HTTP 服务。
- **替代方案**：自己起 `python -m http.server` 或 `ThreadingHTTPServer` 作为文件服务器，pywebview 加载 URL 指向这个 server，**不要给 `webview.start()` 传 `http_server=True`**。
- 监听地址：pywebview 内置 server 硬编码 `127.0.0.1`（源码 `http.py:151`），自己起的 server 也绑定 `127.0.0.1`。局域网其他机器访问超时（`socket.connect_ex` 返回非 0）。
- 端口释放：`server.shutdown() + server.server_close()` 后 1 秒内能 re-bind 同一端口 ✅。

### V5 手机页安全头下的模块加载 —— 可行

**问题**：`phone_http.py` 的安全头（CSP `script-src 'self'` + `X-Content-Type-Options: nosniff` + Referrer-Policy + Cache-Control）下，ES Modules 能不能加载？

**复现命令**：
```
python serve.py    # 起标准库 http.server + pywebview 加载
```

**实际下发的安全头**（与产品 `SECURITY_HEADERS` 完全一致）：
```
Content-Security-Policy: default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'
X-Content-Type-Options: nosniff
Referrer-Policy: no-referrer
Cache-Control: no-store
```

**结论**：`main.mjs → chain.mjs → leaf.mjs` 在这组安全头下完整加载。`X-Content-Type-Options: nosniff` 要求 MIME 类型正确——`.mjs` 在 Python mimetypes 里返回 `text/javascript`（与 `.js` 相同），不触发嗅探。

**PHONE_STATIC 白名单扩展方案**：

现状 `PHONE_STATIC` 是手工登记的路径白名单（`/`, `/index.html`, `/styles.css`, `/app.js`, `/favicon.ico`, `/apple-touch-icon.png`）。ES Modules 引入后 import 链里的 `.mjs` 文件会被浏览器动态请求，有三种方案：

1. **手工登记**：每新增 `.mjs` 都在 `PHONE_STATIC` 加一条。缺点是 import 链里新出现的模块需要同步改 Python。
2. **按扩展名放行**：在 `do_GET` 里加 `if path.endswith('.mjs')` 分支，配合 `resolve()` + 路径边界校验防止目录穿越。
3. **混合（推荐）**：保留 `PHONE_STATIC` 用于 `index.html` / `favicon.ico` 等精确路径，新增 `path.endswith(('.mjs', '.js', '.css', '.svg'))` 分支放行前端资产目录内的文件。好处是 import 链里出现任何新 `.mjs` 都能被浏览器自动发现和请求，server 只需要放行，不需要 Python 手工登记。

**自动发现机制**：ES Modules 的 `import './chain.mjs'` 是浏览器在解析到 import 语句后自己发起 HTTP GET 的，server 只要允许对应路径就够了，**Python 不需要解析 ES import 语句**。

**指挥会话结论**：手机页服务对外开放，不采用按扩展名放行（方案 2、3）。迁移时保留显式登记，另加一条测试：从入口模块递归解析 import，断言每个被引用的模块都已登记在 `PHONE_STATIC` 里，漏登记就红。

### V6 测试工具 —— 可行

**问题**：前端改 ESM 后，现有两种测试思路（Python `read_ui_scripts()` 拼接脚本做文本断言；Node 沙箱回放做行为断言）还有等价方案吗？

**复现命令**：
```
node harness.mjs
```

Node v24.16.0 下直接跑，**不需要 npm install、不需要 package.json、不需要 --experimental-vm-modules**。

**两种替代方案**：

| 维度 | Part A：递归读源码 | Part B：动态 import + mock DOM |
|---|---|---|
| 替代 | `read_ui_scripts()` | `run_phone_js`（Python 端） |
| 做法 | 正则提取 `import ... from 'xxx'`，递归去重 + 拓扑排序，聚合源码后做文本断言 | `await import('file:///<绝对路径>/app.mjs')` 前注入极简 mock（document.window 互相指向、createElement、appendChild、body.innerHTML、textContent），然后调模块导出的函数做行为断言 |
| 依赖 | 零（简单正则 + 文件 IO） | 零（原生 ESM 动态 import，不是 vm.SourceTextModule） |
| 断言数 | 6/6 通过 | 6/6 通过 |
| 适合测 | 模块结构、导出签名、import 关系 | DOM 操作行为、返回值、状态变化 |

Part B 的 mock 是极简实现：只覆盖 demo 模块需要用到的方法。实际迁移时需要把 mock 抽成测试基础设施，覆盖更多 DOM API（例如 `querySelectorAll`、`addEventListener` 的解绑、CSS 计算值等）。这是工作量估算里的主要增量之一。

---

## V7 PyInstaller 打包检查清单（宿主机执行）

**样机不打包**——PyInstaller 打包交给用户在宿主机执行。以下是需要关注的检查点：

### 基本命令

```
# 从项目根执行（假设样机代码已复制到宿主机对应路径）
python -m PyInstaller --noconfirm --onefile --windowed ^
  --add-data "desktop/web;desktop/web" ^
  --add-data "phone/web;phone/web" ^
  spike.py
```

注意：`--add-data` 在 Windows 上用分号 `;` 分隔源和目标路径（PyInstaller 的 `os.pathsep`），不能用冒号。

### onefile 下 HTTP server 文件根

PyInstaller onefile 模式下，运行时会把资源解压到临时目录（`%TEMP%\_MEIxxxxxx`）。起 HTTP server 时文件根必须指向解压后的目录：

```python
import sys
if getattr(sys, 'frozen', False):
    base_dir = sys._MEIPASS          # PyInstaller onefile 解压目录
else:
    base_dir = Path(__file__).parent / 'web'
```

如果起的是标准库 `ThreadingHTTPServer`，`directory` 参数传 `base_dir` 即可。pywebview 加载的 URL 指向 `http://127.0.0.1:{port}/`。

### 打包后验证清单

1. **启动速度**：onefile 每次启动要解压，比源码态慢几秒。这和当前 PyInstaller 打包行为一致，不是 ESM 特有的问题。
2. **HTTP server 能不能正确 serve 资源**：onefile 解压到临时目录后，server 从 `sys._MEIPASS` 读文件能不能正常返回。
3. **ESM import 链完整**：`main.mjs → chain.mjs → leaf.mjs` 能不能全部加载，页面有没有模块缺失错误。
4. **桥接通道**：前端调 `window.pywebview.api.ping(42)` 能不能成功（前端拿到的是 Promise，见 V2）。
5. **退出后端口释放**：关闭窗口后 HTTP server 端口是否释放，不影响下次启动。
6. **安全头**（手机页）：打包后 server 返回的 CSP + nosniff 是否完整下发。

### 不需要做的事

- 不需要 `importlib.resources` 或其他资源访问库——标准库 `open(path, 'rb')` 在 PyInstaller onefile 解压目录下正常工作。
- 不需要把 `.mjs` 显式加入 PyInstaller 的 `.spec` 文件——只要整个 `web/` 目录 `--add-data`，`.mjs` 就会一起被打进去。
- 不需要处理 MIME 类型——Python mimetypes 对 `.mjs` 返回 `text/javascript`，不触发 nosniff 警告。

---

## V8 迁移建议

### 迁移顺序（建议）

1. **`local/ui/` 前端**：先把 state/、views/、controllers/ 改 ESM。入口 `index.html` 只留一个 `<script type="module" src="app.js">`。各模块顶层把对外接口先挂到 `window` 上（过渡期），逐步改成 import/export 直接引用。
2. **`local/ui/m/` 手机页**：和桌面前端同步改。`PHONE_STATIC` 用混合方案扩展（见 V5）。
3. **测试**：把 `read_ui_scripts()` 替换成递归 import 解析（Part A 方案），把 node 沙箱回放替换成动态 import + mock DOM（Part B 方案）。先改一两个文件的测试跑通再全量推。
4. **`local/app.py` pywebview 升级**：js_api 调用已按异步处理（见 V2），升级时没有 Promise 适配工作。同时从内置 `http_server=True` 切换到自己起的标准库 server（如果需要 HTTP server）。
5. **打包**：PyInstaller `.spec` 文件补 `--add-data` 把前端目录整个打进去，onefile 模式下 server 文件根指向 `sys._MEIPASS`。

### 工作量粗估

| 模块 | 主要工作 | 估时 |
|---|---|---|
| `local/ui/` 改 ESM | 拆大文件为多个模块、加 import/export、入口改单模块加载 | 3–5 天 |
| `local/ui/m/` 手机页 | 同步改 ESM + PHONE_STATIC 混合方案 | 1–2 天 |
| 测试改造 | 递归 import 解析器 + mock DOM 基础设施 + 逐文件替换断言 | 2–3 天 |
| pywebview 升级 | 自己起 HTTP server + onefile 路径（js_api 无需 Promise 适配） | 0.5–1 天 |
| 构建与联调 | PyInstaller 测试、安全头验证、真窗口验收 | 1–2 天 |
| **合计** | | **约 7.5–13 个工作日** |

### 主要风险

1. **js_api 调用的异步语义**：前端调用 js_api 拿到的一直是 Promise；产品 `local/ui/controllers/bridge.js` 的 `api()` 已经用 `Promise.resolve` 包装，所有调用点本来就按异步处理，迁移没有额外风险。
2. **pywebview 内置 http_server 报错**：样机运行时观察到 `BottleServer.asset()` 报错，但没有留下原始输出，属于「未留证据的观察」（见 V4），未经验证。如果升级 pywebview 或 bottle 后修复，是否继续用内置 server 需要重新评估。目前保守建议：自己起标准库 server，不依赖 pywebview 内置。
3. **模块拆分后的循环依赖**：从全局函数互相调用改成 ESM import/export 后，原来通过全局作用域绕开的循环依赖会被强制暴露出来。建议迁移时按"叶子先、根后"的拓扑顺序分批拆分，避免引入新循环。
4. **PyInstaller onefile 解压竞态**：极少数情况下 PyInstaller onefile 解压临时目录还没完全解压好，HTTP server 就开始 serve 了。解决方法是 server 起之前先 `sys._MEIPASS` 目录存在性检查 + 等待。
5. **mobile 真实浏览器验证**：样机只在 WebView2 下测了安全头 + ESM。手机上的真实浏览器（Safari on iOS、Chrome on Android）的 WebView 组件对 CSP + nosniff + ESM 的组合行为可能和 WebView2 有差异。建议实际部署时在至少一台真机上验证。

### 退回方案（如果出现阻断）

迁移过程中如果遇到**任何一项不可行**（例如 pywebview 某个版本组合下 js_api 调用不可用、PyInstaller onefile 解压路径确实找不到、或者真实移动端 Safari 拦截），退回"命名空间对象 + 调用关系测试"方案：

- 每个功能模块对外暴露一个命名空间对象（`window.AppAPI.state = {...}`、`window.AppAPI.views = {...}`），不引入 ESM import/export。
- 用测试守住"谁能调谁"的边界（`test_layer_boundaries` 扩展到前端）。
- 保持普通脚本按 `index.html` 声明顺序加载。

这个方案的代价是：文件顺序仍然耦合在 HTML 声明里（不能并行开发）、契约测试的"按源码字面断言"仍然存在（需要额外行为测试）、没有静态导入分析能力。但**不碰 pywebview 行为、不碰 PyInstaller 配置、不需要新的测试基础设施**——纯前端 JS 层面的改动。

---

## 样机复现

所有样机脚本在 `design/evidence/2026-11-12/esm-spike/` 下：

```
# 桌面样机（V1–V4）——四个场景都跑一遍
python desktop/spike.py

# 手机页安全头样机（V5）
python phone/serve.py

# Node 测试工具样机（V6）
node tests/harness.mjs
```

每个脚本都会自动：弹出 pywebview 窗口 → 收集结果 → 写入 JSON → 关闭窗口 → 释放端口。不留常驻进程。

## 原始证据

每个场景的运行输出、JSON 结果和控制台日志都和对应样机脚本放在一起：

- `desktop/comprehensive-result.json` + 四个 `result-{A,B,C,D}.json` + 四个 `scene-{A,B,C,D}.log`
- `phone/phone-result.json` + `phone/run.log`
- `tests/run.log`

## 环境

| 组件 | 版本 |
|---|---|
| Python | 3.12.9 |
| pywebview | 6.2.1 |
| Node | v24.16.0（注：plan context 写的 v26，实际 v24） |
| 系统 | Windows 11 + WebView2 |
| pywebview 源码位置 | `<Python>/Lib/site-packages/webview/http.py` |
| pywebview 内置 http_server 默认绑定 | 127.0.0.1（源码硬编码） |

## 还没验证

- iOS Safari 与 Android Chrome 真机：V5 的安全头与 ESM 组合只在 WebView2 下测过。
- PyInstaller 打包（V7）：只有检查清单，样机没有实际打包。
- 多次运行稳定性：样机没有做重复运行，结论只代表单次运行。
- **对抗审计**：2026-11-12 指挥会话审过，修正了 V1、V2、V4 三处说法。
