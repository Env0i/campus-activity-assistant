# ESM 补验操作手册（宿主机与手机）

本手册对应计划 `20261112-esm-verify`，并经 `20261112-audit-esm-repair` 返修（E1–E9、D4、D5）。命令按 **PowerShell 5.1** 写，逐段复制即可，不用 `&&`。

- 桌面样机会短暂弹出窗口，探针跑完自己退出，属正常。
- H1 只用**已装的 1.2.2 安装版**和**已发布的 1.2.2 独立 EXE**，各加 `--demo` 启动：不登录、不碰学校站点，不在本机打包，不运行安装器。
- 结果全部落在 `design/evidence/2026-11-12/esm-verify/results/`，不要手工改 JSON。
- 不要把探针的输出重定向到文件。stdout 不是 UTF-8 时，探针打印箭头会报错，进程挂住。需要重定向时先设 `$env:PYTHONIOENCODING = 'utf-8'`（第 0 节已设）。代码已兜底（F1 返修）：`probe_app.py` 与 `serve_probe.py` 的打印失败只降级，写盘后照常退出，所以即使漏设也不会挂住；这条提示保留作双保险。
- 如果 `python` 不是 3.12，把下面所有 `python` 换成 `py -3.12`（先跑 `python -V` 确认）。

---

## 0. 准备（约 3 分钟）

在**仓库根**打开 PowerShell 5.1（Win+R 输入 `powershell`），然后：

```powershell
Set-Location '<仓库根>'
$S = (Get-Location).Path
$E = Join-Path $S 'design\evidence\2026-11-12\esm-verify'
$R = Join-Path $E 'results'
New-Item -ItemType Directory -Force -Path $R | Out-Null
$env:PYTHONIOENCODING = 'utf-8'
$env:PYTHONDONTWRITEBYTECODE = '1'
$PSVersionTable.PSVersion.ToString()
python -V
python -c "from importlib.metadata import version;print('pywebview',version('pywebview'))"
python -m PyInstaller --version
```

预期：`5.1.x`；`Python 3.12.x`；`pywebview 6.2.1`；最后一行打印 PyInstaller 版本号。

- **PyInstaller（E9）**：「发版构建环境」指你平时运行 `tools\release.py` 的那个 Python。先用那个环境里已有的 PyInstaller，`python -m PyInstaller --version` 能打印版本就直接用，不装。
- 只有它报「No module named PyInstaller」，才执行 `python -m pip install pyinstaller`，并把装上后的版本号写进勾选表「环境」。

失败记录：把报错原文追加到 `results/HOST-CHECKLIST.md` 的「备注」，不要改脚本。

---

## 1. H7 版本清单（约 3 分钟）

### 1.1 组件版本

```powershell
@'
import json, platform, sys
from importlib.metadata import version, PackageNotFoundError
out = sys.argv[1]
names = ["pywebview", "bottle", "proxy-tools", "pythonnet", "clr-loader", "pyinstaller"]
data = {"python": sys.version.split()[0], "platform": platform.platform()}
for name in names:
    try:
        data[name] = version(name)
    except PackageNotFoundError:
        data[name] = "未安装"
json.dump(data, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print(json.dumps(data, ensure_ascii=False, indent=2))
'@ | python - (Join-Path $R 'host-versions.json')
```

预期：打印 7 个字段，写盘 `results/host-versions.json`。
失败记录：命令报错就贴原文；包查不到会写「未安装」，不算失败。

### 1.2 WebView2 运行时版本

```powershell
$keys = @(
  'HKLM:\SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}',
  'HKLM:\SOFTWARE\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}',
  'HKCU:\SOFTWARE\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}'
)
$wv = $null
foreach ($k in $keys) {
  $wv = (Get-ItemProperty -Path $k -Name pv -ErrorAction SilentlyContinue).pv
  if ($wv) { break }
}
if ($wv) { "WebView2 运行时 $wv" } else { "WebView2 运行时 未找到（用 navigator.userAgent 兜底）" }
$wv | Out-File -FilePath (Join-Path $R 'host-webview2-version.txt') -Encoding utf8
```

预期：一个 `1xx.0.xxxx.xx` 形式的版本号。找不到时，桌面结果 JSON 里的 `ua` 字段同样能读到 `Edg/` 版本。

### 1.3 pywebview 三处源码摘录（锁版本依据）

