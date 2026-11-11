# 版本与发布口径

> 回答「下一个版本号是什么、什么时候升、资产怎么和版本绑定」。
> 规则来源：2026-10-25 版本线纠正（用户指出 3.x 跳版过快）与
> [决策 008 · 应用生命周期、版本单一来源与发布资产](../decisions/008-lifecycle-version-release.md)。

## 基线与当前版本

| 项 | 值 | 依据 |
|---|---|---|
| 实际已发布基线 | **v1.1.0**（2026-10-26 上传） | GitHub `releases/latest` 与 API 实查 |
| 当前正式版本 | **v1.1.1** | v1.1.0 之后的补丁版本（patch） |
| 安装版资产 | **正式发布形态** | 与独立 EXE、完整 ZIP 由同一份冻结 EXE 派生 |
| v1.0.x 与绿色版 | 历史资产，**已停止新增发布** | v1.0.2 是绿色版最后版本；新用户引导至现行资产 |

**三态不能混写**：已发布资产（Release 页真实存在的附件）、历史候选（含脏构建预览，
不可复用、不可发布）、待授权动作（下一版本的构建 / 安装探针 / tag / publish 须用户逐项授权）。
当前文档只引用已发布的 v1.1.1 资产；未来候选必须单独标注「候选」。

从未发布过 2.x/3.x；文档与 CHANGELOG 不得编造这段历史。**已发布 tag 一律不重用、
不删除、不改写**：新版本一律升号重新 `--prepare`；被取代的历史版本在各自 Release
说明中人工标注「已被 vX.Y.Z 取代」（发布侧人工动作，publish 不隐式执行）。

## 升版规则（语义化，来源唯一：仓库根 `VERSION`）

| 场景 | 动作 |
|---|---|
| 同一候选的多次计划、返修、测试与验收轮次 | **不升版**（开发证据用 commit/时间/哈希区分，不用版本号区分） |
| 正式发布后的 bug 修复 | patch +1（1.1.0 → 1.1.1） |
| 累计功能增强的下一批 | minor +1（1.1.0 → 1.2.0） |
| 需要用户迁移的兼容性破坏 | 才评估 major（谨慎，先回 decisions 记录） |

- `VERSION` 是当前软件版本唯一来源：GUI、`build_exe.py`、`make_portable.py`、`tools/release.py`
  都读它；**禁止**改文件名冒充新版本构建，禁止绕过它自定版本。
- Release tag 只能由 `VERSION` 推导（`v` + 版本）；新 tag 用 `git tag -a <tag> <已核验完整提交>`
  **显式绑定**已核验提交，不靠执行当时的 HEAD；origin 同名 tag 用只读 `git ls-remote` 独立核验
  最终提交（附注 tag 取 peeled 值优先；查询失败按错误拒绝，不当成不存在）。**ls-remote 必须同时
  请求 `<tag>` 与 `<tag>{}` 两个 pattern**（EXTRA-1：只查精确 pattern 拿不到附注 tag 的 peeled 行，
  会被对象 SHA 误判指向不符）。本地或远端指向
  不一致都在写入前拒绝、不 force 改写；远端已正确则复用，远端缺失且本地正确才 push，两边都缺
  才创建并 push，push 后再查一次远端落地。`gh release create --verify-tag` 禁止 gh 自动补 tag。
- 发布前逐项核对 manifest/版本/tag/来源一致（见决策 008 的资产绑定规则）；**人工确认之后、
  第一次 Git 写入之前**必须复核「同一干净 main、同一完整 HEAD、同一 VERSION、同一批资产指纹」
  ——确认等待期间任何变化都中止并要求重新确认；上传前再比对一次指纹。
- 引导内容版本 `TOUR_VERSION` 单独管理：软件升版**不**提升它，只有引导内容实质变化才 +1
  （见 [决策 009](../decisions/009-replayable-product-tour.md)）。

## 发版 commit 必须始终可达（2026-11-03）

- **manifest 的 commit 必须能在仓库历史里找到**：发布物的 `manifest.json` 用完整 commit 记录来源，
  发版 tag 必须绑在同一个 commit 上——tag 就是让那个 commit 一直可达的锚点。
- **改写历史前先盘点发版 tag**：运行 `git for-each-ref refs/tags` 并逐个
  `git rev-parse <tag>^{}` 列出所有发版 tag 指向的 commit，确认整理历史（`filter-repo`、`rebase`、
  `gc --prune=now` 等）之后这些 commit 仍然保留；任何一个会丢失就停下，不执行改写。
