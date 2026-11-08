# L6 文档反引号路径引用核验：docs / design/specs / design/decisions / README / AGENTS（2026-11-08）

只读核验，没有改任何文档。对 40 篇文档里反引号内的仓库路径引用逐条 test -e 核验，194 条唯一路径全量收录于下，供判断哪些文档引用需要补丁。

## 范围与方法

- **范围**：git ls-files 的 docs/*.md（不含 docs/archive/）、design/specs/**、design/decisions/**、README.md、AGENTS.md，共 40 篇，其中 34 篇含反引号路径引用。
- **方法**：脚本逐行提取反引号内以 local/、server/、tools/、contracts/、design/、docs/ 开头的路径引用（全文去重，逐字保留），对每个唯一路径用 os.path.exists（等同 test -e）核实；带 :行号 的拆出路径部分核行数；带命令参数的拆出可执行路径。
- **死链复核**：对每个死链用 git ls-files 找同名/相似名文件；命中即给「改名 → 新路径」并引实际文件为证。
- **基准**：commit `a85209e`（素材自注）。
- **搬运与复核（2026-11-08）**：素材三张表机械搬运，39＋12＋143＝194 条无增删。整理后抽样复核 8 处：docs/README.md:58 旧路径 `local/build_advanced.py` 磁盘不存在、右列 `local/build/build_advanced.py` 存在；对照表 96 行目标 `design/archive/prototype-2026-10-22/proto/shoot.py` 存在；`server/config.json`、`local/data` 实测为 gitignore（`git check-ignore` 命中）；存在类抽 `local/domain/signup_reply.py`、`docs/RETRY_POLICY_GUIDE.md`、`local/ui/views/help.js`、`tools/release.py` test -e 全真。与素材判定一致，未改素材任何条目。（对抗审阅后 `local/config.json` 一条由存在表移入有意表，统计前后值见文末修订记录。）

## 统计

| 判定 | 条数 |
|---|---|
| 存在 | 142 |
| 死链 | 39 |
| 有意（不算死链，理由见下） | 13 |
| 改名建议（有实际文件证据） | 39 |
| 删除建议 | 0 |
| NEEDS-HUMAN | 0 |
| 合计（唯一路径引用） | 194 |

- 39 条死链全部集中在 docs/README.md:58-96 的「旧路径 → 新路径」迁移对照表旧路径列；同表右列即改名目标，39 个目标全部存在（已逐一核实）。
- 另有 `server/config.json`、`local/config.json` 2 条按 gitignore 运行配置归入「有意」（local/config.json 本机存在、换干净检出即成死链，与 server/config.json 同口径，见文末修订记录）。
- 唯一路径引用 194 条按出处目录分布（一篇引用可计入多个组）：docs=151，design/specs=18，design/decisions=44，README.md=11，AGENTS.md=29。
- 存在 142 条中：带行号且行号有效的 6 条（local/app.py:102/198/3067、local/grab.py:2144/906、local/gui.py:40）；带命令参数的 2 条。

## 死链全表（39 条，全部出自 docs/README.md 迁移对照表旧路径列）

「判定」均为改名：对照表右列即新路径，39 条逐一 test -e 为真。对抗复核补强：39 对经 git 史复核，27 对 blob 完全一致精确搬移、12 对搬移同时改写文内自指路径，39/39 成立（证据强于原报告「test -e + 右列存在」表述）。

| 位置 | 引用原文（旧路径，test -e 为假） | 判定 | 新路径（对照表右列，test -e 为真） |
|---|---|---|---|
| docs/README.md:58 | `local/build_advanced.py` | 改名 | `local/build/build_advanced.py` |
| docs/README.md:59 | `local/build_exe.py` | 改名 | `local/build/build_exe.py` |
| docs/README.md:60 | `local/build_installer.py` | 改名 | `local/build/build_installer.py` |
| docs/README.md:61 | `local/make_portable.py` | 改名 | `local/build/make_portable.py` |
| docs/README.md:62 | `local/1-登录.bat` | 改名 | `local/launchers/1-登录.bat` |
| docs/README.md:63 | `local/2-抢活动.bat` | 改名 | `local/launchers/2-抢活动.bat` |
| docs/README.md:64 | `local/3-检查登录和活动.bat` | 改名 | `local/launchers/3-检查登录和活动.bat` |
| docs/README.md:65 | `local/4-图形界面.bat` | 改名 | `local/launchers/4-图形界面.bat` |
| docs/README.md:66 | `local/_py.bat` | 改名 | `local/launchers/_py.bat` |
| docs/README.md:67 | `local/install.bat` | 改名 | `local/launchers/install.bat` |
| docs/README.md:68 | `local/启动不了点我.txt` | 改名 | `local/launchers/启动不了点我.txt` |
| docs/README.md:69 | `local/遇到问题先看我.txt` | 改名 | `local/launchers/遇到问题先看我.txt` |
| docs/README.md:70 | `docs/superpowers/discuss/2026-10-30-phone-access-channel.md` | 改名 | `docs/archive/process/2026-10-30/discuss/2026-10-30-phone-access-channel.md` |
| docs/README.md:71 | `docs/superpowers/findings/2026-10-31-ui-findings.md` | 改名 | `docs/archive/process/2026-10-31/findings/2026-10-31-ui-findings.md` |
| docs/README.md:72 | `docs/superpowers/handoff/2026-10-31-codex-handoff-group2.md` | 改名 | `docs/archive/process/2026-10-31/handoff/2026-10-31-codex-handoff-group2.md` |
| docs/README.md:73 | `docs/superpowers/handoff/2026-10-31-mobile-ui-handoff.md` | 改名 | `docs/archive/process/2026-10-31/handoff/2026-10-31-mobile-ui-handoff.md` |
| docs/README.md:74 | `docs/superpowers/handoff/2026-10-31-phone-access-handoff.md` | 改名 | `docs/archive/process/2026-10-31/handoff/2026-10-31-phone-access-handoff.md` |
| docs/README.md:75 | `docs/superpowers/plans/2026-10-30-phone-access-channel.md` | 改名 | `docs/archive/process/2026-10-30/plans/2026-10-30-phone-access-channel.md` |
| docs/README.md:76 | `docs/superpowers/plans/2026-10-30-phone-ui-failure-repair.md` | 改名 | `docs/archive/process/2026-10-30/plans/2026-10-30-phone-ui-failure-repair.md` |
| docs/README.md:77 | `docs/superpowers/plans/2026-10-31-phone-access-channel-redesign.md` | 改名 | `docs/archive/process/2026-10-31/plans/2026-10-31-phone-access-channel-redesign.md` |
| docs/README.md:78 | `docs/superpowers/plans/2026-10-31-phone-access-repair-followup.md` | 改名 | `docs/archive/process/2026-10-31/plans/2026-10-31-phone-access-repair-followup.md` |
| docs/README.md:79 | `docs/superpowers/plans/2026-10-31-phone-access-repair.md` | 改名 | `docs/archive/process/2026-10-31/plans/2026-10-31-phone-access-repair.md` |
| docs/README.md:80 | `docs/superpowers/plans/2026-10-31-phone-control-release-publication-repair.md` | 改名 | `docs/archive/process/2026-10-31/plans/2026-10-31-phone-control-release-publication-repair.md` |
| docs/README.md:81 | `docs/UI_DESIGN.md` | 改名 | `docs/archive/UI_DESIGN.md` |
| docs/README.md:82 | `docs/acceptance/ACCEPTANCE-20261031.md` | 改名 | `design/evidence/2026-10-31/ACCEPTANCE-20261031.md` |
| docs/README.md:83 | `docs/acceptance/UI-SPEC9-AND-D-STATUS-20261031.md` | 改名 | `design/evidence/2026-10-31/UI-SPEC9-AND-D-STATUS-20261031.md` |
| docs/README.md:84 | `design/current-ui/README.md` | 改名 | `design/archive/current-ui-2026-10-25/README.md` |
| docs/README.md:85 | `design/prototype/app.html` | 改名 | `design/archive/prototype-2026-10-22/app.html` |
| docs/README.md:86 | `design/prototype/app/app.css` | 改名 | `design/archive/prototype-2026-10-22/app/app.css` |
| docs/README.md:87 | `design/prototype/app/app.js` | 改名 | `design/archive/prototype-2026-10-22/app/app.js` |
| docs/README.md:88 | `design/prototype/app/led.js` | 改名 | `design/archive/prototype-2026-10-22/app/led.js` |
| docs/README.md:89 | `design/prototype/components.html` | 改名 | `design/archive/prototype-2026-10-22/components.html` |
| docs/README.md:90 | `design/prototype/index.html` | 改名 | `design/archive/prototype-2026-10-22/index.html` |
| docs/README.md:91 | `design/prototype/play.html` | 改名 | `design/archive/prototype-2026-10-22/play.html` |
| docs/README.md:92 | `design/prototype/proto/mock-backend.js` | 改名 | `design/archive/prototype-2026-10-22/proto/mock-backend.js` |
| docs/README.md:93 | `design/prototype/proto/play.css` | 改名 | `design/archive/prototype-2026-10-22/proto/play.css` |
| docs/README.md:94 | `design/prototype/proto/play.js` | 改名 | `design/archive/prototype-2026-10-22/proto/play.js` |
| docs/README.md:95 | `design/prototype/proto/sheet.css` | 改名 | `design/archive/prototype-2026-10-22/proto/sheet.css` |
| docs/README.md:96 | `design/prototype/proto/shoot.py` | 改名 | `design/archive/prototype-2026-10-22/proto/shoot.py` |

## 有意（13 条）

| 路径引用 | 理由 | 出处 |
|---|---|---|
| `design/evidence/<YYYY-MM-DD>/` | 占位符 \<…> | AGENTS.md:216（共 1 处） |
| `local/_site_build.py` | 构建时生成、不入库的文件 | design/decisions/013-distribution-and-privacy.md:171（共 1 处） |
| `local/config.json` | gitignore:4 运行配置，未入库、仅本机存在；与 server/config.json 同口径 | AGENTS.md:56；README.md:17；README.md:88；docs/CONFIG.md:5；docs/CONFIG.md:49（共 5 处） |
| `local/data` | 运行时数据文件/目录：gitignore 且禁读（AGENTS 安全边界），文档口径引用 | docs/UI_SPEC.md:289（共 1 处） |
| `local/data/` | 运行时数据文件/目录：gitignore 且禁读（AGENTS 安全边界），文档口径引用 | AGENTS.md:55；AGENTS.md:157；README.md:19；README.md:95；README.md:215；design/decisions/006-session-persistence.md:13；docs/LOGIN.md:10；docs/PRIVACY_POLICY.md:26；docs/superpowers/specs/2026-11-03-architecture-revision-design.md:125（共 9 处） |
| `local/data/**` | glob 通配示意写法；运行时数据文件/目录：gitignore 且禁读（AGENTS 安全边界），文档口径引用 | docs/UI_SPEC.md:24（共 1 处） |
| `server/**` | glob 通配示意写法 | docs/UI_SPEC.md:24（共 1 处） |
| `server/bot/data/users.json` | 运行时数据文件/目录：gitignore 且禁读（AGENTS 安全边界），文档口径引用 | docs/FEISHU_BOT.md:143（共 1 处） |
| `server/config.json` | 运行时配置文件：gitignore 且禁读（AGENTS 安全边界）；文档教用户创建它，示例 server/config.example.json 在库 | AGENTS.md:56；README.md:17；README.md:122；docs/CONFIG.md:5；docs/CONFIG.md:13；docs/FEISHU_BOT.md:39；docs/FEISHU_BOT.md:76；docs/FEISHU_BOT.md:80；docs/FEISHU_BOT.md:166；docs/FEISHU_BOT.md:260（共 10 处） |
| `server/data` | 运行时数据文件/目录：gitignore 且禁读（AGENTS 安全边界），文档口径引用 | docs/CONFIG.md:99（共 1 处） |
| `server/data/` | 运行时数据文件/目录：gitignore 且禁读（AGENTS 安全边界），文档口径引用 | AGENTS.md:55；README.md:19；README.md:215（共 3 处） |
| `server/data/state.json` | 运行时数据文件/目录：gitignore 且禁读（AGENTS 安全边界），文档口径引用 | AGENTS.md:119（共 1 处） |
| `server/data/watchlist.json` | 运行时数据文件/目录：gitignore 且禁读（AGENTS 安全边界），文档口径引用 | docs/CONFIG.md:97（共 1 处） |

## 存在（142 条）

### 按首处出处文件分组计数

计数基于下方明细表的「出处」首处文件；同一引用可出现在多篇文档，此处不计重复，合计 142。

| 首处出处文件 | 条数 |
|---|---|
| `docs/README.md` | 36 |
| `AGENTS.md` | 23 |
| `docs/ARCHITECTURE.md` | 20 |
| `docs/UI_SPEC.md` | 9 |
| `design/decisions/008-lifecycle-version-release.md` | 6 |
| `docs/superpowers/specs/2026-11-03-architecture-revision-design.md` | 6 |
| `design/decisions/010-standalone-exe-and-settings.md` | 5 |
| `design/decisions/003-retry-policy.md` | 4 |
| `design/decisions/015-signup-path-and-replies.md` | 4 |
| `README.md` | 3 |
| `design/decisions/001-product-naming.md` | 3 |
| `design/decisions/013-distribution-and-privacy.md` | 3 |
| `design/decisions/014-workbench-ui.md` | 3 |
| `design/specs/copywriting.md` | 3 |
| `design/decisions/006-session-persistence.md` | 2 |
| `design/decisions/009-replayable-product-tour.md` | 2 |
| `docs/CONFIG.md` | 2 |
| `docs/LOGIN.md` | 2 |
| `docs/PHONE_ACCESS.md` | 2 |
| `design/decisions/002-signup-modes.md` | 1 |
| `design/decisions/004-multi-activity-and-conflict.md` | 1 |
| `design/decisions/007-runtime-timeline.md` | 1 |
| `design/decisions/011-unified-help-and-manual-update.md` | 1 |

### 全量明细（素材逐字搬运）

| 路径引用 | 判定 | 出处（首处；共 N 处） |
|---|---|---|
| `contracts/` | 存在 | AGENTS.md:15（共 1 处） |
| `contracts/school-api/` | 存在 | AGENTS.md:129（共 1 处） |
| `design/` | 存在 | AGENTS.md:17（共 3 处） |
| `design/archive/current-ui-2026-10-25/README.md` | 存在 | docs/README.md:84（共 1 处） |
| `design/archive/prototype-2026-10-22/` | 存在 | design/decisions/001-product-naming.md:15（共 3 处） |
| `design/archive/prototype-2026-10-22/app.html` | 存在 | docs/README.md:85（共 1 处） |
| `design/archive/prototype-2026-10-22/app/app.css` | 存在 | docs/README.md:86（共 1 处） |
| `design/archive/prototype-2026-10-22/app/app.js` | 存在 | docs/README.md:87（共 1 处） |
| `design/archive/prototype-2026-10-22/app/led.js` | 存在 | docs/README.md:88（共 1 处） |
| `design/archive/prototype-2026-10-22/components.html` | 存在 | docs/README.md:89（共 1 处） |
| `design/archive/prototype-2026-10-22/index.html` | 存在 | docs/README.md:90（共 1 处） |
| `design/archive/prototype-2026-10-22/play.html` | 存在 | docs/README.md:91（共 1 处） |
| `design/archive/prototype-2026-10-22/proto/mock-backend.js` | 存在 | docs/README.md:92（共 1 处） |
| `design/archive/prototype-2026-10-22/proto/play.css` | 存在 | docs/README.md:93（共 1 处） |
| `design/archive/prototype-2026-10-22/proto/play.js` | 存在 | docs/README.md:94（共 1 处） |
| `design/archive/prototype-2026-10-22/proto/sheet.css` | 存在 | docs/README.md:95（共 1 处） |
| `design/archive/prototype-2026-10-22/proto/shoot.py` | 存在 | docs/README.md:96（共 1 处） |
| `design/brand/` | 存在 | docs/UI_SPEC.md:830（共 1 处） |
| `design/decisions/` | 存在 | AGENTS.md:68（共 3 处） |
| `design/decisions/README.md` | 存在 | AGENTS.md:17（共 3 处） |
| `design/evidence/` | 存在 | docs/PHONE_ACCESS.md:16（共 3 处） |
| `design/evidence/2026-10-31/ACCEPTANCE-20261031.md` | 存在 | docs/README.md:82（共 1 处） |
| `design/evidence/2026-10-31/UI-SPEC9-AND-D-STATUS-20261031.md` | 存在 | docs/README.md:83（共 1 处） |
| `design/evidence/2026-10-31/phone-access-channel-redesign-acceptance.md` | 存在 | docs/PHONE_ACCESS.md:188（共 1 处） |
| `design/evidence/2026-11-02/live-check.md` | 存在 | design/decisions/013-distribution-and-privacy.md:177（共 2 处） |
| `design/prototype/workbench-2026-11/` | 存在 | AGENTS.md:72（共 2 处） |
| `design/specs/` | 存在 | AGENTS.md:227（共 1 处） |
| `design/specs/assistance-panels.md` | 存在 | design/decisions/010-standalone-exe-and-settings.md:136（共 3 处） |
| `design/specs/copywriting.md` | 存在 | docs/UI_SPEC.md:636（共 2 处） |
| `design/specs/terms-consent.md` | 存在 | design/specs/copywriting.md:515（共 6 处） |
| `docs/` | 存在 | AGENTS.md:16（共 4 处） |
| `docs/ARCHITECTURE.md` | 存在 | AGENTS.md:130（共 4 处） |
| `docs/FEISHU_BOT.md` | 存在 | docs/CONFIG.md:121（共 1 处） |
| `docs/LOGIN.md` | 存在 | design/decisions/008-lifecycle-version-release.md:124（共 1 处） |
| `docs/OPERATIONS.md` | 存在 | AGENTS.md:179（共 2 处） |
| `docs/PRIVACY_POLICY.md` | 存在 | design/decisions/013-distribution-and-privacy.md:95（共 3 处） |
| `docs/RETRY_POLICY_GUIDE.md` | 存在 | design/decisions/003-retry-policy.md:49（共 5 处） |
| `docs/UI_SPEC.md` | 存在 | design/decisions/001-product-naming.md:41（共 24 处） |
| `docs/USER_AGREEMENT.md` | 存在 | design/decisions/013-distribution-and-privacy.md:95（共 7 处） |
| `docs/archive/UI_DESIGN.md` | 存在 | docs/README.md:81（共 1 处） |
| `docs/archive/process/2026-10-30/discuss/2026-10-30-phone-access-channel.md` | 存在 | docs/README.md:70（共 1 处） |
| `docs/archive/process/2026-10-30/plans/2026-10-30-phone-access-channel.md` | 存在 | docs/README.md:75（共 1 处） |
| `docs/archive/process/2026-10-30/plans/2026-10-30-phone-ui-failure-repair.md` | 存在 | docs/README.md:76（共 1 处） |
| `docs/archive/process/2026-10-31/findings/2026-10-31-ui-findings.md` | 存在 | docs/README.md:71（共 1 处） |
| `docs/archive/process/2026-10-31/handoff/2026-10-31-codex-handoff-group2.md` | 存在 | docs/README.md:72（共 1 处） |
| `docs/archive/process/2026-10-31/handoff/2026-10-31-mobile-ui-handoff.md` | 存在 | docs/README.md:73（共 1 处） |
| `docs/archive/process/2026-10-31/handoff/2026-10-31-phone-access-handoff.md` | 存在 | docs/README.md:74（共 1 处） |
| `docs/archive/process/2026-10-31/plans/2026-10-31-phone-access-channel-redesign.md` | 存在 | docs/README.md:77（共 1 处） |
| `docs/archive/process/2026-10-31/plans/2026-10-31-phone-access-repair-followup.md` | 存在 | docs/README.md:78（共 1 处） |
| `docs/archive/process/2026-10-31/plans/2026-10-31-phone-access-repair.md` | 存在 | docs/README.md:79（共 1 处） |
| `docs/archive/process/2026-10-31/plans/2026-10-31-phone-control-release-publication-repair.md` | 存在 | docs/README.md:80（共 1 处） |
| `docs/superpowers/specs/2026-11-03-architecture-revision-design.md` | 存在 | design/decisions/015-signup-path-and-replies.md:55（共 2 处） |
| `local/` | 存在 | AGENTS.md:13（共 6 处） |
| `local/README.md` | 存在 | design/decisions/006-session-persistence.md:54（共 3 处） |
| `local/app.py` | 存在 | AGENTS.md:134（共 21 处） |
| `local/app.py:102` | 存在（引用含行号） | docs/superpowers/specs/2026-11-03-architecture-revision-design.md:135（共 1 处） |
| `local/app.py:198` | 存在（引用含行号） | docs/superpowers/specs/2026-11-03-architecture-revision-design.md:168（共 1 处） |
| `local/app.py:3067` | 存在（引用含行号） | docs/superpowers/specs/2026-11-03-architecture-revision-design.md:218（共 1 处） |
| `local/build/build_advanced.py` | 存在 | docs/README.md:58（共 1 处） |
| `local/build/build_exe.py` | 存在 | design/decisions/008-lifecycle-version-release.md:79（共 4 处） |
| `local/build/build_installer.py` | 存在 | README.md:66（共 2 处） |
| `local/build/make_portable.py` | 存在 | design/decisions/008-lifecycle-version-release.md:80（共 2 处） |
| `local/business_clock.py` | 存在 | docs/UI_SPEC.md:943（共 3 处） |
| `local/config.example.json` | 存在 | README.md:88（共 1 处） |
| `local/domain/log_events.py` | 存在 | design/decisions/015-signup-path-and-replies.md:65（共 1 处） |
| `local/domain/signup_reply.py` | 存在 | design/decisions/015-signup-path-and-replies.md:58（共 4 处） |
| `local/grab.py` | 存在 | design/decisions/003-retry-policy.md:48（共 8 处） |
| `local/grab.py:2144` | 存在（引用含行号） | docs/superpowers/specs/2026-11-03-architecture-revision-design.md:263（共 1 处） |
| `local/grab.py:906` | 存在（引用含行号） | docs/superpowers/specs/2026-11-03-architecture-revision-design.md:135（共 1 处） |
| `local/gui.py:40` | 存在（引用含行号） | docs/superpowers/specs/2026-11-03-architecture-revision-design.md:135（共 1 处） |
| `local/installer/ChineseSimplified.isl` | 存在 | design/decisions/008-lifecycle-version-release.md:177（共 1 处） |
| `local/launchers/` | 存在 | README.md:93（共 1 处） |
| `local/launchers/1-登录.bat` | 存在 | docs/README.md:62（共 1 处） |
| `local/launchers/2-抢活动.bat` | 存在 | docs/README.md:63（共 1 处） |
| `local/launchers/3-检查登录和活动.bat` | 存在 | docs/README.md:64（共 1 处） |
| `local/launchers/4-图形界面.bat` | 存在 | docs/README.md:65（共 1 处） |
| `local/launchers/_py.bat` | 存在 | docs/README.md:66（共 1 处） |
| `local/launchers/install.bat` | 存在 | docs/README.md:67（共 1 处） |
| `local/launchers/启动不了点我.txt` | 存在 | docs/README.md:68（共 1 处） |
| `local/launchers/遇到问题先看我.txt` | 存在 | docs/README.md:69（共 1 处） |
| `local/requirements.txt` | 存在 | docs/UI_SPEC.md:23（共 1 处） |
| `local/signup_plan.py` | 存在 | design/decisions/004-multi-activity-and-conflict.md:55（共 3 处） |
| `local/signup_signing.py` | 存在 | design/decisions/015-signup-path-and-replies.md:61（共 2 处） |
| `local/tests/fixtures/api_threads.py` | 存在 | AGENTS.md:111（共 1 处） |
| `local/tests/fixtures/runtime_bridge.js` | 存在 | docs/UI_SPEC.md:544（共 1 处） |
| `local/tests/test_installer_script.py` | 存在 | design/decisions/008-lifecycle-version-release.md:178（共 1 处） |
| `local/tests/test_lifecycle_release.py` | 存在 | design/decisions/008-lifecycle-version-release.md:81（共 3 处） |
| `local/tests/test_retry_policy.py` | 存在 | design/decisions/003-retry-policy.md:49（共 1 处） |
| `local/tests/test_runtime_bundle.py` | 存在 | design/decisions/010-standalone-exe-and-settings.md:109（共 1 处） |
| `local/tests/test_session_persistence.py` | 存在 | design/decisions/006-session-persistence.md:54（共 2 处） |
| `local/tests/test_signup_plan.py` | 存在 | design/decisions/002-signup-modes.md:46（共 1 处） |
| `local/tests/test_ui_contract.py` | 存在 | design/decisions/001-product-naming.md:33（共 8 处） |
| `local/tests/test_worker_boundaries.py` | 存在 | design/decisions/003-retry-policy.md:54（共 1 处） |
| `local/time_contract.py` | 存在 | docs/UI_SPEC.md:928（共 1 处） |
| `local/ui` | 存在 | docs/UI_SPEC.md:543（共 2 处） |
| `local/ui/` | 存在 | design/decisions/014-workbench-ui.md:69（共 3 处） |
| `local/ui/app.js` | 存在 | design/decisions/007-runtime-timeline.md:73（共 17 处） |
| `local/ui/brand/` | 存在 | design/decisions/014-workbench-ui.md:74（共 1 处） |
| `local/ui/brand/app.ico` | 存在 | docs/UI_SPEC.md:829（共 1 处） |
| `local/ui/index.html` | 存在 | AGENTS.md:165（共 8 处） |
| `local/ui/m/` | 存在 | AGENTS.md:166（共 1 处） |
| `local/ui/m/styles.css` | 存在 | design/decisions/014-workbench-ui.md:69（共 1 处） |
| `local/ui/state/store.js` | 存在 | design/decisions/009-replayable-product-tour.md:35（共 2 处） |
| `local/ui/styles.css` | 存在 | design/decisions/009-replayable-product-tour.md:48（共 3 处） |
| `local/ui/views/help.js` | 存在 | design/decisions/010-standalone-exe-and-settings.md:135（共 3 处） |
| `local/ui/views/phone.js` | 存在 | design/specs/copywriting.md:390（共 1 处） |
| `local/ui/views/plan-panel.js` | 存在 | docs/UI_SPEC.md:635（共 1 处） |
| `local/ui/views/settings.js` | 存在 | design/decisions/010-standalone-exe-and-settings.md:135（共 4 处） |
| `local/ui/views/update.js` | 存在 | design/decisions/010-standalone-exe-and-settings.md:135（共 2 处） |
| `local/update_check.py` | 存在 | design/decisions/011-unified-help-and-manual-update.md:64（共 1 处） |
| `server/` | 存在 | AGENTS.md:14（共 6 处） |
| `server/bot/bot.js` | 存在 | AGENTS.md:176（共 2 处） |
| `server/config.example.json` | 存在 | docs/CONFIG.md:15（共 1 处） |
| `server/deploy/` | 存在 | AGENTS.md:179（共 1 处） |
| `server/deploy/auto_login.py` | 存在 | docs/ARCHITECTURE.md:79（共 2 处） |
| `server/deploy/grab_signup.py` | 存在 | docs/ARCHITECTURE.md:80（共 2 处） |
| `server/deploy/server_refresh.js` | 存在 | docs/ARCHITECTURE.md:78（共 1 处） |
| `server/deploy/server_refresh.js --daemon` | 存在（引用含命令参数： --daemon） | docs/LOGIN.md:72（共 1 处） |
| `server/deploy/set_credentials.py` | 存在 | docs/ARCHITECTURE.md:81（共 1 处） |
| `server/scripts/` | 存在 | AGENTS.md:170（共 1 处） |
| `server/scripts/activity_watch.py` | 存在 | docs/ARCHITECTURE.md:64（共 1 处） |
| `server/scripts/card.py` | 存在 | docs/ARCHITECTURE.md:68（共 1 处） |
| `server/scripts/common.py` | 存在 | docs/ARCHITECTURE.md:62（共 1 处） |
| `server/scripts/dev/` | 存在 | docs/LOGIN.md:130（共 1 处） |
| `server/scripts/fetch.py` | 存在 | docs/ARCHITECTURE.md:63（共 1 处） |
| `server/scripts/grab_card.py` | 存在 | docs/ARCHITECTURE.md:74（共 1 处） |
| `server/scripts/net_probe.py` | 存在 | docs/ARCHITECTURE.md:73（共 1 处） |
| `server/scripts/notify.py` | 存在 | docs/ARCHITECTURE.md:70（共 1 处） |
| `server/scripts/remind.py` | 存在 | docs/ARCHITECTURE.md:67（共 1 处） |
| `server/scripts/render.py` | 存在 | docs/ARCHITECTURE.md:69（共 1 处） |
| `server/scripts/run.py` | 存在 | docs/ARCHITECTURE.md:65（共 1 处） |
| `server/scripts/scan.py` | 存在 | docs/ARCHITECTURE.md:66（共 1 处） |
| `server/scripts/token_probe.py` | 存在 | docs/ARCHITECTURE.md:71（共 1 处） |
| `server/scripts/token_report.py` | 存在 | docs/ARCHITECTURE.md:72（共 1 处） |
| `server/scripts/trigger_server.py` | 存在 | docs/ARCHITECTURE.md:77（共 1 处） |
| `server/scripts/watchlist.py` | 存在 | docs/ARCHITECTURE.md:75（共 1 处） |
| `server/scripts/watchlist_runner.py` | 存在 | docs/ARCHITECTURE.md:76（共 1 处） |
| `server/tests/` | 存在 | AGENTS.md:119（共 1 处） |
| `tools/` | 存在 | AGENTS.md:18（共 1 处） |
| `tools/qa_runtime_reliability.py` | 存在 | design/specs/copywriting.md:469（共 4 处） |
| `tools/release.py` | 存在 | AGENTS.md:162（共 11 处） |
| `tools/release.py --prepare` | 存在（引用含命令参数： --prepare） | AGENTS.md:184（共 2 处） |

## 补丁判定：docs/ 下可出补丁 = 0 条

- 39 条「死链」全部是 docs/README.md:58-96 迁移对照表的旧路径列；对照表右列就是新路径，删改旧路径列会破坏对照功能。
- 对抗复核：39 条死链位置经独立扫描限于 docs/README.md:58-96（0 例外），全库无其他死链。
- 该表属记录性质文档（AGENTS.md「旧记录不追改」的精神延伸），保持现状。
- 若今后要消灭这批死链，正确做法是在对照表所在节补一句说明，而不是改路径（素材原话）。
- 按此判定不建 PATCHES 文件，本报告不派生任何文档改动。

## 修订记录（对抗审阅 2026-11-08）

- 对抗审阅结论见同目录 `ADVERSARIAL-L6.md`：实质判定 194 条，站得住 193、部分站不住 1（即下条）、推翻 0，红牌 0。机械核验（原分析者只做机械项，实质判定由前端开发者独立承担）对计数、逐字、存在性全部复算通过。
- `local/config.json` 判定「存在」→「有意（gitignore:4 运行配置，未入库、仅本机存在；与 server/config.json 同口径）」，从存在表移入有意表。统计前值：存在 143、有意 12、死链 39、合计 194；后值：存在 142、有意 13、死链 39、合计 194 不变；存在分组计数 AGENTS.md 24→23，其余 22 组不变；删除建议 0、NEEDS-HUMAN 0 不变。
- 对抗复核同时确认：39 对改名经 git 史复核（27 对 blob 完全一致精确搬移、12 对搬移同时改写文内自指路径）39/39 成立；原 12 条有意理由反证 12/12 成立；39 条死链位置限于 docs/README.md:58-96（0 例外），全库无其他死链。
