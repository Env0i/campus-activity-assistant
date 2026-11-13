# ES Modules 补验结论（S3 汇总）

对应计划 `20261112-esm-verify`，经返修 `20261112-audit-esm-repair`（E1–E9、D4、D5）后执行。

- 结论只用宿主机（`host-*`）与手机真机（`phone-*`）的结果。`dry-run-*` 只作本机试跑旁证，文中凡用到处都注明了。
- 每条结论后面的文件名都在本目录 `results/` 下。
- 手机数字由 `tools/summarize.py` 从 `phone-*` 算出，不手抄。复现命令见文末。

## 1. 数据范围

| 项 | 内容 |
|---|---|
| 宿主机 | Windows 11（10.0.26300），WebView2 157.0.4341.46，Python 3.12.9，pywebview 6.2.1，PyInstaller 6.22.3（发版构建环境已有版本，未新装） |
| 产品 | 已装的 1.2.2 安装版、已发布的 1.2.2 独立 EXE，均以 `--demo` 启动，各两次 |
| 样机打包 | onefile 与 onedir，各三种安装目录（纯英文、含空格、中文加空格） |
| 手机 | iPhone，iOS 18.7，Safari 27.0.1。两种通道：Tailscale（HTTP 直连）、Cloudflare 临时隧道（HTTPS） |
| 手机上报 | 共 80 份：Tailscale 32 份，Cloudflare 48 份（`phone-*-ios-safari-*.json`） |
| 手机浏览器范围 | 按用户 2026-11-13 的口径，只用 iOS Safari 或相机扫码进 Safari。微信、飞书内置浏览器与安卓不在使用范围内，未测，不算缺口 |

## 2. 结论总表

| 编号 | 假设 | 结论 | 主要证据 |
|---|---|---|---|
| H1 | 产品经 pywebview 内置服务供页 | 成立 | `host-product-installed-1.2.2-run1.json`、`-run2.json`；`host-product-standalone-1.2.2-run1.json`、`-run2.json` |
| H2 | 产品写法下页面实际经 `http://127.0.0.1:<端口>` 加载 | 成立 | `host-onefile-*-product.json`、`host-onedir-*-product.json`；对照 `host-*-file-url-noallow.json` |
| H3 | 顶层循环报错，调用期循环不报错 | 有条件成立 | `host-*-cycle.json`；`host-*-h9-*.json` |
| H4 | 语法与能力矩阵 | 成立（内联模块的 CSP 拦截只在手机上验证） | `host-*-product.json`；`phone-*-h2` 与 `phone-*-h3-cycle` |
| H5 | 后端早推不丢 | 有条件成立（排队重放路径未被触发） | `host-*-product.json`、`dry-run-product.json` 的 `backend_push` |
| H6 | 样机打包后模块照常执行 | 成立 | `host-onefile-*`、`host-onedir-*`、`host-onefile-plain-run01.json` 至 `run05.json` |
| H7 | 版本清单与源码依据 | 成立 | `host-versions.json`、`host-webview2-version.txt`、`host-pywebview-source.txt` |
| H8 | 两种通道在手机上可用 | 有条件成立（Tailscale 的 h2 只跑了 1 次，要求 3 次） | `phone-tailscale-ios-safari-*.json`、`phone-cloudflare-ios-safari-*.json`、两份服务日志 |
| H9 | 四种加载形态的耗时，决定手机页的结构 | 有条件成立，见第 4 节 | `phone-*` 的 `payload.done_ms` |
| H10 | 手机浏览器覆盖范围 | 成立（按用户口径，只覆盖 iOS Safari） | `results/HOST-CHECKLIST.md` 的 H8/H9/H10 表 |
| H11 | 模块失败时，普通脚本写的兜底提示能显示 | 成立 | `host-*-h11.json`；`phone-*-h11`；手机通用上报 |

## 3. 逐条结论

### H1 产品真实加载机制：成立

