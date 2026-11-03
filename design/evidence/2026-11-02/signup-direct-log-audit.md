# 直发报名回包核对（2026-11-02）

## 结论

桌面端 28 场真实运行里，**直发通道没有产出过一次成功结论，也没有触发过一次点击兜底**：4,049 次直发的回包全是 `code:0` + `Cache 'hd-info' does not allow ...`；当时那版代码只在 message 精确等于「版本不兼容，请刷新页面或清除缓存后重试」时才降级，所以这笔文案既不算成功也不算降级，一路重发到次数上限。

请求本身**没有 body**（`GET signUp/<sig>`，输入全在 URL 里），链路里唯一带 body 的是开抢前的 `runtime/profile`（`{}`）；旧版不调这个接口。详见下文「直发请求长什么样」。

这直接影响 `docs/RETRY_POLICY_GUIDE.md` 的 RISK-001，以及 `design/decisions/002-signup-modes.md` 的现行口径。**本文只记录事实，未改任何文档。**

## 数据与口径

| 项 | 值 |
|---|---|
| 来源 | 桌面端 `local/data/grab.log`（`local/data/` 已被 `.gitignore` 排除） |
| 大小 | 1,056,523 字节 |
| 时间跨度 | 2026-10-27 17:55:21 — 2026-11-01 11:28:55 |

日志不入库，本目录不留副本；下面的「复现」段落给出重新统计的命令。

## 统计

| 项 | 值 |
|---|---|
| 运行场次（`开始盯按钮`） | 28 |
| `直发已发起` | 4,049 |
| `[retry] kind=submit` | 4,049 |
| 结论行 `Cache 'hd-info'` | 4,047 |
| 无结论的提交 | 2 |
| `code:1`（成功结论） | 0 |
| `版本不兼容` | 0 |
| 实际点击兜底 | 0 |
| 单场最大提交次数 | 162 |

`点击` 一共出现 28 次，全部是同一句配置说明——「入口脚本为已知直发包：启用直发（点击兜底保留）」，不是兜底动作。真正兜底会打印「版本不兼容：本场切换为点击兜底」，该行 0 次。

`404 / 429` 没有真实样本。直接 grep 会命中 6 条，但都是时间戳数字串（如 `1793434298`）被误匹配，不是 HTTP 状态码。`stop_reason` 只出现过 1 次 `login_invalid`（2026-10-31 15:42）。

## 样本

```
2026-10-31 15:44:48 [i] 第 1 次提交：直发已发起
2026-10-31 15:44:48 [retry] kind=submit attempts=1 request_id=req-1 phase=full_speed
2026-10-31 15:44:48 [i] 第 1 次提交：code:0 Cache 'hd-info' does not allow
```

```
2026-10-31 17:55:02 [i] 第 1 次提交：直发已发起
2026-10-31 17:55:02 [retry] kind=submit attempts=1 request_id=req-1 phase=full_speed
2026-10-31 17:55:02 [i] 第 1 次提交：code:0 Cache 'hd-info' does not allow
```

```
2026-11-01 09:56:21 [i] 第 1 次提交：直发已发起
2026-11-01 09:56:21 [retry] kind=submit attempts=1 request_id=req-1 phase=full_speed
2026-11-01 09:56:21 [i] 第 1 次提交：code:0 Cache 'hd-info' does not allow
```

同一场内的后续尝试是同一模式的重复，直到次数上限；最长的一场记录到 `第 162 次提交`。

## 旧版判据（产生本目录日志的那版代码）

本目录的日志是 2026-10-27 ~ 11-01 的旧版产物——依据是日志打的是「入口脚本为已知直发包：启用直发（点击兜底保留）」，而现行版本打的是「报名路径：直发（运行时密钥）」，两版文案不同，可据此判代。旧版 `_apply_conclusion` 的规则：
- `code == 1` → 记成功（`resp_ok`），粘性，后续失败不改写
- `str(code) == "4001"` → 记登录失效
- `str(code).strip() == "0"` **且** message 去掉末尾句号后精确等于 `版本不兼容，请刷新页面或清除缓存后重试` → 本场降级为点击兜底

实际文案是 `Cache 'hd-info' does not allow ...`，三条都不满足，因此既不判成功、也不降级，一直重发到次数上限。旧版还把 message 截到 30 字符写进 `last_reason`，所以日志里是截断后的文案。

## 现行判据（决策 015 之后，与本副本代码一致）

`local/grab.py:2381` 的 `_apply_conclusion` 已换成分类型判定（`classify_signup_reply`），不再要求整句精确相等：

| 类型 | 触发 | 处理 |
|---|---|---|
| `success` | `code == 1` | 成功粘性，后续失败不改写 |
| `login_invalid` | `code == 4001` | 停发 → 复查登录（连续两次才算失效） |
| 终态类 | 名额已满 / 报名已截止 / 时间冲突 | 本场直接结束 |
| `no_activity` | 「Cache 'hd-info' does not allow …」 | 直发时立即退回点击核实；点击路径上也这样才按「活动不存在」结束（成因未证实） |
| `version` | 版本不兼容 | 直发先重取运行时密钥；重取后仍不兼容才退回点击 |
| `stale_ts` | 「请求已超时」连续 N 次 | 判时钟问题 |
| `unknown` | 认不出的回包 | **直发同一文案连续 3 次 → 退回点击**；点击路径再出现才结束 |

也就是说，像 `Cache 'hd-info' does not allow` 这种回包，现行实现单列为 `no_activity`：直发时第一次就退回点击，不再一路重发；旧版会一直重发（单场最多 162 次）。

## 直发请求长什么样：没有请求体

上一版只写了回包，漏了请求。补上——**直发是一笔 GET，没有 body**，全部输入在 URL 路径里。