- **已知事实**：v1.2.0 的 manifest 写的 commit 在本仓库历史里查不到（2026-11-03 记录，
  证据 `design/evidence/2026-11-02/live-check.md` 第二十四节）。这条事实只说明
  「manifest 写了 commit」不等于「commit 一定可达」：每次发版后都要按上面的命令复核一次。

## 交付形态（2026-10-27 起现行：三资产同源，详见决策 008/013）

- **三种正式资产**：安装版安装器（推荐下载）、独立可用单 EXE、完整 ZIP 四成员
  （EXE、README.md、启动说明.txt、LICENSE）。三者由同一次 `--prepare` 构建的**同一份冻结
  EXE** 派生：安装器吃暂存区里那份 EXE（`build_installer.py build()` 显式传参，禁止自行
  重新构建主程序）；独立 EXE 与 ZIP 内 EXE 字节一致（publish 核验）。
- **manifest 记录三资产**：名称、大小、SHA-256、VERSION、完整 commit 与 `source_dirty`；
  publish 逐项复核三资产哈希，任何漂移或来源非显式 `false` 都拒绝。
- **安装器不与 EXE 比原始字节**（自解压容器无可比性）；同源证据走**安装后探针**：把安装包
  静默装进隔离临时目录，比对安装出的主 EXE SHA-256 与独立 EXE 一致。该探针属授权验证项，
  见决策 013 的待验收清单。
- **发布验收必须包含实包探针**：在仅含单 EXE 的空目录（cwd 同目录、`CAMPUS_DATA_DIR` 指临时目录）
  运行 `app.py --runtime-check --report <绝对JSON路径>`，实际由主程序启动内置 `worker --help`
  且两者退出 0；mock 单测与主窗口截图不能替代该证据。
- **上传资产名固定 ASCII**：`campus-activity-watch-installer-vX.Y.Z-win-x64.exe` 等；本地
  Inno 产物的中文名只留在构建目录，Release 标题与说明里用中文产品名。
- **绿色版是历史形态**（v1.0.2 及以前）：保留历史资产与 `make_portable.py` 构建能力，
  不再作为正式资产发布；旧 Release 页标注「已停止更新」属发布侧人工动作。
- 来源口径不变：正式候选须在用户验收、提交合并后从干净 main 重新构建并逐项核验；
  历史预览（含 `source_dirty=true` 的 v1.1.1 预览）不能改名复用。
- **授权边界**：prepare、构建、安装探针、tag/publish 是四个需要用户逐项授权的动作；
  未获授权时结果文件只能记 `pending_authorization`，不得用静态检查或历史测试成绩冒充。
  Release 文案只引用实际存在的附件——已发布形态必须与附件清单、manifest 和 VERSION 一致。

## 手动检查与自动安装的区别

- 帮助中的「检查更新」只在点击时读取GitHub最新正式Release，按三段整数比较，显示检查时间。
- 本机1.1.0候选高于线上1.0.2时显示预览状态，不建议降级；网络失败不作版本结论。
- 「查看发布页」只是打开固定链接，不能替代检查结果；没有自动下载、安装或后台轮询。
- 帮助入口合并与本批能力已随 v1.1.1 发布；后续功能或修复按新的版本号处理。
- **完整安装器更新（2026-10-28 起）**：检查到新版且 Release 有可校验安装包时，用户**显式
  确认后**才下载完整安装器——检查、启动和打开帮助都不自动下载。下载只走 HTTPS 并流式写
  `<tmp>`，按 manifest 登记的字节数与 SHA-256 逐项校验；失败、取消、哈希不符一律清理
  半成品并保留旧程序与用户数据。校验通过后由用户确认启动安装向导，**工具不自动退出、
  不自动重启**。首版只做完整安装器，不做差分更新（见下节）。

## 安装器资产哈希、更新基线与回滚边界

- **哈希来源唯一**：安装器的字节数与 SHA-256 来自 Release 附件 `manifest.json`（由
  `tools/release.py` 的 `write_manifest` 生成，`files` 按资产名登记 `sha256` / `bytes`）。
  运行时把 GitHub 资产列表里的 `size` 与 manifest 的 `bytes` 交叉比对，不一致即拒绝下载；
  manifest 缺失、版本不匹配、哈希格式非法都归「无可校验安装包」，退回发布页手动下载，
  **绝不**给出无法校验的下载。资产命名沿用
  `campus-activity-watch-installer-vX.Y.Z-win-x64.exe`，本期**不改**任何发布资产命名。
