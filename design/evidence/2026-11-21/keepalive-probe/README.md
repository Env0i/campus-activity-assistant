# 手机页连接复用对照实验（iPhone Safari，2026-11-22）

## 1. 实验要回答的问题

2026-11-12 的 ES Modules 补验在 iPhone Safari 上观察到两个现象：Tailscale 直连下 `flat` 形态中位数（3.8 秒）明显慢于 `chain` 形态（0.8 秒），而 Cloudflare 临时隧道下 `flat`（6 次有 5 次）与 `chain`（7 次有 3 次）在 10 秒内未执行任何模块。复查当时测速服务（`serve_probe.py`）及产品手机服务（`local/infrastructure/phone_http.py`）发现，两者均未设置 `protocol_version`，默认按 HTTP/1.0 响应并在每个请求后关闭连接，且所有文件均返回 `Cache-Control: no-store`。

本实验回答单一问题：**在同样禁止缓存的条件下，手机页多模块加载慢以及 Cloudflare 通道上 10 秒内未执行完，是否是由「连接不复用（HTTP/1.0 短连接）」造成的。**

---

## 2. 只变一个变量的说明

本实验严格固定除「是否复用 HTTP 连接」之外的所有条件，复用 `design/evidence/2026-11-12/esm-verify/web/generated/` 的测速页面、4 形态 × 3 次自动轮转（`legacy` → `flat` → `chain` → `preload-chain`，单次最多等 10 秒）及上报/脱敏逻辑：

- **不变的项**：同一批静态 HTML/JS/MJS 文件（40 个脚本或模块）、同一组安全响应头（含 `Cache-Control: no-store` 与 CSP）、同一台宿主机与同一部 iPhone（iOS 18.7，Safari，UA 为 `Mozilla/5.0 (iPhone; CPU iPhone OS 18_7 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/27.2 Mobile/15E148 Safari/604.1`）、同一端口 `8765`。
- **唯一改变的项**：`scripts/serve_keepalive.py` 通过 `--arm` 切换处理器的 `protocol_version`。

---

## 3. 两组设置与工具核验

| 组别 | 服务端设置 | 连接行为 | 响应长度头 |
|---|---|---|---|
| `close` | `protocol_version = "HTTP/1.0"` | 每次回复后关闭 TCP 连接，与 2026-11-12 测速服务及当前产品手机服务一致 | 每个回复均带准确 `Content-Length` |
| `keepalive` | `protocol_version = "HTTP/1.1"` | 同一条 TCP 连接保持打开并连续复用（仅错误状态 `>= 400` 时断开） | 每个回复均带准确 `Content-Length` |

### 3.1 离线自检与本机自测

- **离线连接自检**（`python design/evidence/2026-11-21/keepalive-probe/scripts/serve_keepalive.py --self-check`）：
  - `close` 组连发 5 次静态请求：每次回复后断开连接、下次重连（`distinct_connections=5`、`conn_ids=[1, 2, 3, 4, 5]`、`conn_req_seqs=[1, 1, 1, 1, 1]`）。
  - `keepalive` 组连发 5 次静态请求：复用同一条连接（`distinct_connections=1`、`conn_ids=[1, 1, 1, 1, 1]`、`conn_req_seqs=[1, 2, 3, 4, 5]`）。
  - 两组所有回复均带准确 `Content-Length`，退出后端口均已释放。
- **本机 WebView2 自测（仅验证工具与脱敏链路可用，不作实验结论）**：
  - `close` 与 `keepalive` 两组各跑 1 轮（每组 12 份上报、553 条请求），`close` 组用了 553 条连接、`keepalive` 组仅用了 12 条连接（单连接最大 68 请求），所有上报与请求日志均通过 `redact.py --check`。

---

## 4. 事先定好的判据原文

本实验严格按以下事先定好的判据下结论，不另行解读：

- **甲「连接复用是主因」**：`keepalive` 组在 Cloudflare 上 `flat` 与 `chain` 都没有未完成（各至少 6 次），并且 Tailscale 上 `flat` 中位数比 `close` 组降一半以上；
- **乙「复用有帮助但隧道仍不稳」**：Tailscale 上 `flat` 中位数降一半以上，但 Cloudflare 上 `keepalive` 组仍有未完成；
- **丙「复用不是原因」**：两条通道上 `keepalive` 组与 `close` 组差距都在两成以内。
- **兜底规则**：三条都不满足就写「结论不定」并列出原始数。未完成的那几次，如果请求日志显示模块请求根本没到服务器，单独写一句「卡在服务器之前（隧道或浏览器）」。