| 项 | 值 | 出处（本副本） |
|---|---|---|
| 方法 | `GET`（`urllib.request.Request` 显式 `method="GET"`，不传 data） | `local/signup_transport.py:139-141` |
| URL | `<站点根>/dr/api/rjyHdCyr/signUp/<sig>` | `local/grab.py:2711` |
| 请求体 | **无** | 同上 |
| `Accept` | `application/json, text/plain, */*` | `grab.py:2717` |
| `token` | 本场内存里的登录 token；取不到就停发，不降级 | 同上 |
| `Referer` | `<站点根>/stu/` | 同上 |
| `User-Agent` | 固定桌面 UA | 同上 |
| 网关签名头 | **四个都不带**：`X-Page-Ticket` / `X-Timestamp` / `X-Nonce` / `X-Token` 只由 `_post` 添加 | `grab.py:301-323`，仅 `_post` 调用 |
| `Content-Type` | 无（没有 body，也就没设） | 同上 |
| 重定向 | 不跟随，3xx 原样交上层 | `signup_transport.py` 的 `_NoRedirect` |
| 超时 | `min(票据预算, 8s, request_deadline 剩余)` | `_effective_timeout` |

### `<sig>` 怎么算

```
sig = lower( hex( AES-128-ECB( PKCS7( utf8("<activity_id>,<epoch_ms>") ), key ) ) )
```

- 明文只有 `"<活动 id>,<毫秒时间戳>"`：**不含 URL、不含 hd-info、不含其他字段**
- `epoch_ms` 取 business clock，不用 `time.time()`
- PKCS7 一律补齐（整块也补满 16 字节）；ECB 无 IV
- `key` 是 16 字节运行时密钥，来自下面那个接口，不落盘、不进日志

### 同一条链路里唯一有 body 的请求：`runtime/profile`

```
POST <站点根>/dr/api/upms/security/runtime/profile
Content-Type: application/json
token: <登录 token>
X-Page-Ticket / X-Timestamp / X-Nonce / X-Token: 网关签名
body: {}
```

回包顶层 `{code, message, data, version}`，`data` 就是那 16 个 ASCII 字母数字密钥，直接 UTF-8 当 AES key，不做 hex/base64 二次解码（`parse_runtime_key`）。

网关签名头（`sign_request_headers`，本副本 `grab.py:301`，记法为 `HMAC(msg, key)`）：

- `page_ticket = HMAC(RAW_KEY, CLIENT_KEY)`
- `derived_key = HMAC(page_ticket|ts秒|path|nonce, CLIENT_KEY)`
- `canonical = "POST" \n path \n ts_ms \n nonce \n sha256(body) \n page_ticket`
- `signature = HMAC(canonical, derived_key)`，`X-Token` 再经 base64 → 异或掩码 → 反转

body 为空时也发 `{}`，且 bodyHash 算的是**紧凑 JSON 字节**（`separators=(",", ":")`、`ensure_ascii=False`），不是空字节。

### 和日志里 `Cache 'hd-info'` 的关系

旧版（产生日志那版）密钥硬编码在源码里，开抢前**不调** `runtime/profile`，直接裸发 signUp，4,049 次全部回 `Cache 'hd-info' does not allow`。新版（015）把「开抢前先调一次 `runtime/profile`」写进了链路。

两者是否就是因果关系，**目前仍是假设**。至少三种解释都未被排除：缺 `runtime/profile` 这一步、signUp 需要网关签名头、页面须先发一次自己的 hd-info 请求。判别证据只有一份：真实点击那一刻 DevTools 里 `signUp` 那条请求的 method / headers / body，以及它前面紧邻的请求。

### 两个顺手发现

- 网关两个常量（`REQUEST_SECURITY_RAW_KEY` / `REQUEST_SECURITY_CLIENT_KEY`）仍硬编码在 `local/grab.py:61-62`；015 只搬走了报名密钥，这两个没动。
- `sign_request_headers` 的 canonical 里方法写死 `"POST"`，将来若给 GET 加签会静默算错。


## 对现行文档的影响（待决策，未改）

- `docs/UI_SPEC.md:683` 现在写 RISK-001 `blocked/unproven、发布阻断未解除`，语义是「页面自发请求可能被计入本场」。按本证据，更要紧的问题是**直发拿不到成功结论、兜底又走不到**，RISK-001 需要重写而不是简单降级。
- 决策 002 的「直发 + 点击兜底」口径需要补一条：兜底触发依赖的文案与线上实际文案不一致。
- 决策 002 的「活动已开始」提示，与本证据无冲突，可以独立修订。

## 局限

1. 28 场来自同一账号、同一时段，活动类型单一，不能代表站点全貌。
2. 日志存的是截断到 30 字符的文案，完整 message 未取得；不能完全排除 `code:0` 在该站点另有成功语义。
3. **未查 `getJoinInfo`，因此无法确认这些活动在服务端到底报没报上。** 这是目前最大的未知，要确认只能登录后在「我的活动」里逐一对照。
4. 日志是**旧版**产物（硬编码密钥、不调 `runtime/profile`、要求整句精确匹配）。现行代码已按决策 015 重写，本目录的统计不能直接用来评价现行实现——它能说明的是「那版为什么无效」，不是「现在这版会不会无效」。

## 复现

```bash
grep -c '开始盯按钮' local/data/grab.log
grep -c '直发已发起' local/data/grab.log
grep -c "Cache 'hd-info'" local/data/grab.log
grep -c 'code:1' local/data/grab.log
grep -c '版本不兼容' local/data/grab.log
grep -o '第 [0-9]* 次提交' local/data/grab.log | grep -o '[0-9]*' | sort -n | tail -1
```