- **更新基线**：只有 `releases/latest` 里的**正式稳定 Release**（非 draft、非 prerelease）
  才能成为更新目标；三段整数比较，远端较小只显示预览状态、不建议降级。安装包与主程序
  的版本一致性由 manifest 的 `version` 与资产名共同锚定，二者任一不符即拒绝。
- **回滚边界**：更新流程只写 `<tmp>` 的临时目录，**不改程序目录、不改
  `%LOCALAPPDATA%\TianSoftActivityPreRegistration\data`**。因此任何失败（断流、超限、
  哈希不符、取消、启动器失败）都天然回滚：旧程序和用户数据一个字节都不变，用户只需
  重新下载或改从发布页手动安装。安装器本身替换程序文件的回滚由 Inno Setup 向导负责，
  本工具不额外做快照或备份。
- **差分更新是后续候选，不是本期范围**：差分补丁要先有补丁基线管理、产物签名、失败回滚
  和断点恢复四项前置能力，缺一不可。在这些能力就位并单独验收前，**不得**在发布资产里加入
  任何补丁类附件，也不得让更新器接受非完整安装器的下载目标。完整 ZIP 与独立 EXE 继续
  只提供发布页手动下载，不进自动更新流程。


## 历史证据与当前版本的边界

- `dist/release-v3.1.0/` 与 `dist/release-v1.1.0/`（脏预览，manifest `source_dirty=true`）都是
  **旧候选**：前者是草案期产物，后者明确标注来源脏、只能供常用流程人工验收——两者都不能改名
  当正式候选用；正式资产必须在验收、提交合并后从对应干净来源重新构建并逐项核验。
- 截图等交付物保留其真实生成版本口径（见 [current-ui/README](../archive/current-ui-2026-10-25/README.md)），
  软件候选收敛到 1.1.0 不改写旧证据的生成事实。

## 1.2.2 候选的发布兼容与验收（2026-11-10）

- 公开 `manifest.json` 必须满足已发布 1.2.1 检查器的 65,536 字节读取上限。目标文件清单保存一份，以目标清单哈希绑定 full 与 delta，使用确定性的紧凑 UTF-8 序列化。超过上限时准备阶段拒绝产出可发清单。
- `full_payload` 声明的完整版本目录 ZIP 必须进入存在性、大小、SHA-256、确认前后资产指纹和最终上传集合校验。完整 payload、delta 和拆分组件均按清单逐项核对。
- 1.2.1 的安装用户通过完整 Inno 安装器迁入版本目录。历史源码重建的 onedir 可验证差分格式，正式差分基线应对应实际分发过的版本目录清单。
- 拆分组件按稳定内容标识复用，完整功能组在所有下载、校验和组合探针成功后原子切换。旧单体包与旧固定目录继续作为兼容输入，原可用组保留到新组提交成功。
- 本轮本地验收覆盖历史 1.2.1 检查器回放、模拟上传资产集合、组件中断恢复、相同资产零下载、冻结探针和离线全量回归。技术验证、用户验收和外部发布状态分别记录。
- 组件「未安装」与「装坏」分开报告（2026-11-11）：没有组指针、没有可用旧单体包、也没有半套资产时按未安装返回 `available=False`、error 为空，界面显示「下载并安装」；有部分资产但不成组才报 `artifact_incomplete`。复现命令 `py -3.12 -m unittest discover -s local/tests -p "test_advanced_features.py"`，空数据根下两个功能均为 missing。
- 事务日志与组指针损坏按「这一步没发生过」恢复（2026-11-11）：写入改为落盘后 fsync 文件与目录，空文件或坏 JSON 不再抛 `bad_transaction`；持锁方按磁盘上可验证的目录恢复，验证不了按未安装处理，并写一条诊断日志。`cloudflared()`、`feature_status`、`remove` 均不抛。
- 换位前先清残留 `.backup-*`，删不掉就中止本次安装并保留正在使用的组件；已提交后的旧副本清理失败只记诊断，不改变安装成功的结论。持事务锁的操作回收崩溃留下的 `.stage-*`（2026-11-11）。
- 拆分资产下载遇到网络失败（连接、超时、断流、HTTP 5xx）直接报错并保留当前组，不再自动改下完整单体包；只有大小、哈希或兼容性校验不过才回退，并在进度文字里说明（2026-11-11）。