```powershell
@'
import inspect, os, sys
import webview, webview.util, webview.platforms.edgechromium as edge
out = sys.argv[1]
root = os.path.dirname(webview.__file__)
lines = []
def dump_func(label, obj):
    src, start = inspect.getsourcelines(obj)
    lines.append("=== %s（%s:%d）===" % (label, os.path.relpath(inspect.getsourcefile(obj), root), start))
    lines.extend(line.rstrip() for line in src[:12])
    lines.append("")
def dump_hits(label, path, needles, before=1, after=4):
    text = open(path, encoding="utf-8", errors="replace").read().splitlines()
    lines.append("=== %s（%s）===" % (label, os.path.relpath(path, root)))
    shown = set()
    for i, line in enumerate(text, 1):
        if any(n in line for n in needles):
            for k in range(max(1, i - before), min(len(text), i + after) + 1):
                if k not in shown:
                    lines.append("%d: %s" % (k, text[k - 1].strip()))
                    shown.add(k)
            lines.append("")
dump_func("is_local_url", webview.util.is_local_url)
dump_hits("自动起内置服务", inspect.getsourcefile(webview.start),
          ["has_local_urls", "http.start_global_server"])
dump_hits("ALLOW_FILE_URLS", inspect.getsourcefile(edge),
          ["ALLOW_FILE_URLS"], 0, 1)
text = "\n".join(lines)
open(out, "w", encoding="utf-8").write(text + "\n")
print(text)
'@ | python - (Join-Path $R 'host-pywebview-source.txt')
```

预期：三段摘录，第一段是 `is_local_url`，第二段含 `has_local_urls` 与 `http.start_global_server`，第三段是 `ALLOW_FILE_URLS` 与 `--allow-file-access-from-files`。
结果文件：`results/host-pywebview-source.txt`。
失败记录：某个符号取不到时脚本会直接报错，把报错原文贴进勾选表。

---

## 2. H1 已装产品与已发布独立 EXE 的加载方式（约 15 分钟）

目的：证明真实产品在 `--demo` 下经 `127.0.0.1:<随机端口>` 供页（H1 成立）。对象只有两个：

- 2.3 用户**已装**的 1.2.2 安装版；
- 2.4 **已发布**的 1.2.2 独立 EXE（从发布页下载的那份，不是本机构建的）。

不做的事：不运行 `tools\release.py --prepare`，不运行安装器，不覆盖已装版本。

### 2.1 先关掉正在用的产品

1. 关闭所有正在运行的产品窗口，并在托盘里退出。单实例守护会把新启动的那份交给已经开着的那份，取证的就不是这次启动的进程。
2. 确认没有残留进程（只看名字，不看路径）：

```powershell
Get-Process | Where-Object { $_.ProcessName -match 'campus|tian|activity|watch' } | Select-Object Id, ProcessName
```

预期：没有输出。有输出就先在任务管理器里结束它们，再继续。

### 2.2 粘贴辅助函数（整段粘贴一次，2.3 和 2.4 依赖它）