---

## 5. 汇总表

真机按 Tailscale 两组各 1 轮、Cloudflare 两组交替各 2 轮（`close` → `keepalive` → `close` → `keepalive`，每轮重开独立临时隧道）执行。下表全部由 `scripts/summarize.py` 从 `results/` 直接算出：

### 5.1 真机测速汇总（iOS Safari）

| 通道 | 组别 | 形态 | 有效 / 总次 | done_ms 中位数（ms） | done_ms 最大值（ms） | 未完成（10 秒内） |
|---|---|---|---|---:|---:|---:|
| tailscale | close | legacy | 3/3 | 591 | 669 | 0 |
| tailscale | close | flat | 3/3 | 674 | 743 | 0 |
| tailscale | close | chain | 3/3 | 738 | 814 | 0 |
| tailscale | close | preload-chain | 3/3 | 655 | 735 | 0 |
| tailscale | keepalive | legacy | 3/3 | 514 | 515 | 0 |
| tailscale | keepalive | flat | 3/3 | 593 | 598 | 0 |
| tailscale | keepalive | chain | 3/3 | 686 | 701 | 0 |
| tailscale | keepalive | preload-chain | 7/7 | 451 | 3158 | 0 |
| cloudflare | close | legacy | 6/6 | 1917 | 2484 | 0 |
| cloudflare | close | flat | 2/6 | 4418 | 6799 | 4 |
| cloudflare | close | chain | 6/6 | 6220 | 7707 | 0 |
| cloudflare | close | preload-chain | 0/3 | - | - | 3 |
| cloudflare | keepalive | legacy | 6/6 | 2819 | 3929 | 0 |
| cloudflare | keepalive | flat | 4/6 | 3766 | 4498 | 2 |
| cloudflare | keepalive | chain | 6/6 | 6308 | 8385 | 0 |
| cloudflare | keepalive | preload-chain | 6/6 | 1476.5 | 4456 | 0 |

### 5.2 本机 WebView2 自测参考（仅验证工具可用）

| 通道 | 组别 | 形态 | 有效 / 总次 | done_ms 中位数（ms） | done_ms 最大值（ms） | 未完成（10 秒内） |
|---|---|---|---|---:|---:|---:|
| tailscale | close | legacy | 3/3 | 125.7 | 203.8 | 0 |
| tailscale | close | flat | 3/3 | 87.7 | 90.4 | 0 |
| tailscale | close | chain | 3/3 | 108.3 | 133.3 | 0 |
| tailscale | close | preload-chain | 3/3 | 101.9 | 102.3 | 0 |
| tailscale | keepalive | legacy | 3/3 | 86.1 | 101.7 | 0 |
| tailscale | keepalive | flat | 3/3 | 97.9 | 105.1 | 0 |
| tailscale | keepalive | chain | 3/3 | 107.8 | 151.9 | 0 |
| tailscale | keepalive | preload-chain | 3/3 | 85.3 | 85.4 | 0 |

### 5.3 请求日志连接数与请求数

| 请求日志文件 | 通道 | 组别 | 客户端标签 | 总请求数 | TCP 连接数 | 单连接最大请求数 |
|---|---|---|---|---:|---:|---:|
| `requests-cloudflare-close-20261122-104557.jsonl` | cloudflare | close | ios-safari | 407 | 407 | 1 |
| `requests-cloudflare-close-20261122-112329.jsonl` | cloudflare | close | ios-safari | 434 | 434 | 1 |
| `requests-cloudflare-keepalive-20261122-111814.jsonl` | cloudflare | keepalive | ios-safari | 467 | 23 | 111 |
| `requests-cloudflare-keepalive-20261122-112742.jsonl` | cloudflare | keepalive | ios-safari | 465 | 34 | 64 |
| `requests-tailscale-close-20261121-163639.jsonl` | tailscale | close | desktop-webview2 | 553 | 553 | 1 |
| `requests-tailscale-close-20261122-103632.jsonl` | tailscale | close | ios-safari | 543 | 543 | 1 |
| `requests-tailscale-keepalive-20261121-163648.jsonl` | tailscale | keepalive | desktop-webview2 | 553 | 12 | 68 |
| `requests-tailscale-keepalive-20261122-104050.jsonl` | tailscale | keepalive | ios-safari | 496 | 17 | 92 |