- 已装 1.2.2 安装版：两次启动的监听端口分别是 32214 与 6840，`index.html` 返回 200，首行 `<!doctype html>`。
- 已发布 1.2.2 独立 EXE：两次启动的端口分别是 21155 与 40881，同样返回 200 与 `<!doctype html>`。
- 两种形态都在 `127.0.0.1:<随机端口>` 供页，两次端口不同。
- 停止后端口是否为空：勾选表记为两次均为空。这一步的输出只在控制台出现，没有写进 JSON。
- 注意：计划原来有「源码态」形态，返修 D5 去掉了它，宿主机上没有跑源码态。

### H2 产品加载的是 pywebview 内置服务：成立

- 产品写法是不带协议前缀的绝对路径，宿主机上 6 次产品运行（onefile、onedir 各三种目录）都是 `location.protocol = http:`，host 为 `127.0.0.1:<端口>`，模块全部执行。来源：`host-onefile-*-product.json`、`host-onedir-*-product.json`。
- 对照组：`file://` 且 `ALLOW_FILE_URLS=False`（宿主机 onefile 三种目录，3 次）。入口模块的 script 元素报 error，模块一个都没执行（`ready=false`，`caps` 为空）。来源：`host-*-file-url-noallow.json`。
- 只在本机试跑中做过的对照（旁证，不作结论）：`file://` 加 pywebview 默认的 ALLOW（`dry-run-file-url.json`）能跑通；`start(http_server=True)` 能跑通（`dry-run-http-server.json`）。
- 上一轮「Bottle 报错」的说法在本轮没有复现：宿主机与本机试跑都没有这类报错。
- 这条依赖 pywebview 把不带前缀的路径当作本地地址并自动起服务，版本必须锁住，见第 5 节。

### H3 循环引用：有条件成立

- 顶层互相引用：宿主机 6 次全部报 `ReferenceError: Cannot access 'a' before initialization`（`cycle-b.mjs` 第 3 行）。同一个错误也让 `import()` 的 `cycle_dynamic` 失败。来源：`host-*-cycle.json`。
- 调用期循环（40 个模块：13 个 state、13 个 view、13 个 controller、一个入口，入口调用 `build01()`）：宿主机 6 次都执行完了（`esm_count=40`，`done_ms` 有值）。每个形态 6 次的执行顺序完全一致（`distinct_orders=1`）。来源：`host-*-h9-*.json`。
- 耗时与 40 个普通脚本接近，桌面中位数（ms）：legacy 159、flat 159、chain 174、preload 188。
- 注意：调用期循环「没报错」是间接证据。入口执行到末尾才置位完成标记，但结果里没有记录 `__cycleCallOk` 的布尔值。
- 条件：只适用于调用期引用。顶层循环必须消除，迁移时要有测试拦住它。

### H4 语法与能力矩阵：成立

| 能力 | 桌面（宿主机 product） | 手机（iOS Safari） |
|---|---|---|
| 静态 import，默认与命名导出 | 通过 | 通过（5/5 次 h2） |
| 动态 `import()` | 通过 | 通过 |
| `import.meta.url` | 通过 | 通过 |
| 顶层 `await` | 通过 | 通过 |
| `modulepreload` | 通过 | 通过 |
| 模块里用 `fetch` 读 JSON | 通过 | 通过 |
| 依赖的模块 404 | script 元素 error 事件触发（document 捕获阶段），`window.onerror` 不触发 | 同左 |
| CSP `script-src 'self'` 下的内联 `type=module` | 不适用（桌面样机没有设 CSP） | 被拦（`csp_violation`，`inline_module.ran=false`） |

- 手机上 h2 页 5 次（Tailscale 1 次，Cloudflare 4 次）的 `all_caps_ok` 全部为 true。
- 没有直接测试 import 断言（import attributes）语法。计划要求用 `fetch` 读 JSON，这一点已测。

### H5 后端早推事件：有条件成立

- 宿主机 6 次产品运行加 1 次本机试跑（共 7 份），每份都有 6 次推送：`gui_start`（loaded 之前）与 loaded 之后 0、50、100、200、500 毫秒各一次。6 次全部 `received_by_page=true`，`phase=module`（由模块接管后收到）。来源：`host-*-product.json`、`dry-run-product.json`。
- `gui_start` 是在 loaded 之前发出的，`evaluate_js` 阻塞了 0.55–0.86 秒（宿主机）才返回，本机试跑是 2.05 秒。事件在模块接管之后才到页面。在 pywebview 6.2.1 下，这次没有观察到丢失。
- 排队重放路径没有被触发：所有结果里 `backend_queued` 都为空，`backend_replayed` 都为 0。所以「普通脚本先挂排队的 `onBackend`，模块就绪后接管并重放，一条不丢」没有证据。
- 结论：本轮数据不要求必须排队，但也没有证明排队有效。见第 5 节的建议。

