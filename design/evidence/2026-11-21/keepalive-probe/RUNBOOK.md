# 手机页连接复用对照实验操作手册（iPhone 真机）

本手册用于在 iPhone Safari 上对 `close`（HTTP/1.0，每请求后断开）与 `keepalive`（HTTP/1.1，保持并复用连接）两组做单一变量对照测速。所有命令同时兼容 **PowerShell 5.1** 与 **PowerShell 7**（不使用 `&&`）。

- 测速页直接复用 `design/evidence/2026-11-12/esm-verify/web/generated` 下的页面与 4 形态 × 3 次轮转（`legacy` → `flat` → `chain` → `preload-chain`，单次最多等 10 秒），不重新生成。
- 每轮只需要在 iPhone Safari 打开一次入口页 `/h9/legacy/?run=1`，页面会自动跑完 12 次并显示 `计时完成：{"h9:legacy":3,"h9:flat":3,"h9:chain":3,"h9:preload-chain":3}`。
- 结果与请求日志自动脱敏并写入 `design/evidence/2026-11-21/keepalive-probe/results/`，不要手工编辑 JSON 或 JSONL 文件。

---

## 0. 准备与端口检查（约 2 分钟）

1. 如果正在运行产品主程序或开启了产品的「手机访问」，先在产品界面关闭手机访问或退出程序，避免占用 `8765` 端口。
2. 在**仓库根**打开 PowerShell（5.1 或 7 均可），执行：

```powershell
Set-Location '<仓库根>'
$S = (Get-Location).Path
$P = Join-Path $S 'design\evidence\2026-11-21\keepalive-probe'
$R = Join-Path $P 'results'
$E = Join-Path $S 'design\evidence\2026-11-12\esm-verify'
$env:PYTHONIOENCODING = 'utf-8'
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:http_proxy = $null; $env:HTTP_PROXY = $null; $env:https_proxy = $null; $env:HTTPS_PROXY = $null; $env:all_proxy = $null
python -V
Get-NetTCPConnection -LocalPort 8765 -State Listen -ErrorAction SilentlyContinue
```

预期：`Python 3.12.x`（若 `python` 不是 3.12，将下文所有 `python` 替换为 `py -3.12`）；最后一行无输出（表示 `8765` 端口空闲）。

---

## 1. Tailscale 通道：两组各跑一轮（共 2 轮，约 8 分钟）

先准备本机的 Tailscale IPv4 地址与 MagicDNS 域名（不写进仓库文件，只在终端会话变量中使用）：

```powershell
$tsIp = Read-Host '粘贴本机 Tailscale IPv4 地址（形如 100.x.x.x）'
$tsName = Read-Host '粘贴本机 MagicDNS 域名（不带端口，或直接填同上 IP）'
```

### 1.1 第 1 轮：Tailscale × `close` 组

1. 启动服务：

```powershell
python (Join-Path $P 'scripts\serve_keepalive.py') --channel tailscale --arm close --bind $tsIp --public-host $tsName --port 8765
```

2. 看到控制台打印 `直接进四形态轮转：http://<MagicDNS 名>:8765/h9/legacy/?run=1` 后，在 **iPhone Safari** 打开该地址：
   - 保持手机亮屏，等待页面自动跳转并跑完 4 种形态 × 3 次（共 12 次上报）。
   - 当电脑控制台打印完 `-01.json` 至 `-12.json`、手机页面出现 `计时完成：{"h9:legacy":3,"h9:flat":3,"h9:chain":3,"h9:preload-chain":3}` 时，本轮完成。
3. 在电脑终端按 `Ctrl+C` 停止服务，确认终端最后一行打印 `端口已释放=True`。

### 1.2 第 2 轮：Tailscale × `keepalive` 组

1. 启动服务：

```powershell
python (Join-Path $P 'scripts\serve_keepalive.py') --channel tailscale --arm keepalive --bind $tsIp --public-host $tsName --port 8765
```

2. 在 **iPhone Safari** 打开控制台给出的 `http://<MagicDNS 名>:8765/h9/legacy/?run=1`，等自动跑完 12 次上报（控制台打印 `phone-tailscale-keepalive-ios-safari-01.json` 至 `12.json`）。
3. 按 `Ctrl+C` 停止服务，确认打印 `端口已释放=True`。

---

## 2. Cloudflare 临时隧道通道：两组交替各跑两轮（共 4 轮，约 20 分钟）

为减少临时隧道的时段波动影响，按 **`close` → `keepalive` → `close` → `keepalive`** 的顺序交替跑 4 轮；**每一轮都必须停止上一轮进程并重新启动一条新的临时隧道**。

先在终端变量中填入本机 `cloudflared.exe` 的路径：

```powershell
$cf = Read-Host '粘贴 cloudflared.exe 的完整路径'
```

### 2.1 第 1 轮：Cloudflare × `close`（第 1 次）

1. 启动服务与新临时隧道：

```powershell
python (Join-Path $P 'scripts\serve_keepalive.py') --channel cloudflare --arm close --cloudflared $cf --port 8765
```