```powershell
function Get-TreeIds([int]$RootId) {
  # 父进程及其全部子进程，按 ParentProcessId 递归展开
  $all = @(Get-CimInstance -ClassName Win32_Process -ErrorAction SilentlyContinue)
  $ids = New-Object System.Collections.ArrayList
  [void]$ids.Add($RootId)
  $i = 0
  while ($i -lt $ids.Count) {
    $parent = [int]$ids[$i]
    foreach ($c in $all) {
      $cid = [int]$c.ProcessId
      if (([int]$c.ParentProcessId) -eq $parent -and -not $ids.Contains($cid)) { [void]$ids.Add($cid) }
    }
    $i++
  }
  return ,([int[]]$ids.ToArray())
}
function Get-TreePorts([int[]]$Ids) {
  @(Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue |
    Where-Object { $Ids -contains [int]$_.OwningProcess } |
    Select-Object -ExpandProperty LocalPort -Unique)
}
function Get-TreeNames([int[]]$Ids) {
  # 只记进程名和进程号，不记路径
  @(Get-CimInstance -ClassName Win32_Process -ErrorAction SilentlyContinue |
    Where-Object { $Ids -contains [int]$_.ProcessId } |
    ForEach-Object { $_.Name + '#' + $_.ProcessId })
}
function Stop-Tree([int[]]$Ids) {
  # 子进程先停，根进程最后停
  $order = @($Ids)
  [array]::Reverse($order)
  foreach ($id in $order) { Stop-Process -Id $id -Force -ErrorAction SilentlyContinue }
}
function Invoke-DemoProbe([string]$Label, [string]$Exe, [string]$OutName) {
  $info = Get-Item -LiteralPath $Exe
  $sha = (Get-FileHash -Path $Exe -Algorithm SHA256).Hash
  $p = Start-Process -FilePath $Exe -ArgumentList '--demo' -PassThru
  Start-Sleep -Seconds 15
  $ids = Get-TreeIds $p.Id
  $ports = @(Get-TreePorts $ids)
  if ($ports.Count -eq 0) {
    Start-Sleep -Seconds 5
    $ids = Get-TreeIds $p.Id
    $ports = @(Get-TreePorts $ids)
  }
  $names = Get-TreeNames $ids
  $rows = foreach ($port in $ports) {
    $url = "http://127.0.0.1:$port/index.html"
    # 响应变量叫 $resp，不能叫 $r：PowerShell 变量名不区分大小写，$r 会覆盖结果目录 $R
    try {
      $resp = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 5
      [pscustomobject]@{ port = $port; status = [int]$resp.StatusCode
                         head = $resp.Content.Substring(0, [Math]::Min(200, $resp.Content.Length)) }
    } catch {
      [pscustomobject]@{ port = $port; status = $null; head = 'ERR: ' + $_.Exception.Message }
    }
  }
  $obj = [pscustomobject]@{
    label = $Label
    args = '--demo'
    file_version = $info.VersionInfo.FileVersion
    product_version = $info.VersionInfo.ProductVersion
    sha256 = $sha
    tree_processes = $names
    listen_ports = $ports
    rows = @($rows)
  }
  $obj | ConvertTo-Json -Depth 5 | Out-File -FilePath (Join-Path $R $OutName) -Encoding utf8
  $obj | Format-List label, file_version, product_version, listen_ports, tree_processes
  Stop-Tree $ids
  Start-Sleep -Seconds 2
  '停止后仍在监听的端口（应为空）：' + (@(Get-TreePorts $ids) -join ',')
}
```

粘贴后没有报错即可。

### 2.3 已装的 1.2.2 安装版

要填的是 `<安装目录>\versions\<版本目录>\campus-activity-watch.exe`，**不能填 `update-launcher.exe`**：启动器不会把 `--demo` 传给主程序，取到的就不是演示模式。

```powershell
$installed = Read-Host '粘贴已装 1.2.2 的 EXE 完整路径（只在本机使用，不写进结果）'
Invoke-DemoProbe 'installed-run1' $installed 'host-product-installed-1.2.2-run1.json'
Invoke-DemoProbe 'installed-run2' $installed 'host-product-installed-1.2.2-run2.json'
```

预期：`listen_ports` 非空；`rows` 里 `status` 为 200，`head` 以 `<!DOCTYPE html>` 开头；`file_version` 含 `1.2.2`；两次启动的端口不同；最后一行为空。
结果文件：`results/host-product-installed-1.2.2-run1.json`、`...-run2.json`。
失败记录：端口为空时函数已自动再等 5 秒重查；仍为空就记「无监听端口」，把 `tree_processes` 原样贴进勾选表。`status` 为空时保留 `head` 里的错误原文，不改写。

### 2.4 已发布的 1.2.2 独立 EXE

```powershell
$standalone = Read-Host '粘贴从发布页下载的 1.2.2 独立 EXE 完整路径（不是本机构建的）'
Invoke-DemoProbe 'standalone-run1' $standalone 'host-product-standalone-1.2.2-run1.json'
Invoke-DemoProbe 'standalone-run2' $standalone 'host-product-standalone-1.2.2-run2.json'
```

预期与 2.3 相同。结果文件：`results/host-product-standalone-1.2.2-run1.json`、`...-run2.json`。

### 2.5 结论填进勾选表

在 `results/HOST-CHECKLIST.md` 的 H1 两行写下：`file_version`、`listen_ports`、`status`、`head` 首行、两次端口是否不同、停止后端口是否为空。
判定标准：两种形态都能从 `127.0.0.1:<随机端口>` 取到 `index.html`，且两次启动端口不同，说明产品经 pywebview 内置 HTTP 服务供页（H1 成立）。

---

## 3. H6 打包样机：两种形态 × 三种目录（约 20 分钟）

前提：第 0 节的 PyInstaller 可用。样机入口是 `desktop\probe_app.py`，资源用 `--add-data` 打进 `web/generated` 与 `tools`，与产品 `local/build/build_exe.py:73-88` 的写法一致。

