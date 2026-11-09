# 本地验收：v1.2.0 发布产物（2026-11-09）

- 来源：`main` / `3d4d0ca`，`source_dirty=false`（`dist/release-v1.2.0/manifest.json`）
- 范围：实包探针、安装器同源探针、静默卸载探针
- 环境：Windows，Inno Setup 6.7.3（构建机）
- 结论：三项均通过；真机手动项（登录、时钟、条款、手机通道）未覆盖

## 1. 实包探针（决策 010）

把独立 EXE 单独拷进 `%TEMP%` 下的空目录，`CAMPUS_DATA_DIR` 指向另一个临时目录，
运行离线自检：

```powershell
$T = Join-Path $env:TEMP 'campus-acceptance-20261109'
$env:CAMPUS_DATA_DIR = Join-Path $T 'data'
Start-Process -FilePath (Join-Path $T 'standalone\campus-activity-watch-v1.2.0-win-x64.exe') `
  -ArgumentList '--runtime-check', '--report', (Join-Path $T 'report\probe.json') -Wait -PassThru
```

结果：进程退出码 0；报告

```json
{"version": "1.2.0", "frozen": true,
 "worker": "%TEMP%\\_MEI...\\grab-worker.exe",
 "ok": true, "exit_code": 0}
```

内置 worker 确实从解包目录启动并退出 0；临时数据根事后 0 个文件。

## 2. 安装器同源探针（决策 013）

静默装进隔离临时目录：

```powershell
Start-Process -FilePath 'dist\release-v1.2.0\campus-activity-watch-installer-v1.2.0-win-x64.exe' `
  -ArgumentList '/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART',('/DIR=' + (Join-Path $T 'install')) -Wait -PassThru
```

结果：退出码 0；安装目录四成员（`campus-activity-watch.exe`、`README.md`、
`遇到问题先看我.txt`、`LICENSE`）+ `unins000.exe`。安装出的主程序与独立 EXE
SHA-256 一致：

| 文件 | SHA-256 |
|---|---|
| 独立 EXE / 安装后主程序 | `34D904E86CD7AFA2216A3F38BD0955FFC3A5DF02A62859EDF52C40B464984BE7` |

安装器自身 SHA-256：`B7B9A738CA1E342630FC694831A07483B936B33AAC508AA58BA6BC15FD90E4B2`。

## 3. 静默卸载探针

```powershell
Start-Process -FilePath (Join-Path $T 'install\unins000.exe') `
  -ArgumentList '/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART' -Wait -PassThru
```

结果：退出码 0；安装目录剩余 0 个文件；`HKCU` 卸载登记与开始菜单项均已清除；
临时数据根仍为 0 个文件。静默分支跳过删除数据目录，与
`local/build/build_installer.py`（`UninstallSilent` 时直接结束 `CurUninstallStepChanged`）一致。
探针全程未以默认数据根启动程序，未触碰真实登录态。

## 未覆盖（需另行验收）

- 真机清单（决策 008）：有效登录、崩溃重开后的时钟显示、条款同意与拒绝、手机通道。
- ZIP 成员白名单、安装器安装后探针之外的签名/升级路径。
- 单测与离线 UI 浏览器验收本轮未运行。
