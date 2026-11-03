# 直发报名回包核对（2026-11-02）

## 结论

桌面端 28 场真实运行里，**直发通道没有产出过一次成功结论，也没有触发过一次点击兜底**：4,049 次直发的回包全是 `code:0` + `Cache 'hd-info' does not allow ...`，而代码的降级条件要求 message 精确等于「版本不兼容，请刷新页面或清除缓存后重试」。

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

## 代码判据

`local/grab.py` 的 `_apply_conclusion`（`grab.py:2280-2303`）：

- `code == 1` → 记成功（`resp_ok`），粘性，后续失败不改写
- `str(code) == "4001"` → 记登录失效
- `str(code).strip() == "0"` **且** message 去掉末尾句号后精确等于 `版本不兼容，请刷新页面或清除缓存后重试` → 本场降级为点击兜底

实际文案是 `Cache 'hd-info' does not allow ...`，三条都不满足，因此既不判成功、也不降级，继续按次数重发。另外 `grab.py:2289` 把 message 截到 30 字符写进 `last_reason`，所以日志里的文案是截断后的。

## 对现行文档的影响（待决策，未改）

- `docs/UI_SPEC.md:683` 现在写 RISK-001 `blocked/unproven、发布阻断未解除`，语义是「页面自发请求可能被计入本场」。按本证据，更要紧的问题是**直发拿不到成功结论、兜底又走不到**，RISK-001 需要重写而不是简单降级。
- 决策 002 的「直发 + 点击兜底」口径需要补一条：兜底触发依赖的文案与线上实际文案不一致。
- 决策 002 的「活动已开始」提示，与本证据无冲突，可以独立修订。

## 局限

1. 28 场来自同一账号、同一时段，活动类型单一，不能代表站点全貌。
2. 日志存的是截断到 30 字符的文案，完整 message 未取得；不能完全排除 `code:0` 在该站点另有成功语义。
3. **未查 `getJoinInfo`，因此无法确认这些活动在服务端到底报没报上。** 这是目前最大的未知，要确认只能登录后在「我的活动」里逐一对照。

## 复现

```bash
grep -c '开始盯按钮' local/data/grab.log
grep -c '直发已发起' local/data/grab.log
grep -c "Cache 'hd-info'" local/data/grab.log
grep -c 'code:1' local/data/grab.log
grep -c '版本不兼容' local/data/grab.log
grep -o '第 [0-9]* 次提交' local/data/grab.log | grep -o '[0-9]*' | sort -n | tail -1
```