### 5.4 未完成轮次（10 秒内 `done_ms` 为空）的模块请求到达情况

| 上报文件 | 通道 | 组别 | 形态 | run | 页面已执行模块数 | 到达服务器的模块请求数（共 40） | 不同模块文件数 |
|---|---|---|---|---:|---:|---:|---:|
| `phone-cloudflare-close-ios-safari-05.json` | cloudflare | close | flat | 1 | 0 | 26 | 26 |
| `phone-cloudflare-close-ios-safari-09.json` | cloudflare | close | flat | 3 | 0 | 13 | 13 |
| `phone-cloudflare-close-ios-safari-21.json` | cloudflare | close | flat | 1 | 0 | 33 | 33 |
| `phone-cloudflare-close-ios-safari-24.json` | cloudflare | close | flat | 3 | 0 | 34 | 34 |
| `phone-cloudflare-close-ios-safari-31.json` | cloudflare | close | preload-chain | 1 | 0 | 17 | 17 |
| `phone-cloudflare-close-ios-safari-33.json` | cloudflare | close | preload-chain | 2 | 0 | 1 | 1 |
| `phone-cloudflare-close-ios-safari-35.json` | cloudflare | close | preload-chain | 3 | 0 | 1 | 1 |
| `phone-cloudflare-keepalive-ios-safari-05.json` | cloudflare | keepalive | flat | 1 | 0 | 38 | 38 |
| `phone-cloudflare-keepalive-ios-safari-23.json` | cloudflare | keepalive | flat | 2 | 0 | 38 | 38 |

---

## 6. 结论

按事先定好的判据逐条核对：

1. **判据甲不满足**：Tailscale 上 `flat` 中位数从 `674 ms` 降到 `593 ms`（仅降 `12.0%`，远未降一半以上），且 Cloudflare 上 `keepalive` 组 `flat` 仍有 2 次未完成（仅 `4/6` 完成）。
2. **判据乙不满足**：Tailscale 上 `flat` 中位数未降一半以上（只降 `12.0%`）。
3. **判据丙不满足**：并非所有形态在两条通道上差距都在两成以内——Tailscale 的 `preload-chain` 差距达 `31.1%`（`655 ms` vs `451 ms`）；Cloudflare 的 `legacy` 差距达 `47.1%`（`1917 ms` vs `2819 ms`）；Cloudflare 的 `preload-chain` 在 `close` 组 3 次汇报全部未完成（`0/3`，另有第 1 轮在 `runner.js` 未送达时停跑）而 `keepalive` 组 `6/6` 全部完成（中位数 `1476.5 ms`），差距明显超过两成。

三条都不满足，结论：**结论不定**。

未完成的轮次（包括第 1 轮 `preload-chain` 停跑那次与上表 9 次正式汇报 `done_ms` 为空的轮次）中，请求日志显示模块请求从未集齐到达服务器：

**卡在服务器之前（隧道或浏览器）。**

### 各组原始 `done_ms` 数值（ms，`None` 表示 10 秒内未完成）

- `tailscale / close / legacy`：`[669, 555, 591]`
- `tailscale / close / flat`：`[743, 674, 653]`
- `tailscale / close / chain`：`[814, 738, 730]`
- `tailscale / close / preload-chain`：`[655, 735, 574]`
- `tailscale / keepalive / legacy`：`[494, 515, 514]`
- `tailscale / keepalive / flat`：`[598, 593, 585]`
- `tailscale / keepalive / chain`：`[680, 686, 701]`
- `tailscale / keepalive / preload-chain`：`[3158, 551, 149, 101, 115, 451, 554]`（前 4 条为 Safari 回到该标签页时先重跑上一轮末尾 `run=3` 的记录，最后 3 条为本轮自动跳入的 `run=1,2,3`）
- `cloudflare / close / legacy`：`[2412, 1923, 1441, 2484, 1911, 1623]`
- `cloudflare / close / flat`：`[None, 6799, None, None, 2037, None]`
- `cloudflare / close / chain`：`[7707, 6608, 5901, 6539, 5468, 5209]`
- `cloudflare / close / preload-chain`：`[None, None, None]`（第 1 轮在 `run=1` 收到 35 个模块后停跑、未产生 `h9` 上报；第 2 轮 3 次全部 10 秒超时）
- `cloudflare / keepalive / legacy`：`[2898, 2595, 3560, 2740, 3929, 2341]`
- `cloudflare / keepalive / flat`：`[None, 4498, 3915, 2811, None, 3617]`
- `cloudflare / keepalive / chain`：`[8385, 6035, 6702, 6331, 6285, 5230]`
- `cloudflare / keepalive / preload-chain`：`[3442, 1223, 1654, 4456, 1299, 958]`