### H6 样机打包：成立

- onefile 与 onedir，三种目录，产品样机全部 `ready=true`、`caps` 全部通过（宿主机 6 次）。
- 7 个场景在每个目录都写出了结果文件（onefile 三目录各 7/7，onedir 三目录各 7/7）。
- onefile 在纯英文目录连跑 5 次：`ready` 5/5，页面完成时间 120–152 毫秒。
- 产品样机的完成时间（宿主机 11 次，含连跑）：中位数 137 毫秒，范围 120–252 毫秒。
- 注意：打包的是样机，不是产品本身。参数与 `local/build/build_exe.py` 的写法一致，但产品没有在本次验证中被重新打包。

### H7 版本清单：成立

- 版本：Python 3.12.9；pywebview 6.2.1；bottle 0.13.4；proxy-tools 0.1.0；pythonnet 3.2.1；clr-loader 0.3.1；PyInstaller 6.22.3。来源：`host-versions.json`。
- WebView2 运行时：157.0.4341.46。来源：`host-webview2-version.txt`。
- pywebview 源码依据（`host-pywebview-source.txt`）：
  - `webview/util.py:75` 的 `is_local_url`：不以 `http://`、`https://`、`file://` 开头、也不是应用对象的字符串，都当作本地地址。
  - `webview/__init__.py:271–281`：有本地地址时，`has_local_urls` 为真，就调用 `http.start_global_server` 起内置服务。
  - `webview/platforms/edgechromium.py:84–85`：`ALLOW_FILE_URLS` 为真时加 `--allow-file-access-from-files`。宿主机结果里 `pywebview_default_allow_file_urls=true`。

### H8 手机真机两种通道：有条件成立

| 通道 | 页面 | 次数 | 说明 |
|---|---|---|---|
| Tailscale | h2 | 1 | 要求 3 次，**未达标** |
| Tailscale | h3-cycle | 1 | RUNBOOK 只要求 1 次 |
| Tailscale | h11 | 5 | 满足 |
| Tailscale | h9 | 25 | 其中 H9 运行记录 21 条，通用上报 4 条 |
| Cloudflare | h2 | 4 | 满足 |
| Cloudflare | h3-cycle | 1 | RUNBOOK 只要求 1 次 |
| Cloudflare | h11 | 3 | 满足 |
| Cloudflare | h9 | 40 | 其中 H9 运行记录 27 条，通用上报 13 条 |

- 两条通道的服务都在结束时写了「端口已释放=True」。Tailscale 的日志在到时自动退出后，末行是 `端口已释放=True`；Cloudflare 同样。
- 上报中的 h2 页 5 次全部 `all_caps_ok=true`，H3 的顶层循环报错在两条通道上都出现了（预期中的失败）。

### H9 手机加载耗时：有条件成立（数字见第 4 节）

### H10 手机浏览器范围：成立（按用户口径）

- 覆盖：iOS Safari（系统浏览器），两条通道都跑通。设备与系统版本：iPhone，iOS 18.7，Safari 27.0.1。完整 User-Agent 在结果 JSON 的 `payload.ua` 里。
- 未测、不在使用范围内：微信与飞书内置浏览器、安卓的 Chrome 与系统浏览器。按 2026-11-13 的口径，这些不算缺口。

### H11 失败时用户看到什么：成立

| 环境 | 次数 | 兜底提示出现时间（毫秒） |
|---|---|---|
| 桌面（样机打包，onefile 与 onedir 各三种目录） | 6/6 | 5112–5143 |
| 手机 Tailscale | 5/5 | 5177–5198 |
| 手机 Cloudflare | 3/3 | 6168–7194 |