3.4–3.7 的启动一律用 `Start-Process -Wait`，顺序执行。`& <exe>` 在 PowerShell 5.1 下不会等 GUI 程序退出，21 次启动会瞬间返回，结果文件一个也写不出来。

### 3.1 打 onefile

```powershell
$D = Join-Path $E 'desktop'
$W = Join-Path $E 'web\generated'
$T = Join-Path $E 'tools'
$B = Join-Path $E 'build'
New-Item -ItemType Directory -Force -Path (Join-Path $B 'onefile'),(Join-Path $B 'onedir') | Out-Null

python -m PyInstaller --noconfirm --clean --name esm-probe --onefile --windowed --collect-all webview --add-data "$W;web/generated" --add-data "$T;tools" --distpath (Join-Path $B 'onefile\dist') --workpath (Join-Path $B 'onefile\build') --specpath (Join-Path $B 'onefile') (Join-Path $D 'probe_app.py')
```

预期：`build\onefile\dist\esm-probe.exe` 生成。失败时把最后 20 行贴进勾选表。

### 3.2 打 onedir

```powershell
python -m PyInstaller --noconfirm --clean --name esm-probe --onedir --windowed --collect-all webview --add-data "$W;web/generated" --add-data "$T;tools" --distpath (Join-Path $B 'onedir\dist') --workpath (Join-Path $B 'onedir\build') --specpath (Join-Path $B 'onedir') (Join-Path $D 'probe_app.py')
```

预期：`build\onedir\dist\esm-probe\esm-probe.exe`。

### 3.3 三种安装目录

```powershell
$base = Join-Path $env:USERPROFILE 'esm-probe-paths'
$dirs = [ordered]@{
  'plain' = Join-Path $base 'plain'
  'space' = Join-Path $base 'with space'
  'cjk'   = Join-Path $base '中文 路径'
}
foreach ($k in $dirs.Keys) { New-Item -ItemType Directory -Force -Path $dirs[$k] | Out-Null }
$dirs.Values
```

预期：三个目录，分别覆盖纯英文、含空格、含中文与空格。

### 3.4 onefile 跑三种目录

```powershell
$one = Join-Path $B 'onefile\dist\esm-probe.exe'
foreach ($k in $dirs.Keys) { Copy-Item $one (Join-Path $dirs[$k] 'esm-probe.exe') -Force }
$scenarios = 'product','h11','cycle','h9-legacy','h9-flat','h9-chain','h9-preload'
foreach ($k in $dirs.Keys) {
  foreach ($sc in $scenarios) {
    $out = Join-Path $R ("host-onefile-$k-$sc.json")
    Start-Process -FilePath (Join-Path $dirs[$k] 'esm-probe.exe') -ArgumentList ('--scenario {0} --out "{1}"' -f $sc, $out) -Wait -PassThru | Out-Null
  }
}
```

预期：每个场景打印一行 `[desktop] <场景> → ...`，窗口闪现 3–8 秒后退出；共 21 个 `host-onefile-*.json`。
重点看：`cjk` 目录下 `snapshot.ready = true` 且 `snapshot.caps` 有值；`h11` 的 `fallback.shown = true`。
失败记录：没写出文件的，把控制台输出和 `build\onefile\build\esm-probe\warn-esm-probe.txt` 一起贴进勾选表。

### 3.5 onefile 连跑 5 次

```powershell
1..5 | ForEach-Object {
  $n = '{0:00}' -f $_
  $out = Join-Path $R ("host-onefile-plain-run$n.json")
  Start-Process -FilePath (Join-Path $dirs['plain'] 'esm-probe.exe') -ArgumentList ('--scenario product --out "{0}"' -f $out) -Wait -PassThru | Out-Null
}
```

预期：5 次都写出文件，`snapshot.ready = true` 的 5/5。任何一次超时无文件，记「第 N 次未写出」。

### 3.6 onedir 跑三种目录

```powershell
$od = Join-Path $B 'onedir\dist\esm-probe'
foreach ($k in $dirs.Keys) {
  $dst = Join-Path $dirs[$k] 'onedir'
  New-Item -ItemType Directory -Force -Path $dst | Out-Null
  Copy-Item (Join-Path $od '*') $dst -Recurse -Force
  foreach ($sc in $scenarios) {
    $out = Join-Path $R ("host-onedir-$k-$sc.json")
    Start-Process -FilePath (Join-Path $dst 'esm-probe.exe') -ArgumentList ('--scenario {0} --out "{1}"' -f $sc, $out) -Wait -PassThru | Out-Null
  }
}
```

预期：同 3.4，共 21 个 `host-onedir-*.json`。