---

## 7. 请求日志的发现

1. **连接数开关确实生效**：`close` 组在 Tailscale 真机（543 请求 / 543 连接）和 Cloudflare 第 1、2 轮真机（407 请求 / 407 连接、434 请求 / 434 连接）中全部表现为单连接单请求；`keepalive` 组在 Tailscale 真机将 496 条请求压到 17 条连接（单连接最多 92 条请求），在 Cloudflare 两轮分别将 467、465 条请求压到 23、34 条连接（单连接最多 111、64 条请求）。
2. **Tailscale 上不出现 2026-11-12 的「flat 3.8 秒」现象，连接复用只有温和提速（约 7%–31%）**：本次 Tailscale 上即便 `close` 组，4 种形态中位数都在 `591–738 ms`，开启 `keepalive` 后降为 `451–686 ms`。说明当无线局域网与 Tailscale 直连状态较好时，短连接建连开销本身不是造成 3.8 秒级慢加载的主因。
3. **Cloudflare 临时隧道下，突发并发 `flat` 与 `preload-chain` 在 `close` 组受损最明显**：
   - `flat` 形态一次并发 40 个模块：`close` 组 6 次里有 4 次（第 1 轮 `run=1,3` 到达 26/40、13/40，第 2 轮 `run=1,3` 到达 33/40、34/40）未在 10 秒内收齐 40 个模块；`keepalive` 组也有 2 次各到达 38/40 而超时（完成率由 `2/6` 升至 `4/6`，但未能清零未完成）。
   - `preload-chain` 形态页面一开始就并行发起全图 preloading：`close` 组第 1 轮在 `preload-chain/?run=1` 收到 35/40 个模块后，后续请求（含 `common/runner.js`）未能到达服务器，导致页面卡住、15 分钟到点前都未发出 `h9` 上报；第 2 轮则出现 `run=1` 只到 17/40 个模块、`run=2,3` 各自只收到 1/40（仅 `main.mjs`）且全部 10 秒超时。而同一形态在 `keepalive` 组两轮 `6/6` 全部跑完（中位数 `1476.5 ms`）。
   - 需要补充的是，`cloudflared` 从浏览器到边缘节点走 HTTPS/HTTP2，从本机 `cloudflared` 到 `serve_keepalive.py` 这段回环转发才受 `HTTP/1.0 close` 与 `HTTP/1.1 keepalive` 直接切换影响；`close` 组突发并发下出现大批连接瞬间建连与断开，更容易让本地隧道转发并发饱和或丢掉后续子模块请求。

---

## 8. 未验证项与复现命令

- **未验证项**：
  - 只测了 iPhone Safari（iOS 18.7），未测微信/飞书内置浏览器或安卓设备。
  - 两组均固定 `Cache-Control: no-store`，没有对比强缓存、协商缓存（`ETag` / `304`）或合并单文件形态的效果。
  - 产品手机服务 `local/infrastructure/phone_http.py` 未作任何修改，生产行为未在本实验改动范围内验证。
  - Cloudflare `close` 组第 1 轮因 `preload-chain/?run=1` 未完成 `runner.js` 下发而没有产生 `preload-chain` 的 `h9` 上报，导致 `cloudflare close preload-chain` 有效统计样本为 `0/3`。
  - Tailscale `keepalive` 组启动时 Safari 先刷新了残留标签页中的 `preload-chain/?run=3`，使该形态共记录 7 次（均已完成，全量进入统计）。
- **脱敏自检**：`results/` 下全部 138 个文件均已通过 `design/evidence/2026-11-12/esm-verify/tools/redact.py --check`，零残留。
- **复现汇总命令**（在仓库根执行，不写任何文件）：

```powershell
python -B design/evidence/2026-11-21/keepalive-probe/scripts/summarize.py
```