2. 等待控制台（最多 90 秒）打印 `直接进四形态轮转：https://<随机隧道域名>/h9/legacy/?run=1`，在 **iPhone Safari** 打开该地址。
3. 等自动跑完 12 次上报（控制台打印 `phone-cloudflare-close-ios-safari-01.json` 至 `12.json`，单次若 10 秒未完成也会自动上报并跳到下一次，中途不要刷新或关闭页面）。
4. 跑完 12 次后按 `Ctrl+C` 停止服务，确认打印 `端口已释放=True`，并确认 `cloudflared` 已退出：

```powershell
Get-Process cloudflared -ErrorAction SilentlyContinue
```

（若有残留进程，执行 `Stop-Process -Name cloudflared -Force -ErrorAction SilentlyContinue`。）

### 2.2 第 2 轮：Cloudflare × `keepalive`（第 1 次）

1. 重新启动服务以建立一条新的临时隧道：

```powershell
python (Join-Path $P 'scripts\serve_keepalive.py') --channel cloudflare --arm keepalive --cloudflared $cf --port 8765
```

2. 在 **iPhone Safari** 打开控制台新打印出的 `https://<新随机隧道域名>/h9/legacy/?run=1`（**注意用本轮新域名，旧隧道已关闭**）。
3. 等自动跑完 12 次上报（控制台打印 `phone-cloudflare-keepalive-ios-safari-01.json` 至 `12.json`）。
4. 按 `Ctrl+C` 停止服务，确认 `端口已释放=True` 且 `Get-Process cloudflared -ErrorAction SilentlyContinue` 无残留。

### 2.3 第 3 轮：Cloudflare × `close`（第 2 次）

1. 再次启动服务建立新的临时隧道：

```powershell
python (Join-Path $P 'scripts\serve_keepalive.py') --channel cloudflare --arm close --cloudflared $cf --port 8765
```

2. 在 **iPhone Safari** 打开本轮新打印的 `https://<新随机隧道域名>/h9/legacy/?run=1`。
3. 等自动跑完 12 次上报（控制台会自动续号写出 `phone-cloudflare-close-ios-safari-13.json` 至 `24.json`）。
4. 按 `Ctrl+C` 停止服务，确认 `端口已释放=True` 且 `cloudflared` 已退出。

### 2.4 第 4 轮：Cloudflare × `keepalive`（第 2 次）

1. 再次启动服务建立新的临时隧道：

```powershell
python (Join-Path $P 'scripts\serve_keepalive.py') --channel cloudflare --arm keepalive --cloudflared $cf --port 8765
```

2. 在 **iPhone Safari** 打开本轮新打印的 `https://<新随机隧道域名>/h9/legacy/?run=1`。
3. 等自动跑完 12 次上报（控制台自动续号写出 `phone-cloudflare-keepalive-ios-safari-13.json` 至 `24.json`）。
4. 按 `Ctrl+C` 停止服务，确认 `端口已释放=True` 且 `cloudflared` 已退出。

---

## 3. 查看汇总、确认端口释放与脱敏自检（约 2 分钟）

全部 6 轮跑完后，在电脑终端执行：

```powershell
# 1. 确认 8765 端口已释放且 cloudflared 已退出
Get-NetTCPConnection -LocalPort 8765 -State Listen -ErrorAction SilentlyContinue
Get-Process cloudflared -ErrorAction SilentlyContinue

# 2. 运行汇总脚本（应看到 Tailscale 两组各 12 份 = 3/3 x 4 形态，Cloudflare 两组各 24 份 = 6/6 x 4 形态）
python (Join-Path $P 'scripts\summarize.py')

# 3. 脱敏残留自检（全部应为 PASS）
$files = @(Get-ChildItem $R -File | Select-Object -ExpandProperty FullName)
python (Join-Path $E 'tools\redact.py') --name $env:COMPUTERNAME --check $files
```

完成后在对话中告知「已测完」（或说明哪一轮无法完成），由执行器继续汇总并生成 `README.md`。

---

## 4. 排错速查

| 现象 | 处理方式 |
|---|---|
| 启动时报 `绑定 ...:8765 失败` | 先跑 `Get-NetTCPConnection -LocalPort 8765 -State Listen` 找到占端口的进程；若是产品主程序或上一轮未退出的 python，先关闭后再启动 |
| `cloudflared 90 秒内没有给出 trycloudflare.com 地址` | 检查外网连通性或重新执行一次命令；临时文件如写往系统临时目录（`%TEMP%`），无需手动清理 |
| 手机页面停在某个形态约 10 秒才跳下一页 | 正常现象：单个形态 10 秒内未执行完 40 个模块时，runner 会在 10 秒到点时上报一次未完成记录（`done_ms=null`）并自动跳到下一轮，**不要手动刷新** |
| 某轮中途不小心关掉了 Safari 标签页 | 先按 `Ctrl+C` 停掉该轮服务，删除 `results/` 下该轮未满 12 份的残缺上报与对应的最后一封 `requests-*.jsonl`，再重跑该轮 |
| 在电脑浏览器用 `127.0.0.1:8765` 打开报 `403 host not allowed` | 正常：服务只认当前通道白名单内的 Host（Tailscale 地址/域名或当轮隧道域名） |
