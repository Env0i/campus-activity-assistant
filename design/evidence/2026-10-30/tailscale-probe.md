# Tailscale 探测取证与状态契约

- 采集时间：2026-10-31 09:00 前后（本机 Windows）
- 采集对象：`local/infrastructure/tunnel_manager.py` 的 `tailscale_endpoint()`
- 采集方式：只读调用探测函数，不安装、不启动、不登录 Tailscale

## 一、本机实测结果

| 检查项 | 结果 |
|---|---|
| `shutil.which("tailscale")` | `None` |
| `shutil.which("tailscale.exe")` | `None` |
| `tailscale_endpoint()` | `{"available": false, "error": "tailscale_missing", "state": "missing"}` |
| `resolve_cloudflared()` | 空串（组件包未导入，PATH 中也没有 cloudflared） |

结论：本机既没有 Tailscale 也没有 cloudflared，两条远程通道当前都不可用。这是环境事实，不是代码缺陷；本轮不为取证安装任何外部程序。

## 二、已连接状态无法在本机取证

本机没有 Tailscale，所以「已连接」这一档只能用替身 JSON 固定契约，不能声称实测过。真实设备上的取证必须由使用者在装好并登录 Tailscale 后单独补，结论写进 `design/evidence/2026-10-30/phone-access-acceptance.md`。

替身样本（测试里使用，不含任何真实账号信息）：

```json
{"BackendState": "Running", "Self": {"DNSName": "box.ts.net."}}
```

## 三、冻结的状态契约

`tailscale_endpoint()` 永远返回 `available`、`state`、`text` 三个字段，失败时再加 `error`。

| 场景 | available | state | error | 判定依据 |
|---|---|---|---|---|
| 命令行不存在 | false | `missing` | `tailscale_missing` | `which("tailscale")` / `which("tailscale.exe")` 都为空 |
| 命令能跑、有 CGNAT 地址 | true | `connected` | 无 | `tailscale ip -4` 里至少一个 `100.64.0.0/10` 地址 |
| 命令能跑、无地址、`BackendState=NeedsLogin` | false | `not_logged_in` | `tailscale_not_logged_in` | 状态值明确表示未登录 |
| 命令能跑、无地址、拿不到 JSON | false | `not_logged_in` | `tailscale_not_logged_in` | 未登录时 CLI 往往直接打印 `Logged out.`，没有 JSON |
| `BackendState` 属于 Stopped / NoState / Starting / NeedsMachineAuth | false | `probe_failed` | `tailscale_probe_failed` | 认识但没就绪，提示里回显原始取值 |
| `BackendState` 是不认识的取值 | false | `probe_failed` | `tailscale_probe_failed` | 不认识就报失败，绝不显示成已连接 |
| 子进程抛错/超时 | false | `probe_failed` | `tailscale_probe_failed` | 异常类型写进 `text`，不写完整异常内容 |

两条硬规则：

1. `available: true` 只允许出现在 `state=connected`，其余一律 false。
2. `state` 是给界面用的语义字段，`backend` 是原始 `BackendState`（能取到时才带），二者不能互相替代。

## 四、取值来源的可靠性

Tailscale 官方 CLI 文档页（`https://tailscale.com/docs/reference/tailscale-cli`）只说明 `status --json` 输出机器可读状态，没有逐条列出 `BackendState` 的全部取值。因此契约按「认识集合 + 未知即失败」设计：不把没见过的取值猜成已连接，也不新增契约之外的状态。

`Stopped`、`NoState`、`Starting`、`NeedsMachineAuth` 四个取值来自 Tailscale 客户端的 ipn 状态命名惯例（推断，未经本机实测），因此：

- 它们只影响提示文案与是否可重试，不影响安全判定（全都返回 `available: false`）；
- 若实测发现某个取值不属于上述集合，它仍会落到 `probe_failed` 分支，不会误报已连接。

## 五、本轮未验证

- 真实 `Running` 状态下的 `ip -4` 与 `status --json` 输出形状（无设备）。
- 手机端通过 MagicDNS 名称访问 `http://<magicdns>:8765` 是否可用（无设备）。
- Windows 上 Tailscale 未登录时 `status --json` 的实际 stdout（推断为纯文本 `Logged out.`）。
