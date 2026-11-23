# 手机页请求与配对会话组去重整理

- **日期**：2026-11-23
- **分支**：`refactor/phone-page`（基线提交 `fd8a32f`）

## 1. 整理范围

仅整理手机页「请求与配对会话」组内三处重复写法，保持所有用户可见行为、请求顺序、定时器排程、CSRF 取值时机与错误文案不变，不改动桌面端、后端、原型、测试及其余十份手机脚本：

- `local/ui/m/model.js`（267 行 → 275 行）：新增纯成员 `PhoneModel.sessionVerdict(status)`。
- `local/ui/m/ui-session.js`（296 行 → 309 行）：新增 `adoptCookieCsrf()`、`showAppView()`、`showPairView()`，并将 `api()`、`pair()`、`poll()`、`onNeedPair()`、`onForbidden()` 的对应重复片段收拢到上述入口。
- `design/evidence/2026-11-23/phone-session-tidy/`：新增复跑脚本 `scripts/net_after_tidy.py`、72 条对照报告 `net-after-tidy.md` 及本说明。

## 2. 三处重复改前改后位置

| 重复项 | 收拢入口（改后位置） | 改前位置（`HEAD:local/ui/m/ui-session.js`） | 改后调用位置（`local/ui/m/ui-session.js`） | 保留不合并的邻近写法 |
|---|---|---|---|---|
| 读 `campus_phone_csrf` cookie 非空覆盖 `model.csrf` | `adoptCookieCsrf()`（`ui-session.js:64-67`） | `api()` 写请求分支（`75-76`）、`onForbidden()`（`272-273`） | `api()` 写请求分支（`91`）、`onForbidden()`（`286`） | `poll()` 仅在 `model.csrf` 为空时从 cookie 补值（改前 `222` → 改后 `237`），语义不同保持原样 |
| 主界面 / 配对页两行显隐切换 | `showAppView()`（`ui-session.js:69-72`）、`showPairView()`（`ui-session.js:74-77`） | `pair()` 成功（`211-212`）、`poll()` 成功（`234-235`）、`onNeedPair()`（`263-264`） | `pair()`（`227`）、`poll()`（`250`）、`onNeedPair()`（`278`，仍在 `renderPair()` 之前） | — |
| HTTP 状态码会话分流（200 / 401 / 403 / 其余） | `PhoneModel.sessionVerdict(status)`（`model.js:78-83`） | `api()` `/api/action` 401/403 判断（`89-90`）、`poll()` 三行状态判断（`227-229`） | `api()` `/api/action` 分支（`104-106`）、`poll()`（`242-245`） | `api()` 中 `if (resp.status !== 200 \|\| body.ok === false)`（改前 `91` → 改后 `107`）保持原样 |

## 3. 新命名撞名检查

改动前在 `local`、`server`、`tools`、`design` 目录下全仓检索 `adoptCookieCsrf`、`showAppView`、`showPairView`、`sessionVerdict`（覆盖 `.py`、`.js`、`.html`、`.mjs`）：

- 命中数为 **0**，`local/ui/m/` 十二份普通脚本与 `local/tests/` 中均无同名函数、常量或变量，直接采用上述四个名字。

## 4. 安全网 72 条变异复跑对照与重定位映射

只读复用 `design/evidence/2026-11-22/phone-net/scripts/mutate_phone.py` 的 72 条变异定义与 `equiv.json`，在 `tempfile.gettempdir()` 下由 `git archive HEAD` 导出并叠加工作区 `local/ui/m/` 改动的独立副本中，先过 `node --check`，再逐条运行 `local/tests/test_phone_ui.py`，并与 `design/evidence/2026-11-22/phone-net/after.md` 逐条比对。完整逐条结果见 `net-after-tidy.md`。

### 结论统计对照