### 3.7 H2 对照：file-url-noallow（E1）

```powershell
foreach ($k in $dirs.Keys) {
  $out = Join-Path $R ("host-onefile-$k-file-url-noallow.json")
  Start-Process -FilePath (Join-Path $dirs[$k] 'esm-probe.exe') -ArgumentList ('--scenario file-url-noallow --out "{0}"' -f $out) -Wait -PassThru | Out-Null
}
```

预期：3 个文件。每个文件里 `allow_file_urls` 为 `false`，`allow_file_urls_is_pywebview_default` 为 `false`。这是对照组：显式关掉 `ALLOW_FILE_URLS` 后 file:// 页面的模块还能不能跑，要如实记下 `snapshot.ready`、`snapshot.caps`。
不要因为 `ready = false` 就改探针或页面，那正是要看的结果。

---

## 4. H8 / H9 / H10 / H11 手机真机（约 30 分钟）

手机样机服务会：只服务 `web/generated/manifest.json` 登记的文件；带产品同款安全头（照 `local/infrastructure/phone_http.py:34-42`）；校验 Host，被拒的 Host 写日志前先脱敏；上报只收 64KB 内的 JSON；默认 15 分钟自动退出，退出前写一行「端口已释放=True/False」。

### 4.1 Tailscale 通道

先拿地址（二选一）：

```powershell
tailscale ip -4
tailscale status --json | ConvertFrom-Json | ForEach-Object { $_.Self.DNSName }
```

没有 `tailscale` 命令：在 Tailscale 托盘菜单里复制本机 IP 与机器名。

```powershell
$tsIp = Read-Host '粘贴 Tailscale 地址（100.x.x.x）'
$tsName = Read-Host '粘贴 MagicDNS 名（不带端口）'
python (Join-Path $E 'phone\serve_probe.py') --channel tailscale --bind $tsIp --public-host $tsName --port 8765
```

预期：打印 `手机打开：http://<MagicDNS 名>:8765/`；日志从这一刻起写 `results/phone-tailscale-server.log`（已脱敏）。
窗口保持不关，另开一节做手机操作。结束时 `Ctrl+C`，日志末行应为 `端口已释放=True`。

### 4.2 Cloudflare 临时隧道（HTTPS）

`cloudflared.exe` 的路径由你提供，手册不记录它。

```powershell
$cf = Read-Host '粘贴 cloudflared.exe 的完整路径'
python (Join-Path $E 'phone\serve_probe.py') --channel cloudflare --cloudflared $cf --port 8765
```

预期：最多 90 秒后打印 `手机打开：https://<随机>.trycloudflare.com/`，并写 `results/phone-cloudflare-server.log`。
失败记录：90 秒没出地址，把 cloudflared 的输出（已脱敏）和报错原文贴进勾选表；不要手工拼隧道地址。

### 4.3 手机上的页面顺序

每台设备、每个浏览器、每个通道各做一次，建议顺序：

| 顺序 | 地址 | 覆盖 | 预期看到 |
|---|---|---|---|
| 1 | `/` | 落地页 | 五个探针入口 |
| 2 | `/h2/page.html` | H2/H4/H5 | `通过：{...}` 或 `有失败：{...}`，含协议、host、UA |
| 3 | `/h3/cycle/` | H3 | `失败（预期）：ReferenceError: Cannot access 'a' before initialization` |
| 4 | `/h9/legacy/` | H9 | 自动连跑 4 形态 × 3 次，最后显示各形态计数；中途别关页面 |
| 5 | `/h11/` | H11 | 约 5 秒后出现「页面没有加载完整，请刷新或重新扫码」 |

说明：

- 同一浏览器把 `/h9/legacy/` 打开一次即可，页面自己会跳完 12 次。
- H2/H11 各打开 3 次，以满足「每种通道各 3 次」；每次都会生成一个结果文件。
- 微信/飞书扫码进的是内置浏览器，也算一个独立浏览器，单独记一行。

### 4.4 看汇总

服务运行期间，在**手机浏览器**打开 `<当前通道地址>/__summary`（例如 `http://<MagicDNS 名>:8765/__summary`），会看到 `total`、`counts`、`failures`。
不要在电脑上用 `127.0.0.1` 访问：直连通道不认这个 Host，会返回 403，这是设计如此。

### 4.5 每台设备要记的

在 `results/HOST-CHECKLIST.md` 里逐台填写：

