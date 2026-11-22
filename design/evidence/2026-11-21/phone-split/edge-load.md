# 真 Edge 加载核对（HEAD 与拆分工作区对照）

- 结论：**PASS**
- 浏览器：Playwright `msedge` 无头模式，视口 `390×844`，仅访问 `127.0.0.1` 随机端口替身服务（3 场固定活动、固定业务时钟）
- `about:blank` `window` 自带属性与 12 份脚本 73 个顶格声明交集：`[]`（空）
- 配对前规整 `body` DOM（剔除 `<script>` 标签后）对比：**一致**
- 配对后规整 `body` DOM（剔除 `<script>` 标签，并将已隐藏 `#pair` 内随随机配对码变化的 `#pair-led` 点阵归一化为点阵数后）对比：**一致**
- HEAD 错误数：console=0, pageerror=0, failed=0
- 工作区错误数：console=0, pageerror=0, failed=0

## 工作区静态资源请求记录

| 路径 | HTTP 状态 | Content-Type |
|---|---:|---|
| `/` | 200 | `text/html; charset=utf-8` |
| `/styles.css` | 200 | `text/css; charset=utf-8` |
| `/model-conflict.js` | 200 | `text/javascript; charset=utf-8` |
| `/model.js` | 200 | `text/javascript; charset=utf-8` |
| `/model-run.js` | 200 | `text/javascript; charset=utf-8` |
| `/model-list.js` | 200 | `text/javascript; charset=utf-8` |
| `/model-relogin.js` | 200 | `text/javascript; charset=utf-8` |
| `/ui-session.js` | 200 | `text/javascript; charset=utf-8` |
| `/ui-status.js` | 200 | `text/javascript; charset=utf-8` |
| `/ui-sync.js` | 200 | `text/javascript; charset=utf-8` |
| `/ui-list.js` | 200 | `text/javascript; charset=utf-8` |
| `/ui-plan.js` | 200 | `text/javascript; charset=utf-8` |
| `/ui-shell.js` | 200 | `text/javascript; charset=utf-8` |
| `/ui-relogin.js` | 200 | `text/javascript; charset=utf-8` |

## 产物位置

- `edge/head-before.html`、`edge/head-before.png`、`edge/head-after.html`、`edge/head-after.png`
- `edge/work-before.html`、`edge/work-before.png`、`edge/work-after.html`、`edge/work-after.png`