### 版本目录更新与安装器返修（2026-11-11）

起因是对「版本目录增量更新」与「历史基线增量包」的审计，下面逐条记录口径，复现命令都是离线单测，不构建、不联网。

- **安装器目录名**：`[Files]` 的 `DestDir` 对 payload 父目录原样保留，只把 `/` 换成 `\`；`numpy.libs`、`pkg-1.2.3.dist-info` 不再被删点，`_internal/cv2/data` 这类深层同名目录照装。只跳过 payload 顶层第一段为 data / config / logs / log 的路径。旧写法让安装版目录与目标清单永远对不上，增量包对安装版用户不可用。复现 `py -3.12 -X utf8 -m unittest discover -s local/tests -p "test_installer_script.py" -k PayloadDestDir`。
- **版本目录切换的适用条件**：冻结态、`update-launcher.exe` 存在、当前进程正从 `versions/<当前版本>/` 运行，三者缺一就走完整安装器。判定是 `app.version_switch_available()`，`_do_update_download` 只在它为真时才下载版本目录包；独立 EXE 与源码态直接下载完整安装器，不再留下 `.staging-*`，也不会在 `update_launch` 处被拒绝。`update_launch` 保留冻结态加启动器文件的防御判定，因为 `ready_to_restart` 只会在上面的判定为真时产生。
- **切换后主程序自退**：启动器拉起成功后推 `launching`、文案以「更新启动器已启动」开头，界面据此把「启动中…」换成「关闭本工具…」；约 1 秒后主程序走现有关窗口的「退出」动作。启动器没拉起时不退出，状态进 `failed`。
- **启动器等待父进程**：`OpenProcess` 失败且 `GetLastError` 为 87（PID 不存在）说明主程序已退出，直接放行；其他失败原因仍不切换。`OpenProcess`、`WaitForSingleObject`、`CloseHandle` 设置了函数原型，默认等待时限由 30 秒改为 120 秒。
- **目标目录已存在与坏 staging**：目标版本目录已存在时先改名为 `.old-<版本>-<随机>`，切换成功后删除，失败时改回原名并把 staging 放回原处。staging 缺固定程序时在等待父进程之前就拒绝，`current.json` 与所有版本目录不动。
- **current.json 与回退**：切换成功后写 `{"version","previous_version"}`，写入经 flush 与 fsync 再原子替换。`--start` 在 current 指向的版本不可用时依次回退 `previous_version`、版本号最大的有效目录，回退只影响这一次启动，不改写 `current.json`。
- **版本目录清理与卸载**：`updater.sweep_version_root` 只删 `versions` 下的 `.staging-*`、`.stage-*`、`.part-*`、`.old-*` 残留，以及超出 current 与 previous 的旧版本；跳过当前进程所在目录和链接，`current.json` 读不出来时只清残留；删不掉的跳过不抛。冻结态且从 `versions/<当前版本>/` 运行时，主程序启动后在后台线程调用一次。安装脚本新增 `[UninstallDelete]` 删除 `{app}` 下的 `versions`，用户数据目录不在其中，是否删除仍只由卸载时的确认决定。
- **发版前门禁**：`write_manifest` 在序列化与哈希之前检查 `files` 每一项不超过 300 MiB，超限直接中止，因为已发布的 1.2.0 与 1.2.1 客户端会把含超限项的整份清单当作无效。`--prepare` 带 `--delta-base` 时必须同时给 `--delta-base-manifest`（基线版本已发布的 `manifest.json` 本地副本），在构建之前用与更新器同一实现算出基线目录的目标清单哈希并比对，版本或哈希不符就中止；PyInstaller 构建不可复现，重建的基线生成的增量包对谁都不匹配。复现 `py -3.12 -X utf8 -m unittest discover -s local/tests -p "test_lifecycle_release.py" -k ReleaseGuard`。
- **验证边界**：以上均为离线单测与替身（Windows 句柄接口、进程启动、关窗口都不真实调用）。真实安装、版本切换、卸载仍需在打包产物上人工验收，不能用本节的单测成绩代替。

候选构建命令为 `py -3.12 -X utf8 tools/release.py --prepare --split-components`。验证记录应注明源码来源与实际运行结果，候选返修沿用 1.2.2。