- 另外，手机 H9 的通用上报里有 14 条 `esm_count=0`（模块一个都没执行），这 14 条的 `fallback.shown` 全部为 true。
- 结论：兜底提示必须用普通脚本写，不依赖模块。模块 404 时它照样出现。
- Cloudflare 上出现得更晚，因为页面 DOM 完成得更晚（约 1.2 秒）。这一点影响阈值的选择，见第 5 节。

## 4. H9 手机加载耗时

数据来源：`phone-*` 中带 `form` 字段的 H9 运行记录，取 `payload.done_ms`。计算由 `tools/summarize.py` 完成。

| 通道 | 形态 | 有效 / 总次 | 中位数（ms） | 最大值（ms） | 未完成（done_ms 为空） |
|---|---|---|---|---|---|
| Tailscale | legacy（40 个普通脚本） | 3/3 | 628 | 641 | 0 |
| Tailscale | flat | 3/3 | 3824 | 5625 | 0 |
| Tailscale | chain（8 层） | 6/6 | 799 | 941 | 0 |
| Tailscale | preload-chain | 9/9 | 216 | 4020 | 0 |
| Cloudflare | legacy | 3/3 | 3432 | 4182 | 0 |
| Cloudflare | flat | 1/6 | 5510 | 5510 | 5 |
| Cloudflare | chain | 4/7 | 8686 | 9511 | 3 |
| Cloudflare | preload-chain | 10/11 | 1798 | 4903 | 1 |

说明：

- 次数不是严格的 3 次。同一页面被多次打开过，记录按实际条数计算。
- 「未完成」的 9 条记录全部在 Cloudflare 上，它们的 `module_count=0`，`dom_ready_ms` 与 `load_ms` 也为空，即一个模块都没执行。这是 H9 页面的 10 秒等待到点上报（`web/generated/common/runner.js:87-90`），不是数据丢失：模块脚本没执行完时 DOMContentLoaded 不会触发，所以这 9 次可以读作「40 个模块经 Cloudflare 临时隧道 10 秒内没加载完」。具体卡在网络、隧道还是 Safari 的并发上限没有分开测（指挥会话 2026-11-13 复核补注）。这条加强了下面「手机页不要裸拆成很多模块」的建议。
- 通用上报（不带 `form`）共 17 条，和某次运行的完成时间重复，没有计入。
- 手机上的 `ready` 字段对 H9 页无意义（这些页没有能力探针），判断以 `esm_count` 与 `done_ms` 为准。
- 桌面参考（宿主机，每形态 6 次，onefile 与 onedir 各三种目录）：中位数 legacy 159、flat 159、chain 174、preload-chain 188 毫秒，最大值 479 毫秒。

建议（用于决定手机页迁移后的结构）：

1. 不建议把 40 个模块按现在的链式或扁平写法直接拆开上线。Cloudflare 上 8 层链式中位数 8.7 秒，并且有 3 次未执行任何模块。扁平写法有 5 次未执行任何模块。
2. 四种形态里，`modulepreload` 是最快的拆分方式，在两条通道上都能跑完（Cloudflare 上 10 次完成，中位数 1.8 秒，比 40 个普通脚本的 3.4 秒快）。
3. 迁移后手机页先保留单文件。如果要拆，只能用 `modulepreload`，并把依赖层级压平。之后用同样的 H9 在 Cloudflare 上重测。
4. 如果重测仍慢或仍有未执行的情况，就合并成一个模块文件（一次请求）。
5. 单文件形态没有在本轮 H9 中直接测量。计划里的「1 个普通脚本」形态没有写进样机（`legacy` 是 40 个脚本）。所以「单文件最快」只是推断。

## 5. 迁移约束清单

1. **锁版本**：pywebview 精确锁到 `6.2.1`，并锁住本次解析到的依赖组合：

   | 包 | 建议版本 |
   |---|---|
   | pywebview | 6.2.1 |
   | bottle | 0.13.4 |
   | proxy-tools | 0.1.0 |
   | pythonnet | 3.2.1 |
   | clr-loader | 0.3.1 |

   理由：产品能工作，靠的是 pywebview 把不带协议前缀的路径当作本地地址并自动起内置服务（H2、H7）。`ALLOW_FILE_URLS` 的默认值（H7）决定 `file://` 是否能用。任一行为在别的版本里变了，模块加载就会变。`local/requirements.txt` 现在写的是 `pywebview>=5.0`。改成精确版本是另一份计划的事，本计划不改。