- 设备型号与系统版本（例如「安卓 14」）。
- 浏览器与完整 User-Agent（结果 JSON 的 `payload.ua` 里有）。
- 两种通道是否都跑通；没跑的写「未测：没有设备 / 不用该浏览器」。

---

## 5. 收尾（约 5 分钟）

```powershell
Set-Location $S
git log --oneline -3
git status --short
$files = @(Get-ChildItem $R -File | Select-Object -ExpandProperty FullName)
python (Join-Path $E 'tools\redact.py') --name $env:COMPUTERNAME --check $files
Get-ChildItem $E -Recurse -Directory -Filter __pycache__ | Select-Object -ExpandProperty FullName
```

预期：`git status --short` 只多出 `?? design/evidence/2026-11-12/esm-verify/`，以及计划里已声明的 `design/proposals/engineering-refactor.md` 与 `design/evidence/2026-11-12/refactor-audit/`。出现别的改动：**停下并报告，不要回滚**。
`redact.py --check` 预期全部 `PASS`。最后一条命令没有输出。
任何 `FAIL`：停下，把文件名和残留片段报告给执行方，不要手工改结果文件。

最后勾完 `results/HOST-CHECKLIST.md` 的勾选表，把 `results/` 留在仓库同一位置即可。

---

## 6. 勾选表（与 HOST-CHECKLIST.md 对应）

| 编号 | 项 | 结果 | 备注 |
|---|---|---|---|
| H7 | 组件版本 + WebView2 + 源码摘录 |  |  |
| H1-A | 已装 1.2.2 安装版（`--demo`，两次启动） |  |  |
| H1-B | 已发布 1.2.2 独立 EXE（`--demo`，两次启动） |  |  |
| H2 | file-url-noallow 对照（onefile × 三种目录） |  |  |
| H6-A | onefile × 纯英文目录 |  |  |
| H6-B | onefile × 含空格目录 |  |  |
| H6-C | onefile × 中文含空格目录 |  |  |
| H6-D | onefile 连跑 5 次 |  |  |
| H6-E | onedir × 三种目录 |  |  |
| H8-A | Tailscale 通道 |  |  |
| H8-B | Cloudflare 通道 |  |  |
| H9 | 四形态 × 3 次耗时 |  |  |
| H10 | 设备 / 浏览器清单 |  |  |
| H11 | 桌面与手机兜底提示 |  |  |

---

## 7. 排错速查

| 现象 | 先做什么 |
|---|---|
| `python` 找不到 | 改用 `py -3.12`，或把 Python 3.12 加入 PATH |
| `python -m PyInstaller` 找不到模块 | 按第 0 节：先确认发版构建环境，确实没有才 `python -m pip install pyinstaller`，并记版本 |
| 样机窗口不出现、进程不退 | 按进程树停止（2.2 的 `Stop-Tree`，或 `Stop-Process -Id <PID> -Force`），把场景名记进勾选表；不要改 `probe_app.py` 的退出方式 |
| 探针挂住、窗口不关，输出里有 `UnicodeEncodeError` | 输出被重定向了。先 `$env:PYTHONIOENCODING = 'utf-8'`，不要重定向，重跑 |
| 端口为空 | 先看 `tree_processes`，有没有产品进程；启动后立刻退出多半是单实例守护，回到 2.1 确认产品已全部关闭；等 5 秒重查 |
| 端口只在子进程上 | 正常：onefile 与安装版的启动器会再起子进程，结果里 `tree_processes` 已包含 |
| 手机打不开 Tailscale 地址 | 确认手机在同一 tailnet、服务窗口没被防火墙拦住；换 MagicDNS 名与 100.x 各试一次 |
| `__summary` 返回 403 | 正常：必须用当前通道的域名访问，不能用 `127.0.0.1` |
| 打包后页面空白 | 看 `snapshot.collect_error` 与 `build\*\build\esm-probe\warn-esm-probe.txt`，记下 `location.protocol` |
| `redact.py --check` 报残留 | 把文件名和残留片段报告给执行方；不要手改 JSON |

## 8. 不允许做的事

- 不运行 `tools\release.py`，不运行安装器，不覆盖已装版本。
- 不改 `local/**`、`server/**`、`tools/**`、`docs/**`、`AGENTS.md`、`CLAUDE.md`。
- 不把隧道地址、tailnet 名、100.x 地址、截图里的地址栏写进仓库或勾选表。
- 不把真实站点地址、账号、验证码、日志里的 cookie 贴进任何结果文件。
- 不为了「跑绿」改断言、改结果 JSON 或删掉失败的场景。