| 结论分类 | 安全网补测后（`after.md`） | 整理后复跑（`net-after-tidy.md`） | 变化 |
|---|---:|---:|---:|
| 行为守 | 66 | 66 | 0 |
| 等价 | 6 | 6 | 0 |
| 字面守 | 0 | 0 | 0 |
| 无人守 | 0 | 0 | 0 |
| 定位不到 / 无效 | 0 | 0 | 0 |
| **总计** | **72** | **72** | **0** |

### 重定位映射表（72 条中 9 条按新位置定位，其余 63 条仅沿用去两格缩进的原样定位）

| 变异编号 | 原函数 | 新函数 | 定位调整 |
|---|---|---|---|
| `M06` | `api` | `adoptCookieCsrf` | `if (fresh) model.csrf = fresh;` → `if (!(fresh)) model.csrf = fresh;` |
| `M07` | `api` | `adoptCookieCsrf` | `if (fresh) model.csrf = fresh;` → `if (fresh) void 0;` |
| `M12` | `api` | `api` | `if (verdict === "need_pair")` → `if (!(verdict === "need_pair"))` |
| `M13` | `api` | `api` | `if (verdict === "forbidden")` → `if (!(verdict === "forbidden"))` |
| `M47` | `poll` | `poll` | `if (verdict === "need_pair")` → `if (!(verdict === "need_pair"))` |
| `M48` | `poll` | `poll` | `if (verdict === "forbidden")` → `if (!(verdict === "forbidden"))` |
| `M49` | `poll` | `poll` | `if (verdict !== "ok")` → `if (!(verdict !== "ok"))` |
| `M61` | `onForbidden` | `adoptCookieCsrf` | `if (fresh) model.csrf = fresh;` → `if (!(fresh)) model.csrf = fresh;` |
| `M62` | `onForbidden` | `adoptCookieCsrf` | `if (fresh) model.csrf = fresh;` → `if (fresh) void 0;` |

## 5. 测试与代码形状检查结果

| 检查项 | 改动前基线 | 改动后结果 |
|---|---|---|
| `node --check local/ui/m/ui-session.js` / `model.js` | — | 均通过（退出码 0） |
| `test_phone_ui.py` | 262 通过 / 0 失败 / 0 跳过 | 262 通过 / 0 失败 / 0 跳过 |
| `test_phone_infra.py` | 47 通过 / 0 失败 / 0 跳过 | 47 通过 / 0 失败 / 0 跳过 |
| `test_ui_contracts.py` | 374 通过 / 0 失败 / 0 跳过 | 374 通过 / 0 失败 / 0 跳过 |
| `local/tests` 全量（`test_*.py`） | — | 2813 通过 / 0 失败 / 2 跳过 |
| `python tools/code_shape/check.py` | 通过（退出码 0） | 通过（退出码 0，`baseline.json` 未改动） |

## 6. 未验证项

- 真机（iOS Safari / Android 浏览器）与真实局域网 / Cloudflare 隧道联调未实测；所有测试与安全网复跑均在离线 Node `vm` 沙箱与本地测试替身下执行。
- PyInstaller 打包后的冻结态 EXE 内手机页加载未实测。
- 手机页其余四组（「摄入与渲染」「外壳与接线」「计划操作」「重新登录」）未纳入本批整理与变异覆盖。

## 7. 复现命令

在仓库根执行（Python 3.12；跑测试与脚本前清空 `http_proxy`、`HTTP_PROXY`、`https_proxy`、`HTTPS_PROXY`、`all_proxy`）：

```bash
node --check local/ui/m/ui-session.js
node --check local/ui/m/model.js
python tools/code_shape/check.py
python -m unittest discover -s local/tests -p "test_phone_ui.py"
python -m unittest discover -s local/tests -p "test_phone_infra.py"
python -m unittest discover -s local/tests -p "test_ui_contracts.py"
python -m unittest discover -s local/tests -p "test_*.py"
python design/evidence/2026-11-23/phone-session-tidy/scripts/net_after_tidy.py --list
python design/evidence/2026-11-23/phone-session-tidy/scripts/net_after_tidy.py --workers 4
```