2. **允许的语法**：静态 import 与导出（默认、命名）、动态 `import()`、`import.meta.url`、顶层 `await`、`modulepreload`、模块里用 `fetch` 读 JSON（H4）。只在 iOS Safari 27.0.1 与 WebView2 157 上验证过。
3. **禁止的写法**：模块的顶层循环引用（H3，报 `ReferenceError`）；CSP 下的内联 `type=module`（H4，手机上被拦）。import 断言未测，不用。
4. **PHONE_STATIC 保留显式登记**，不改成目录遍历。另加一条 import 图测试：从入口出发解析所有静态 import 与 `modulepreload`，断言每个路径都在 PHONE_STATIC 里登记过。H11 的 404 实验说明，漏登记时页面只会显示兜底提示，不会报错，所以这条测试必须在 CI 里拦住它。
5. **兜底提示**：用普通脚本写（H11），不依赖模块。阈值要注意：Cloudflare 上最慢的成功形态要 9.5 秒（H9），按计划的判定，5 秒内没报到就显示兜底，所以在 Cloudflare 上要 8–9.5 秒才完成的形态会被误报为「加载不完整」。迁移时二选一：把阈值定在大于实测最慢成功值（留余量，例如 10 秒以上），或改成「模块全部报到」判定。两种都要在 Cloudflare 上重测。
6. **onBackend 排队**：保留「普通脚本先挂排队用的 `onBackend`」的写法，成本低。迁移时补一条排队重放测试，在锁版本下验证，因为本轮没有触发这条路径（H5）。
7. **循环引用**：顶层循环不允许。调用期循环可以用，但要有测试。顶层 `ReferenceError` 会让整个模块图执行失败，页面的其他部分也不会起来。

## 6. 退回「命名空间对象 + 调用关系测试」方案的条件

出现以下任一情况，就退回到不用 ES Modules 的方案（普通脚本挂命名空间对象，用调用关系测试守住依赖）：

- pywebview 无法锁在 6.2.1 及依赖组合，或者升级后 H1、H2 复测失败（产品不再经 `127.0.0.1` 供页，或 `ALLOW_FILE_URLS` 的默认值、自动起服务的行为变了）。
- 排队重放测试在锁版本下无法一条不丢地通过（H5）。
- 手机页拆模块后，在 Cloudflare 上仍然出现未执行模块的情况，并且合并成一个模块文件也解决不了。
- 顶层循环引用无法消除。

## 7. 仍然没有测到的项

- Tailscale 通道的 h2 只跑了 1 次，计划要求 3 次。
- 手机上的 h3-cycle 每个通道只跑了 1 次（RUNBOOK 的要求）。
- 单文件形态没有在 H9 中测量（计划的「1 个普通脚本」没有进入样机）。
- Cloudflare 上 9 次未执行模块的运行，原因没有定位。
- H1 的源码态形态没有在宿主机上跑（D5 删除了这一形态）。
- H2 的 `file://` 默认 ALLOW 与 `http_server=True` 两个对照，只在本机试跑中做过（旁证）。
- H5 的排队重放路径没有被触发。
- 桌面样机没有设 CSP，所以 CSP 下的内联模块只在手机上验证。
- 样机打包不等于产品打包，产品本身没有在本次验证中重新打包。
- 停止后端口为空的结论只记在勾选表里，没有写进 JSON。
- 微信与飞书内置浏览器、安卓：按用户口径不在使用范围内，未测。

## 8. 脱敏与复现

- 本目录不写主机路径、地址、tailnet 名、隧道域名、账号，也不写所在位置信息。
- `tools/redact.py --selftest` 与 `--check` 的结果见 `.claude/results/20261112-esm-verify-result.yaml`。
- 复现手机与桌面汇总（仓库根执行，不写文件）：

```
py -3.12 -I -X utf8 -B design/evidence/2026-11-12/esm-verify/tools/summarize.py
```
