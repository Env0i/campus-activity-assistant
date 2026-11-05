# STANDARDIZATION — 全量标准化台账(469 文件对齐 reports/STANDARD.md 八节)

生成:reports/_tools/std_ledger_gen.py(规则化默认 + 批1-8 扫描裁决覆盖)。判定口径:
**合规**=判据命令 0 命中或裁决通过;**已改**=本轮改动(std-N patch,判据红→绿+反向对照);**保留**=不动的明确理由;**N/A**=判据不适用(资产/数据/样式)。

## 判定统计

| 判定 | 文件数 |
|---|---|
| 合规 | 147 |
| 已改 | 53 |
| 保留 | 120 |
| N/A | 149 |

## 修复批次索引(patch series,均未 commit)

| patch | 批 | 内容 |
|---|---|---|
| std-1-domain.patch | 1 | login_rules.py:91 窄化 except |
| std-2-application.patch | 2 | advanced_component_service _note + 6 处注释 |
| std-3-infrastructure.patch | 3 | lifecycle_store :263/:140 留痕 |
| std-4a-ui.patch | 4a | relogin.js:74 addLog + terms/app 注释 |
| std-4b-ui.patch | 4b | controllers plan/update 注释 |
| std-5-tests.patch | 5 | 两处 docstring <tmp> 口径 |
| std-6-server.patch | 6 | sync_token.sh 参数化 + server 测试注释 |
| std-7-tools.patch | 7 | tools 三文件(窄化/注释/docstring) |
| std-9a-app.patch | 9a(根级补充) | app.py 13 处吞异常注释 |
| std-9b-grab.patch | 9b(根级补充) | grab/business_clock/signup_transport 11 处注释 |
| std-8a-docs.patch | 8a | README 版本口径(77/256/79) + versioning:11-12 |
| std-8b-docs.patch | 8b | copywriting + assistance-panels + UI_SPEC(:352/六步/§9 旧口径) |
| std-8c-docs.patch | 8c | design/README + specs/README + ARCHITECTURE 54 |
| std-8d-docs.patch | 8d | terms-consent 五步 + CHANGELOG r4 记录 |
| std-10-infra-comments.patch | 10 | process_tree/tray_icon/tunnel_manager 12 处裁决注释 |
| std-11-autologin-comments.patch | 11 | auto_login.py 7 处(含计划外 :679) |
| std-12-server-comments.patch | 12 | grab_signup/login/notify 4 处 |
| std-13-server-js-comments.patch | 13 | server_refresh.js + bot.js:114 策略分歧注释(C9) |
| std-15a-wording.patch | 15a | app.py 3 处措辞修正(质检员文本) |
| std-15b-wording.patch | 15b | business_clock/lifecycle_store/advanced_component_service 措辞 |
| std-16-armedat.patch | 16 | armedAt 死键 5 处删除(3 文件) |
| std-17-docs-p3.patch | 17 | docs 三文件词汇对齐(抢报名/绿色版) |
| std-18a/18b/18c-rename.patch | 18 | TestWallClock→WallClockStub(8 文件 65 处,计数守恒) |
| std-19-splitbranches-redact.patch | 19 | split_branches 失败输出 URL 凭证脱敏 |

## 逐文件清单(469 行)

| 路径 | 判定 | 判据节 | 理由 | 证据 |
|---|---|---|---|---|
| .gitattributes | 合规 | §6 | ignore 覆盖核对通过 | 轮1 密钥治理 |
| .gitignore | 合规 | §6 | ignore 覆盖核对通过 | 轮1 密钥治理 |
| AGENTS.md | 合规 | §8 | 本轮判据来源之一,干净 | 批8 |
| CHANGELOG.md | 已改 | §8 | 1.2.0 待发布段补 r4 记录(std-8d);已发布段不追改 | std-8d-docs.patch;批8 #29 |
| CLAUDE.md | 合规 | §8 | 干净 | 批8 |
| LICENSE | N/A | 全部 | 随包许可证 | 轮1 |
| README.md | 已改 | §8 | :77/:256 版本口径+ :79 六步措辞对齐 VERSION(std-8a,F-29 闭环) | std-8a-docs.patch;批8 P1-1/2 |
| VERSION | 合规 | §8 | 版本唯一真源 | 批8 J8.2 |
| contracts/school-api/README.md | 合规 | §5/§8 | 契约 README:脱敏说明与样例分工,无版本硬写 | 批8 范围外自查;轮1 B3 |
| contracts/school-api/get-info.data.json | N/A | 全部 | 契约样例数据(脱敏已核) | 轮1 密钥治理/L4-B3 |
| contracts/school-api/get-join-info.json | N/A | 全部 | 契约样例数据(脱敏已核) | 轮1 密钥治理/L4-B3 |
| contracts/school-api/list-activity.items.json | N/A | 全部 | 契约样例数据(脱敏已核) | 轮1 密钥治理/L4-B3 |
| contracts/school-api/list-activity.raw-item.json | N/A | 全部 | 契约样例数据(脱敏已核) | 轮1 密钥治理/L4-B3 |
| contracts/school-api/signup-replies.json | N/A | 全部 | 契约样例数据(脱敏已核) | 轮1 密钥治理/L4-B3 |
| design/README.md | 已改 | §8 | :52 版本态+:71 五步状态注记(std-8c) | std-8c-docs.patch;批8 #20/21 |
| design/archive/README.md | 保留 | §8 | 归档历史记录,J8.3 不追改;轮1 范围外 | 轮1 COVERAGE |
| design/archive/current-ui-2026-10-25/README.md | 保留 | §8 | 归档历史记录,J8.3 不追改;轮1 范围外 | 轮1 COVERAGE |
| design/archive/prototype-2026-10-22/app.html | 保留 | §8 | 归档历史记录,J8.3 不追改;轮1 范围外 | 轮1 COVERAGE |
| design/archive/prototype-2026-10-22/app/app.css | 保留 | §8 | 归档历史记录,J8.3 不追改;轮1 范围外 | 轮1 COVERAGE |
| design/archive/prototype-2026-10-22/app/app.js | 保留 | §8 | 归档历史记录,J8.3 不追改;轮1 范围外 | 轮1 COVERAGE |
| design/archive/prototype-2026-10-22/app/led.js | 保留 | §8 | 归档历史记录,J8.3 不追改;轮1 范围外 | 轮1 COVERAGE |
| design/archive/prototype-2026-10-22/components.html | 保留 | §8 | 归档历史记录,J8.3 不追改;轮1 范围外 | 轮1 COVERAGE |
| design/archive/prototype-2026-10-22/index.html | 保留 | §8 | 归档历史记录,J8.3 不追改;轮1 范围外 | 轮1 COVERAGE |
| design/archive/prototype-2026-10-22/play.html | 保留 | §8 | 归档历史记录,J8.3 不追改;轮1 范围外 | 轮1 COVERAGE |
| design/archive/prototype-2026-10-22/proto/mock-backend.js | 保留 | §8 | 归档历史记录,J8.3 不追改;轮1 范围外 | 轮1 COVERAGE |
| design/archive/prototype-2026-10-22/proto/play.css | 保留 | §8 | 归档历史记录,J8.3 不追改;轮1 范围外 | 轮1 COVERAGE |
| design/archive/prototype-2026-10-22/proto/play.js | 保留 | §8 | 归档历史记录,J8.3 不追改;轮1 范围外 | 轮1 COVERAGE |
| design/archive/prototype-2026-10-22/proto/sheet.css | 保留 | §8 | 归档历史记录,J8.3 不追改;轮1 范围外 | 轮1 COVERAGE |
| design/archive/prototype-2026-10-22/proto/shoot.py | 保留 | §8 | 归档历史记录,J8.3 不追改;轮1 范围外 | 轮1 COVERAGE |
| design/brand/README.md | 保留 | 全部 | 品牌 JS(2 个 152 行),范围外;静态扫描留档 | 轮1 COVERAGE |
| design/brand/ico/app.ico | N/A | 全部 | 品牌图像资产 | 批4 同类裁决 |
| design/brand/ico/favicon.ico | N/A | 全部 | 品牌图像资产 | 批4 同类裁决 |
| design/brand/png/apple-touch-icon.png | N/A | 全部 | 品牌图像资产 | 批4 同类裁决 |
| design/brand/png/lockup-dark.png | N/A | 全部 | 品牌图像资产 | 批4 同类裁决 |
| design/brand/png/lockup-dark@2x.png | N/A | 全部 | 品牌图像资产 | 批4 同类裁决 |
| design/brand/png/lockup.png | N/A | 全部 | 品牌图像资产 | 批4 同类裁决 |
| design/brand/png/lockup@2x.png | N/A | 全部 | 品牌图像资产 | 批4 同类裁决 |
| design/brand/png/logo-1024.png | N/A | 全部 | 品牌图像资产 | 批4 同类裁决 |
| design/brand/png/logo-128.png | N/A | 全部 | 品牌图像资产 | 批4 同类裁决 |
| design/brand/png/logo-16.png | N/A | 全部 | 品牌图像资产 | 批4 同类裁决 |
| design/brand/png/logo-20.png | N/A | 全部 | 品牌图像资产 | 批4 同类裁决 |
| design/brand/png/logo-24.png | N/A | 全部 | 品牌图像资产 | 批4 同类裁决 |
| design/brand/png/logo-256.png | N/A | 全部 | 品牌图像资产 | 批4 同类裁决 |
| design/brand/png/logo-32.png | N/A | 全部 | 品牌图像资产 | 批4 同类裁决 |
| design/brand/png/logo-40.png | N/A | 全部 | 品牌图像资产 | 批4 同类裁决 |
| design/brand/png/logo-48.png | N/A | 全部 | 品牌图像资产 | 批4 同类裁决 |
| design/brand/png/logo-512.png | N/A | 全部 | 品牌图像资产 | 批4 同类裁决 |
| design/brand/png/logo-64.png | N/A | 全部 | 品牌图像资产 | 批4 同类裁决 |
| design/brand/png/maskable-512.png | N/A | 全部 | 品牌图像资产 | 批4 同类裁决 |
| design/brand/png/tile-192.png | N/A | 全部 | 品牌图像资产 | 批4 同类裁决 |
| design/brand/png/tile-512.png | N/A | 全部 | 品牌图像资产 | 批4 同类裁决 |
| design/brand/preview.png | N/A | 全部 | 品牌图像资产 | 批4 同类裁决 |
| design/brand/svg/lockup-dark.svg | N/A | 全部 | 品牌图像资产 | 批4 同类裁决 |
| design/brand/svg/lockup.svg | N/A | 全部 | 品牌图像资产 | 批4 同类裁决 |
| design/brand/svg/logo-mono-white.svg | N/A | 全部 | 品牌图像资产 | 批4 同类裁决 |
| design/brand/svg/logo-mono.svg | N/A | 全部 | 品牌图像资产 | 批4 同类裁决 |
| design/brand/svg/logo-small.svg | N/A | 全部 | 品牌图像资产 | 批4 同类裁决 |
| design/brand/svg/logo-tile-square.svg | N/A | 全部 | 品牌图像资产 | 批4 同类裁决 |
| design/brand/svg/logo-tile.svg | N/A | 全部 | 品牌图像资产 | 批4 同类裁决 |
| design/brand/svg/logo.svg | N/A | 全部 | 品牌图像资产 | 批4 同类裁决 |
| design/brand/tools/export.js | 保留 | 全部 | 品牌 JS(2 个 152 行),范围外;静态扫描留档 | 轮1 COVERAGE |
| design/brand/tools/pngkit.js | 保留 | 全部 | 品牌 JS(2 个 152 行),范围外;静态扫描留档 | 轮1 COVERAGE |
| design/check_refs.py | 保留 | 全部 | 引用校验工具,范围外;静态扫描留档 | 轮1 COVERAGE |
| design/decisions/001-product-naming.md | 保留 | §8 | 决策记录,J8.3 不追改(009 六步注记与代码矛盾,留决策流程改状态) | 批8 只登记清单 |
| design/decisions/002-signup-modes.md | 保留 | §8 | 决策记录,J8.3 不追改(009 六步注记与代码矛盾,留决策流程改状态) | 批8 只登记清单 |
| design/decisions/003-retry-policy.md | 保留 | §8 | 决策记录,J8.3 不追改(009 六步注记与代码矛盾,留决策流程改状态) | 批8 只登记清单 |
| design/decisions/004-multi-activity-and-conflict.md | 保留 | §8 | 决策记录,J8.3 不追改(009 六步注记与代码矛盾,留决策流程改状态) | 批8 只登记清单 |
| design/decisions/005-attendance-filters.md | 保留 | §8 | 决策记录,J8.3 不追改(009 六步注记与代码矛盾,留决策流程改状态) | 批8 只登记清单 |
| design/decisions/006-session-persistence.md | 保留 | §8 | 决策记录,J8.3 不追改(009 六步注记与代码矛盾,留决策流程改状态) | 批8 只登记清单 |
| design/decisions/007-runtime-timeline.md | 保留 | §8 | 决策记录,J8.3 不追改(009 六步注记与代码矛盾,留决策流程改状态) | 批8 只登记清单 |
| design/decisions/008-lifecycle-version-release.md | 保留 | §8 | 决策记录,J8.3 不追改(009 六步注记与代码矛盾,留决策流程改状态) | 批8 只登记清单 |
| design/decisions/009-replayable-product-tour.md | 保留 | §8 | 决策记录,J8.3 不追改(009 六步注记与代码矛盾,留决策流程改状态) | 批8 只登记清单 |
| design/decisions/010-standalone-exe-and-settings.md | 保留 | §8 | 决策记录,J8.3 不追改(009 六步注记与代码矛盾,留决策流程改状态) | 批8 只登记清单 |
| design/decisions/011-unified-help-and-manual-update.md | 保留 | §8 | 决策记录,J8.3 不追改(009 六步注记与代码矛盾,留决策流程改状态) | 批8 只登记清单 |
| design/decisions/012-independent-beijing-clock.md | 保留 | §8 | 决策记录,J8.3 不追改(009 六步注记与代码矛盾,留决策流程改状态) | 批8 只登记清单 |
| design/decisions/013-distribution-and-privacy.md | 保留 | §8 | 决策记录,J8.3 不追改(009 六步注记与代码矛盾,留决策流程改状态) | 批8 只登记清单 |
| design/decisions/014-workbench-ui.md | 保留 | §8 | 决策记录,J8.3 不追改(009 六步注记与代码矛盾,留决策流程改状态) | 批8 只登记清单 |
| design/decisions/015-signup-path-and-replies.md | 保留 | §8 | 决策记录,J8.3 不追改(009 六步注记与代码矛盾,留决策流程改状态) | 批8 只登记清单 |
| design/decisions/README.md | 保留 | §8 | 决策记录,J8.3 不追改(009 六步注记与代码矛盾,留决策流程改状态) | 批8 只登记清单 |
| design/evidence/2026-10-30/README.md | 保留 | §8 | 过程记录,J8.3 不追改 | 批8;轮1 |
| design/evidence/2026-10-30/UI-ACCEPTANCE.md | 保留 | §8 | 过程记录,J8.3 不追改 | 批8;轮1 |
| design/evidence/2026-10-30/phone-access-acceptance.md | 保留 | §8 | 过程记录,J8.3 不追改 | 批8;轮1 |
| design/evidence/2026-10-30/tailscale-probe.md | 保留 | §8 | 过程记录,J8.3 不追改 | 批8;轮1 |
| design/evidence/2026-10-30/本机版核心操作流程-交互说明.md | 保留 | §8 | 过程记录,J8.3 不追改 | 批8;轮1 |
| design/evidence/2026-10-31/ACCEPTANCE-20261031.md | 保留 | §8 | 过程记录,J8.3 不追改 | 批8;轮1 |
| design/evidence/2026-10-31/UI-SPEC9-AND-D-STATUS-20261031.md | 保留 | §8 | 过程记录,J8.3 不追改 | 批8;轮1 |
| design/evidence/2026-10-31/mobile-ui-polling-repair.md | 保留 | §8 | 过程记录,J8.3 不追改 | 批8;轮1 |
| design/evidence/2026-10-31/mobile-ui-real-device-acceptance.md | 保留 | §8 | 过程记录,J8.3 不追改 | 批8;轮1 |
| design/evidence/2026-10-31/phone-access-channel-redesign-acceptance.md | 保留 | §8 | 过程记录,J8.3 不追改 | 批8;轮1 |
| design/evidence/2026-10-31/phone-access-repair-acceptance.md | 保留 | §8 | 过程记录,J8.3 不追改 | 批8;轮1 |
| design/evidence/2026-11-02/.gitignore | 保留 | §8 | 过程记录,J8.3 不追改 | 批8;轮1 |
| design/evidence/2026-11-02/README.md | 保留 | §8 | 过程记录,J8.3 不追改 | 批8;轮1 |
| design/evidence/2026-11-02/doc-consistency-check.md | 保留 | §8 | 过程记录,J8.3 不追改 | 批8;轮1 |
| design/evidence/2026-11-02/live-check.md | 保留 | §8 | 过程记录,J8.3 不追改 | 批8;轮1 |
| design/evidence/2026-11-02/patches-for-capture.md | 保留 | §8 | 过程记录,J8.3 不追改 | 批8;轮1 |
| design/evidence/2026-11-02/server-and-token-check.md | 保留 | §8 | 过程记录,J8.3 不追改 | 批8;轮1 |
| design/evidence/2026-11-02/server-live-check.md | 保留 | §8 | 过程记录,J8.3 不追改 | 批8;轮1 |
| design/evidence/2026-11-02/signup-direct-log-audit.md | 保留 | §8 | 过程记录,J8.3 不追改 | 批8;轮1 |
| design/evidence/2026-11-02/signup-idle-open.txt | N/A | 全部 | 证据资产(图片/文本),判据不适用;脱敏已核 | 轮1 密钥治理 |
| design/evidence/2026-11-02/ui-01-list-demo.png | N/A | 全部 | 证据资产(图片/文本),判据不适用;脱敏已核 | 轮1 密钥治理 |
| design/evidence/2026-11-02/ui-02-plan-selected-demo.png | N/A | 全部 | 证据资产(图片/文本),判据不适用;脱敏已核 | 轮1 密钥治理 |
| design/evidence/2026-11-02/ui-03-plan-running-demo.png | N/A | 全部 | 证据资产(图片/文本),判据不适用;脱敏已核 | 轮1 密钥治理 |
| design/evidence/2026-11-02/ui-04-plan-partial-demo.png | N/A | 全部 | 证据资产(图片/文本),判据不适用;脱敏已核 | 轮1 密钥治理 |
| design/evidence/2026-11-02/ui-05-short-window-demo.png | N/A | 全部 | 证据资产(图片/文本),判据不适用;脱敏已核 | 轮1 密钥治理 |
| design/evidence/2026-11-02/ui-screenshots.md | 保留 | §8 | 过程记录,J8.3 不追改 | 批8;轮1 |
| design/evidence/2026-11-04/README.md | 保留 | §8 | 过程记录,J8.3 不追改 | 批8;轮1 |
| design/evidence/2026-11-04/a5-manual-check.md | 保留 | §8 | 过程记录,J8.3 不追改 | 批8;轮1 |
| design/evidence/2026-11-04/decision-agenda.md | 保留 | §8 | 过程记录,J8.3 不追改 | 批8;轮1 |
| design/evidence/2026-11-04/prototype-gap.md | 保留 | §8 | 过程记录,J8.3 不追改 | 批8;轮1 |
| design/evidence/2026-11-04/prototype-missing-states.md | 保留 | §8 | 过程记录,J8.3 不追改 | 批8;轮1 |
| design/evidence/2026-11-04/school-frontend-analysis.md | 保留 | §8 | 过程记录,J8.3 不追改 | 批8;轮1 |
| design/flows/README.md | 合规 | §8 | 批8 抽查未列违规;索引层短文档 | 批8 |
| design/flows/activity-selection-and-plan.md | 合规 | §8 | 批8 抽查未列违规;索引层短文档 | 批8 |
| design/flows/first-use-and-login.md | 合规 | §8 | 批8 抽查未列违规;索引层短文档 | 批8 |
| design/flows/mixed-plan-runtime.md | 合规 | §8 | 批8 抽查未列违规;索引层短文档 | 批8 |
| design/flows/stop-and-result.md | 合规 | §8 | 批8 抽查未列违规;索引层短文档 | 批8 |
| design/proposals/README.md | 合规 | §8 | 批8 抽查未列违规;索引层短文档 | 批8 |
| design/proposals/replayable-product-tour.md | 合规 | §8 | 批8 抽查未列违规;索引层短文档 | 批8 |
| design/prototype/workbench-2026-11/.gitignore | N/A | 全部 | 原型基准物(workbench-2026-11 硬基准),八节判据不适用;轮1 静态扫描留档 | 轮1 static_scan |
| design/prototype/workbench-2026-11/Attention.dc.html | N/A | 全部 | 原型基准物(workbench-2026-11 硬基准),八节判据不适用;轮1 静态扫描留档 | 轮1 static_scan |
| design/prototype/workbench-2026-11/Broken.dc.html | N/A | 全部 | 原型基准物(workbench-2026-11 硬基准),八节判据不适用;轮1 静态扫描留档 | 轮1 static_scan |
| design/prototype/workbench-2026-11/ClockHold.dc.html | N/A | 全部 | 原型基准物(workbench-2026-11 硬基准),八节判据不适用;轮1 静态扫描留档 | 轮1 static_scan |
| design/prototype/workbench-2026-11/CloseAsk.dc.html | N/A | 全部 | 原型基准物(workbench-2026-11 硬基准),八节判据不适用;轮1 静态扫描留档 | 轮1 static_scan |
| design/prototype/workbench-2026-11/CloseConfirm.dc.html | N/A | 全部 | 原型基准物(workbench-2026-11 硬基准),八节判据不适用;轮1 静态扫描留档 | 轮1 static_scan |
| design/prototype/workbench-2026-11/CloseHidden.dc.html | N/A | 全部 | 原型基准物(workbench-2026-11 硬基准),八节判据不适用;轮1 静态扫描留档 | 轮1 static_scan |
| design/prototype/workbench-2026-11/CloseIdle.dc.html | N/A | 全部 | 原型基准物(workbench-2026-11 硬基准),八节判据不适用;轮1 静态扫描留档 | 轮1 static_scan |
| design/prototype/workbench-2026-11/CloseLive.dc.html | N/A | 全部 | 原型基准物(workbench-2026-11 硬基准),八节判据不适用;轮1 静态扫描留档 | 轮1 static_scan |
| design/prototype/workbench-2026-11/CompFail.dc.html | N/A | 全部 | 原型基准物(workbench-2026-11 硬基准),八节判据不适用;轮1 静态扫描留档 | 轮1 static_scan |
| design/prototype/workbench-2026-11/CompLive.dc.html | N/A | 全部 | 原型基准物(workbench-2026-11 硬基准),八节判据不适用;轮1 静态扫描留档 | 轮1 static_scan |
| design/prototype/workbench-2026-11/CompOk.dc.html | N/A | 全部 | 原型基准物(workbench-2026-11 硬基准),八节判据不适用;轮1 静态扫描留档 | 轮1 static_scan |
| design/prototype/workbench-2026-11/CompWrong.dc.html | N/A | 全部 | 原型基准物(workbench-2026-11 硬基准),八节判据不适用;轮1 静态扫描留档 | 轮1 static_scan |
| design/prototype/workbench-2026-11/CredForm.dc.html | N/A | 全部 | 原型基准物(workbench-2026-11 硬基准),八节判据不适用;轮1 静态扫描留档 | 轮1 static_scan |
| design/prototype/workbench-2026-11/CredSaved.dc.html | N/A | 全部 | 原型基准物(workbench-2026-11 硬基准),八节判据不适用;轮1 静态扫描留档 | 轮1 static_scan |
| design/prototype/workbench-2026-11/DesignSpec.dc.html | N/A | 全部 | 原型基准物(workbench-2026-11 硬基准),八节判据不适用;轮1 静态扫描留档 | 轮1 static_scan |
| design/prototype/workbench-2026-11/Editing.dc.html | N/A | 全部 | 原型基准物(workbench-2026-11 硬基准),八节判据不适用;轮1 静态扫描留档 | 轮1 static_scan |
| design/prototype/workbench-2026-11/FirstUse.dc.html | N/A | 全部 | 原型基准物(workbench-2026-11 硬基准),八节判据不适用;轮1 静态扫描留档 | 轮1 static_scan |
| design/prototype/workbench-2026-11/HelpKeys.dc.html | N/A | 全部 | 原型基准物(workbench-2026-11 硬基准),八节判据不适用;轮1 静态扫描留档 | 轮1 static_scan |
| design/prototype/workbench-2026-11/ImplNotes.dc.html | N/A | 全部 | 原型基准物(workbench-2026-11 硬基准),八节判据不适用;轮1 静态扫描留档 | 轮1 static_scan |
| design/prototype/workbench-2026-11/LoginShort.dc.html | N/A | 全部 | 原型基准物(workbench-2026-11 硬基准),八节判据不适用;轮1 静态扫描留档 | 轮1 static_scan |
| design/prototype/workbench-2026-11/LongName.dc.html | N/A | 全部 | 原型基准物(workbench-2026-11 硬基准),八节判据不适用;轮1 静态扫描留档 | 轮1 static_scan |
| design/prototype/workbench-2026-11/Main.dc.html | N/A | 全部 | 原型基准物(workbench-2026-11 硬基准),八节判据不适用;轮1 静态扫描留档 | 轮1 static_scan |
| design/prototype/workbench-2026-11/Medium.dc.html | N/A | 全部 | 原型基准物(workbench-2026-11 硬基准),八节判据不适用;轮1 静态扫描留档 | 轮1 static_scan |
| design/prototype/workbench-2026-11/MediumRun.dc.html | N/A | 全部 | 原型基准物(workbench-2026-11 硬基准),八节判据不适用;轮1 静态扫描留档 | 轮1 static_scan |
| design/prototype/workbench-2026-11/Narrow.dc.html | N/A | 全部 | 原型基准物(workbench-2026-11 硬基准),八节判据不适用;轮1 静态扫描留档 | 轮1 static_scan |
| design/prototype/workbench-2026-11/NarrowPop.dc.html | N/A | 全部 | 原型基准物(workbench-2026-11 硬基准),八节判据不适用;轮1 静态扫描留档 | 轮1 static_scan |
| design/prototype/workbench-2026-11/NarrowWarn.dc.html | N/A | 全部 | 原型基准物(workbench-2026-11 硬基准),八节判据不适用;轮1 静态扫描留档 | 轮1 static_scan |
| design/prototype/workbench-2026-11/NetOff.dc.html | N/A | 全部 | 原型基准物(workbench-2026-11 硬基准),八节判据不适用;轮1 静态扫描留档 | 轮1 static_scan |
| design/prototype/workbench-2026-11/Phone.dc.html | N/A | 全部 | 原型基准物(workbench-2026-11 硬基准),八节判据不适用;轮1 静态扫描留档 | 轮1 static_scan |
| design/prototype/workbench-2026-11/PhoneApp.dc.html | N/A | 全部 | 原型基准物(workbench-2026-11 硬基准),八节判据不适用;轮1 静态扫描留档 | 轮1 static_scan |
| design/prototype/workbench-2026-11/PhoneAuto.dc.html | N/A | 全部 | 原型基准物(workbench-2026-11 硬基准),八节判据不适用;轮1 静态扫描留档 | 轮1 static_scan |
| design/prototype/workbench-2026-11/PhoneCaptcha.dc.html | N/A | 全部 | 原型基准物(workbench-2026-11 硬基准),八节判据不适用;轮1 静态扫描留档 | 轮1 static_scan |
| design/prototype/workbench-2026-11/PhoneCheck.dc.html | N/A | 全部 | 原型基准物(workbench-2026-11 硬基准),八节判据不适用;轮1 静态扫描留档 | 轮1 static_scan |
| design/prototype/workbench-2026-11/PhoneExpired.dc.html | N/A | 全部 | 原型基准物(workbench-2026-11 硬基准),八节判据不适用;轮1 静态扫描留档 | 轮1 static_scan |
| design/prototype/workbench-2026-11/PhoneLinked.dc.html | N/A | 全部 | 原型基准物(workbench-2026-11 硬基准),八节判据不适用;轮1 静态扫描留档 | 轮1 static_scan |
| design/prototype/workbench-2026-11/PhoneLock.dc.html | N/A | 全部 | 原型基准物(workbench-2026-11 硬基准),八节判据不适用;轮1 静态扫描留档 | 轮1 static_scan |
| design/prototype/workbench-2026-11/PhoneOffline.dc.html | N/A | 全部 | 原型基准物(workbench-2026-11 硬基准),八节判据不适用;轮1 静态扫描留档 | 轮1 static_scan |
| design/prototype/workbench-2026-11/PhonePick.dc.html | N/A | 全部 | 原型基准物(workbench-2026-11 硬基准),八节判据不适用;轮1 静态扫描留档 | 轮1 static_scan |
| design/prototype/workbench-2026-11/PhoneRelAcct.dc.html | N/A | 全部 | 原型基准物(workbench-2026-11 硬基准),八节判据不适用;轮1 静态扫描留档 | 轮1 static_scan |
| design/prototype/workbench-2026-11/PhoneRelAll.dc.html | N/A | 全部 | 原型基准物(workbench-2026-11 硬基准),八节判据不适用;轮1 静态扫描留档 | 轮1 static_scan |
| design/prototype/workbench-2026-11/PhoneRelBad.dc.html | N/A | 全部 | 原型基准物(workbench-2026-11 硬基准),八节判据不适用;轮1 静态扫描留档 | 轮1 static_scan |
| design/prototype/workbench-2026-11/PhoneRelConfirm.dc.html | N/A | 全部 | 原型基准物(workbench-2026-11 硬基准),八节判据不适用;轮1 静态扫描留档 | 轮1 static_scan |
| design/prototype/workbench-2026-11/PhoneResult.dc.html | N/A | 全部 | 原型基准物(workbench-2026-11 硬基准),八节判据不适用;轮1 静态扫描留档 | 轮1 static_scan |
| design/prototype/workbench-2026-11/PhoneReview.dc.html | N/A | 全部 | 原型基准物(workbench-2026-11 硬基准),八节判据不适用;轮1 静态扫描留档 | 轮1 static_scan |
| design/prototype/workbench-2026-11/PhoneReviewWarn.dc.html | N/A | 全部 | 原型基准物(workbench-2026-11 硬基准),八节判据不适用;轮1 静态扫描留档 | 轮1 static_scan |
| design/prototype/workbench-2026-11/PhoneRun.dc.html | N/A | 全部 | 原型基准物(workbench-2026-11 硬基准),八节判据不适用;轮1 静态扫描留档 | 轮1 static_scan |
| design/prototype/workbench-2026-11/PhoneSetup.dc.html | N/A | 全部 | 原型基准物(workbench-2026-11 硬基准),八节判据不适用;轮1 静态扫描留档 | 轮1 static_scan |
| design/prototype/workbench-2026-11/PhoneTerms.dc.html | N/A | 全部 | 原型基准物(workbench-2026-11 硬基准),八节判据不适用;轮1 静态扫描留档 | 轮1 static_scan |
| design/prototype/workbench-2026-11/PhoneTs.dc.html | N/A | 全部 | 原型基准物(workbench-2026-11 硬基准),八节判据不适用;轮1 静态扫描留档 | 轮1 static_scan |
| design/prototype/workbench-2026-11/PhoneWait.dc.html | N/A | 全部 | 原型基准物(workbench-2026-11 硬基准),八节判据不适用;轮1 静态扫描留档 | 轮1 static_scan |
| design/prototype/workbench-2026-11/PopClock.dc.html | N/A | 全部 | 原型基准物(workbench-2026-11 硬基准),八节判据不适用;轮1 静态扫描留档 | 轮1 static_scan |
| design/prototype/workbench-2026-11/PopDown.dc.html | N/A | 全部 | 原型基准物(workbench-2026-11 硬基准),八节判据不适用;轮1 静态扫描留档 | 轮1 static_scan |
| design/prototype/workbench-2026-11/PopLogin.dc.html | N/A | 全部 | 原型基准物(workbench-2026-11 硬基准),八节判据不适用;轮1 静态扫描留档 | 轮1 static_scan |
| design/prototype/workbench-2026-11/PopPhone.dc.html | N/A | 全部 | 原型基准物(workbench-2026-11 硬基准),八节判据不适用;轮1 静态扫描留档 | 轮1 static_scan |
| design/prototype/workbench-2026-11/PreWarn.dc.html | N/A | 全部 | 原型基准物(workbench-2026-11 硬基准),八节判据不适用;轮1 静态扫描留档 | 轮1 static_scan |
| design/prototype/workbench-2026-11/README.md | N/A | 全部 | 原型基准物(workbench-2026-11 硬基准),八节判据不适用;轮1 静态扫描留档 | 轮1 static_scan |
| design/prototype/workbench-2026-11/Relogin.dc.html | N/A | 全部 | 原型基准物(workbench-2026-11 硬基准),八节判据不适用;轮1 静态扫描留档 | 轮1 static_scan |
| design/prototype/workbench-2026-11/Result.dc.html | N/A | 全部 | 原型基准物(workbench-2026-11 硬基准),八节判据不适用;轮1 静态扫描留档 | 轮1 static_scan |
| design/prototype/workbench-2026-11/RlBad.dc.html | N/A | 全部 | 原型基准物(workbench-2026-11 硬基准),八节判据不适用;轮1 静态扫描留档 | 轮1 static_scan |
| design/prototype/workbench-2026-11/RlCap.dc.html | N/A | 全部 | 原型基准物(workbench-2026-11 硬基准),八节判据不适用;轮1 静态扫描留档 | 轮1 static_scan |
| design/prototype/workbench-2026-11/RlConfirm.dc.html | N/A | 全部 | 原型基准物(workbench-2026-11 硬基准),八节判据不适用;轮1 静态扫描留档 | 轮1 static_scan |
| design/prototype/workbench-2026-11/RunAuto.dc.html | N/A | 全部 | 原型基准物(workbench-2026-11 硬基准),八节判据不适用;轮1 静态扫描留档 | 轮1 static_scan |
| design/prototype/workbench-2026-11/RunClick.dc.html | N/A | 全部 | 原型基准物(workbench-2026-11 硬基准),八节判据不适用;轮1 静态扫描留档 | 轮1 static_scan |
| design/prototype/workbench-2026-11/RunExpired.dc.html | N/A | 全部 | 原型基准物(workbench-2026-11 硬基准),八节判据不适用;轮1 静态扫描留档 | 轮1 static_scan |
| design/prototype/workbench-2026-11/RunPhone.dc.html | N/A | 全部 | 原型基准物(workbench-2026-11 硬基准),八节判据不适用;轮1 静态扫描留档 | 轮1 static_scan |
| design/prototype/workbench-2026-11/Running.dc.html | N/A | 全部 | 原型基准物(workbench-2026-11 硬基准),八节判据不适用;轮1 静态扫描留档 | 轮1 static_scan |
| design/prototype/workbench-2026-11/Settings.dc.html | N/A | 全部 | 原型基准物(workbench-2026-11 硬基准),八节判据不适用;轮1 静态扫描留档 | 轮1 static_scan |
| design/prototype/workbench-2026-11/Short.dc.html | N/A | 全部 | 原型基准物(workbench-2026-11 硬基准),八节判据不适用;轮1 静态扫描留档 | 轮1 static_scan |
| design/prototype/workbench-2026-11/Slept.dc.html | N/A | 全部 | 原型基准物(workbench-2026-11 硬基准),八节判据不适用;轮1 静态扫描留档 | 轮1 static_scan |
| design/prototype/workbench-2026-11/TermsDoc.dc.html | N/A | 全部 | 原型基准物(workbench-2026-11 硬基准),八节判据不适用;轮1 静态扫描留档 | 轮1 static_scan |
| design/prototype/workbench-2026-11/TermsOff.dc.html | N/A | 全部 | 原型基准物(workbench-2026-11 硬基准),八节判据不适用;轮1 静态扫描留档 | 轮1 static_scan |
| design/prototype/workbench-2026-11/TermsPrivacy.dc.html | N/A | 全部 | 原型基准物(workbench-2026-11 硬基准),八节判据不适用;轮1 静态扫描留档 | 轮1 static_scan |
| design/prototype/workbench-2026-11/TermsUpdate.dc.html | N/A | 全部 | 原型基准物(workbench-2026-11 硬基准),八节判据不适用;轮1 静态扫描留档 | 轮1 static_scan |
| design/prototype/workbench-2026-11/TermsWithdraw.dc.html | N/A | 全部 | 原型基准物(workbench-2026-11 硬基准),八节判据不适用;轮1 静态扫描留档 | 轮1 static_scan |
| design/prototype/workbench-2026-11/ToastMin.dc.html | N/A | 全部 | 原型基准物(workbench-2026-11 硬基准),八节判据不适用;轮1 静态扫描留档 | 轮1 static_scan |
| design/prototype/workbench-2026-11/TourPick.dc.html | N/A | 全部 | 原型基准物(workbench-2026-11 硬基准),八节判据不适用;轮1 静态扫描留档 | 轮1 static_scan |
| design/prototype/workbench-2026-11/TourRun.dc.html | N/A | 全部 | 原型基准物(workbench-2026-11 硬基准),八节判据不适用;轮1 静态扫描留档 | 轮1 static_scan |
| design/prototype/workbench-2026-11/TourTable.dc.html | N/A | 全部 | 原型基准物(workbench-2026-11 硬基准),八节判据不适用;轮1 静态扫描留档 | 轮1 static_scan |
| design/prototype/workbench-2026-11/UpdateAvail.dc.html | N/A | 全部 | 原型基准物(workbench-2026-11 硬基准),八节判据不适用;轮1 静态扫描留档 | 轮1 static_scan |
| design/prototype/workbench-2026-11/UpdateDown.dc.html | N/A | 全部 | 原型基准物(workbench-2026-11 硬基准),八节判据不适用;轮1 静态扫描留档 | 轮1 static_scan |
| design/prototype/workbench-2026-11/UpdateFail.dc.html | N/A | 全部 | 原型基准物(workbench-2026-11 硬基准),八节判据不适用;轮1 静态扫描留档 | 轮1 static_scan |
| design/prototype/workbench-2026-11/UpdateLive.dc.html | N/A | 全部 | 原型基准物(workbench-2026-11 硬基准),八节判据不适用;轮1 静态扫描留档 | 轮1 static_scan |
| design/prototype/workbench-2026-11/UpdateReady.dc.html | N/A | 全部 | 原型基准物(workbench-2026-11 硬基准),八节判据不适用;轮1 静态扫描留档 | 轮1 static_scan |
| design/prototype/workbench-2026-11/Waiting.dc.html | N/A | 全部 | 原型基准物(workbench-2026-11 硬基准),八节判据不适用;轮1 静态扫描留档 | 轮1 static_scan |
| design/prototype/workbench-2026-11/ZeroAct.dc.html | N/A | 全部 | 原型基准物(workbench-2026-11 硬基准),八节判据不适用;轮1 静态扫描留档 | 轮1 static_scan |
| design/prototype/workbench-2026-11/canvas.json | N/A | 全部 | 原型基准物(workbench-2026-11 硬基准),八节判据不适用;轮1 静态扫描留档 | 轮1 static_scan |
| design/prototype/workbench-2026-11/index.html | N/A | 全部 | 原型基准物(workbench-2026-11 硬基准),八节判据不适用;轮1 静态扫描留档 | 轮1 static_scan |
| design/prototype/workbench-2026-11/打开原型.bat | N/A | 全部 | 原型基准物(workbench-2026-11 硬基准),八节判据不适用;轮1 静态扫描留档 | 轮1 static_scan |
| design/specs/README.md | 已改 | §8 | 版本线/assistance-panels 描述/补 terms-consent 行(std-8c) | std-8c-docs.patch;批8 #22 |
| design/specs/assistance-panels.md | 已改 | §8 | §3 状态表对齐 update.js 实际状态机(std-8b) | std-8b-docs.patch;批8 #10 |
| design/specs/copywriting.md | 已改 | §8 | 五步引导/时钟六态/浮层字段/删登录剩余残留/抢单注记/std 六态(std-8b) | std-8b-docs.patch;批8 #5-9/24 |
| design/specs/terms-consent.md | 已改 | §8 | :188/:193 六步→五步(std-8d);直发残留登记待 r5(C8) | std-8d-docs.patch;批8 #23 |
| design/specs/versioning-and-release.md | 已改 | §8 | :11-12 基线行对齐 v1.1.1 已发布+去硬写(std-8a) | std-8a-docs.patch;批8 P1-4 |
| docs/ARCHITECTURE.md | 已改 | §8 | :177 Api 公开方法数 49→54(awk 实测复核,std-8c) | std-8c-docs.patch;批8 #25 |
| docs/CONFIG.md | 合规 | §8 | 示例占位符合规 | 批8;轮1 密钥治理 |
| docs/FEISHU_BOT.md | 合规 | §8 | :17 直发=飞书 webhook 语境,非用户文案 | 批8 |
| docs/GRAB.md | 已改 | §8 | 「抢报名」×4 对齐词表(std-17,含判据驱动 :38/:40/:55) | std-17-docs-p3.patch;批8 #27 |
| docs/LOGIN.md | 已改 | §8 | :10 「绿色版」→「本机版开发(bat、python)」(std-17) | std-17-docs-p3.patch;批8 #28 |
| docs/OPERATIONS.md | 合规 | §8 | 部署时区前提明示(F-09 依据) | 批8 |
| docs/PHONE_ACCESS.md | 合规 | §8 | :190 历史范围句 | 批8 |
| docs/PRIVACY_POLICY.md | 保留 | §8 | :11 入口路径同 C8 | 批8 #18 |
| docs/README.md | 已改 | §8 | :13 「抢报名」→「报名」(std-17) | std-17-docs-p3.patch;批8 #27 |
| docs/RETRY_POLICY_GUIDE.md | 合规 | §8 | 100 秒/直发/RISK-001 与实现一致 | 批8 |
| docs/TIMING_AND_DEDUP_ANALYSIS.md | 合规 | §8 | 时点分析,头部已标日期 | 批8 |
| docs/UI_SPEC.md | 已改 | §8 | :352 版本基线+六步×3+§9 七条旧口径对齐实现(std-8a/8b);:122 直发登记待 r5(C8) | std-8a/8b-docs.patch;批8 |
| docs/USER_AGREEMENT.md | 保留 | §8 | 入口路径+直发清理=r5 升版项(C8/B9,用户已拍板待排期) | 批8 #18/#19 |
| docs/archive/ASK_CODEX_REVIEW.md | 保留 | §8 | 归档/带日期设计稿,J8.3 不追改 | 批8 |
| docs/archive/BUILD_FROM_SCRATCH.md | 保留 | §8 | 归档/带日期设计稿,J8.3 不追改 | 批8 |
| docs/archive/README-full-20261022.md | 保留 | §8 | 归档/带日期设计稿,J8.3 不追改 | 批8 |
| docs/archive/REVIEW_PROMPT.md | 保留 | §8 | 归档/带日期设计稿,J8.3 不追改 | 批8 |
| docs/archive/UI_DESIGN.md | 保留 | §8 | 归档/带日期设计稿,J8.3 不追改 | 批8 |
| docs/archive/WORKBUDDY_LOGIN_PROMPT.md | 保留 | §8 | 归档/带日期设计稿,J8.3 不追改 | 批8 |
| docs/archive/process/2026-10-30/discuss/2026-10-30-phone-access-channel.md | 保留 | §8 | 归档/带日期设计稿,J8.3 不追改 | 批8 |
| docs/archive/process/2026-10-30/plans/2026-10-30-phone-access-channel.md | 保留 | §8 | 归档/带日期设计稿,J8.3 不追改 | 批8 |
| docs/archive/process/2026-10-30/plans/2026-10-30-phone-ui-failure-repair.md | 保留 | §8 | 归档/带日期设计稿,J8.3 不追改 | 批8 |
| docs/archive/process/2026-10-31/findings/2026-10-31-ui-findings.md | 保留 | §8 | 归档/带日期设计稿,J8.3 不追改 | 批8 |
| docs/archive/process/2026-10-31/handoff/2026-10-31-codex-handoff-group2.md | 保留 | §8 | 归档/带日期设计稿,J8.3 不追改 | 批8 |
| docs/archive/process/2026-10-31/handoff/2026-10-31-mobile-ui-handoff.md | 保留 | §8 | 归档/带日期设计稿,J8.3 不追改 | 批8 |
| docs/archive/process/2026-10-31/handoff/2026-10-31-phone-access-handoff.md | 保留 | §8 | 归档/带日期设计稿,J8.3 不追改 | 批8 |
| docs/archive/process/2026-10-31/plans/2026-10-31-phone-access-channel-redesign.md | 保留 | §8 | 归档/带日期设计稿,J8.3 不追改 | 批8 |
| docs/archive/process/2026-10-31/plans/2026-10-31-phone-access-repair-followup.md | 保留 | §8 | 归档/带日期设计稿,J8.3 不追改 | 批8 |
| docs/archive/process/2026-10-31/plans/2026-10-31-phone-access-repair.md | 保留 | §8 | 归档/带日期设计稿,J8.3 不追改 | 批8 |
| docs/archive/process/2026-10-31/plans/2026-10-31-phone-control-release-publication-repair.md | 保留 | §8 | 归档/带日期设计稿,J8.3 不追改 | 批8 |
| docs/archive/process/README.md | 保留 | §8 | 归档/带日期设计稿,J8.3 不追改 | 批8 |
| docs/superpowers/specs/2026-10-31-phone-access-channel-design.md | 保留 | §8 | 归档/带日期设计稿,J8.3 不追改 | 批8 |
| docs/superpowers/specs/2026-11-02-workbench-ui-redesign-design.md | 保留 | §8 | 归档/带日期设计稿,J8.3 不追改 | 批8 |
| docs/superpowers/specs/2026-11-02-workbench-ui-state-map.md | 保留 | §8 | 归档/带日期设计稿,J8.3 不追改 | 批8 |
| docs/superpowers/specs/2026-11-03-architecture-revision-design.md | 保留 | §8 | 归档/带日期设计稿,J8.3 不追改 | 批8 |
| local/README.md | 保留 | 全部 | 未匹配批次规则,人工复核项 | - |
| local/advanced_helper.py | 合规 | §4 | 薄壳(61 行);自扫 0 命中 | 根级自扫 |
| local/app.py | 已改 | §4 | 13 处吞异常裁决注释(std-9a)+3 处措辞修正(std-15a,质检员文本);datetime=日志戳/兜底/epoch(J3.2);Fix C 已提交 | std-9a-app/std-15a-wording.patch;质检员 33 处全查 0 不符 |
| local/application/__init__.py | 保留 | §1 | 「只依赖 domain」声明与 advanced_component_service 直连 infrastructure 的口径出入(C6),P3 保留 | 批2 观察项 A |
| local/application/advanced_component_service.py | 已改 | §4 | :287 except-pass→_note 留痕(P2);:352 补注释;canonical 14→13 | std-2-application.patch |
| local/application/auto_relogin.py | 合规 | §1/§2/§3/§4/§5/§6 | 批2 扫描:now 全注入、0 写盘、0 硬路径、脱敏合格 | 批2 判据命令 |
| local/application/login_relay_service.py | 已改 | §4 | :479/:481 补注释(时序核实:SUCCESS 先于回调);canonical 其余命中裁决合规 | std-2-application.patch |
| local/application/login_service.py | 合规 | §1/§2/§3/§4/§5/§6 | 批2 扫描:now 全注入、0 写盘、0 硬路径、脱敏合格 | 批2 判据命令 |
| local/application/phone_service.py | 合规 | §1/§3/§4/§5 | now 注入;:211/:216 canonical 命中为裁决合规(必要吞,批2 已核) | 批2 + 根级自扫 |
| local/application/plan_service.py | 已改 | §4 | :378/:384/:388 finally 清理吞补注释(必要吞);Fix B 时钟门控为 §3 合规样板 | std-2-application.patch |
| local/application/update_service.py | 合规 | §1/§2/§3/§4/§5/§6 | 批2 扫描:now 全注入、0 写盘、0 硬路径、脱敏合格 | 批2 判据命令 |
| local/build/build_advanced.py | 保留 | 全部 | 打包构建链,轮1 范围外;仅静态扫描(轮1)+根级 grep 无违规命中 | 轮1 COVERAGE;静态扫描 |
| local/build/build_exe.py | 保留 | 全部 | 打包构建链,轮1 范围外;仅静态扫描(轮1)+根级 grep 无违规命中 | 轮1 COVERAGE;静态扫描 |
| local/build/build_installer.py | 保留 | 全部 | 打包构建链,轮1 范围外;仅静态扫描(轮1)+根级 grep 无违规命中 | 轮1 COVERAGE;静态扫描 |
| local/build/make_portable.py | 保留 | 全部 | 打包构建链,轮1 范围外;仅静态扫描(轮1)+根级 grep 无违规命中 | 轮1 COVERAGE;静态扫描 |
| local/business_clock.py | 已改 | §4 | 2 处注释(std-9b)+:665 措辞修正(std-15b,质检员文本);:859 os_offset=设计;时间源实现=J3.2a | std-9b-grab/std-15b-wording.patch;质检员抽查 |
| local/config.example.json | 保留 | 全部 | 未匹配批次规则,人工复核项 | - |
| local/domain/__init__.py | 合规 | §1/§2/§3/§4/§5/§6 | 批1 扫描:纯函数层判据全过(import 0 反向/0 落盘/0 读钟/20 处 except 全窄捕) | 批1 判据命令 + 根级自扫 |
| local/domain/demo_data.py | 合规 | §1/§2/§3/§4/§5/§6 | 批1 扫描:纯函数层判据全过(import 0 反向/0 落盘/0 读钟/20 处 except 全窄捕) | 批1 判据命令 + 根级自扫 |
| local/domain/errors.py | 合规 | §1/§2/§3/§4/§5/§6 | 批1 扫描:纯函数层判据全过(import 0 反向/0 落盘/0 读钟/20 处 except 全窄捕) | 批1 判据命令 + 根级自扫 |
| local/domain/lifecycle_rules.py | 合规 | §1/§2/§3/§4/§5/§6 | 批1 扫描:纯函数层判据全过(import 0 反向/0 落盘/0 读钟/20 处 except 全窄捕) | 批1 判据命令 + 根级自扫 |
| local/domain/log_events.py | 合规 | §5 | 键名黑名单模块,§5 正面样板;批1 扫描确认 | 批1 命令 11/12 |
| local/domain/login_rules.py | 已改 | §4 | :91 宽 except→(TypeError,ValueError)+注释;判据 1→0,反向 0→1 | std-1-domain.patch;批1 P2 |
| local/domain/phone_rules.py | 保留 | §8 | MAX_IMAGE_BYTES/_PNG_MAGIC 跨进程镜像常量,注释已指明对端 | 批1 P3-3 |
| local/domain/plan_rules.py | 保留 | §8 | _NON_CONFLICT_TEXT 与 selection.js 双源,测试钉住(test_signup_plan:189) | 批1 P3-2 |
| local/domain/retry_rules.py | 合规 | §1/§2/§3/§4/§5/§6 | 批1 扫描:纯函数层判据全过(import 0 反向/0 落盘/0 读钟/20 处 except 全窄捕) | 批1 判据命令 + 根级自扫 |
| local/domain/retry_window.py | 合规 | §1/§2/§3/§4/§5/§6 | 批1 扫描:纯函数层判据全过(import 0 反向/0 落盘/0 读钟/20 处 except 全窄捕) | 批1 判据命令 + 根级自扫 |
| local/domain/signup_reply.py | 合规 | §1/§2/§3/§4/§5/§6 | 批1 扫描:纯函数层判据全过(import 0 反向/0 落盘/0 读钟/20 处 except 全窄捕) | 批1 判据命令 + 根级自扫 |
| local/domain/time_text.py | 合规 | §1/§2/§3/§4/§5/§6 | 批1 扫描:纯函数层判据全过(import 0 反向/0 落盘/0 读钟/20 处 except 全窄捕) | 批1 判据命令 + 根级自扫 |
| local/domain/worker_lines.py | 合规 | §1/§2/§3/§4/§5/§6 | 批1 扫描:纯函数层判据全过(import 0 反向/0 落盘/0 读钟/20 处 except 全窄捕) | 批1 判据命令 + 根级自扫 |
| local/grab.py | 已改 | §4 | 8 处裸 except-pass 补注释(std-9b);datetime 命中=日志戳/nonce 种子(J3.2) | std-9b-grab.patch;根级自扫;轮1 深审 |
| local/gui.py | 保留 | §4/§3 | 遗留 tkinter 壳:4 处裸 pass 不注(B7 决定删除);:820/:833 naive 时区=轮1 F-12 已记 | 轮1 F-12;根级自扫 |
| local/infrastructure/__init__.py | 合规 | §1/§2/§3/§4/§5/§6 | 批3 扫描:os.replace 原子写齐、锁句柄 finally 收口、脱敏合格、0 盘符 | 批3 判据命令 |
| local/infrastructure/advanced_features.py | 合规 | §1/§2/§3/§4/§5/§6 | 批3 扫描:os.replace 原子写齐、锁句柄 finally 收口、脱敏合格、0 盘符 | 批3 判据命令 |
| local/infrastructure/component_packages.py | 合规 | §1/§2/§3/§4/§5/§6 | 批3 扫描:os.replace 原子写齐、锁句柄 finally 收口、脱敏合格、0 盘符 | 批3 判据命令 |
| local/infrastructure/credential_store.py | 合规 | §1/§2/§3/§4/§5/§6 | 批3 扫描:os.replace 原子写齐、锁句柄 finally 收口、脱敏合格、0 盘符 | 批3 判据命令 |
| local/infrastructure/lifecycle_store.py | 已改 | §4 | :263/:140 留痕(std-3);:264 措辞修正+删未使用 as exc(std-15b);:33/:79 本机经过时长=J3.2 允许清单 | std-3/15b-infrastructure/wording.patch;批3 V1/V2 |
| local/infrastructure/phone_http.py | 合规 | §1/§2/§3/§4/§5/§6 | 批3 扫描:os.replace 原子写齐、锁句柄 finally 收口、脱敏合格、0 盘符 | 批3 判据命令 |
| local/infrastructure/phone_qr.py | 合规 | §1/§2/§3/§4/§5/§6 | 批3 扫描:os.replace 原子写齐、锁句柄 finally 收口、脱敏合格、0 盘符 | 批3 判据命令 |
| local/infrastructure/phone_session_store.py | 保留 | §3 | 设备信任 TTL 用 time.time():非报名链、now 可注入,J3.2c 同类,意见性保留 | 批3 V3 |
| local/infrastructure/prefs_store.py | 合规 | §6 | 锁句柄非 with 但双层 finally(J6.2 允许清单);:33 broad except=文档化契约非 pass | 批3 J6.2 核对 |
| local/infrastructure/process_tree.py | 已改 | §4 | 5 处清理路径 pass 补裁决注释(std-10);外层 raise 保原异常 | std-10-infra-comments.patch;批3 V6 |
| local/infrastructure/tray_icon.py | 已改 | §4 | 6 处 broad pass 补裁决注释(std-10):装饰层失败语义,docstring 明示 | std-10-infra-comments.patch;批3 V5 |
| local/infrastructure/tunnel_manager.py | 已改 | §4 | :303 kill 兜底补裁决注释(std-10);deadline 用注入 monotonic | std-10-infra-comments.patch;批3 V7 |
| local/installer/ChineseSimplified.isl | N/A | 全部 | 启动器/打包资产/依赖清单,判据不适用;密钥治理已核 | 轮1 |
| local/launchers/1-登录.bat | N/A | 全部 | 启动器/打包资产/依赖清单,判据不适用;密钥治理已核 | 轮1 |
| local/launchers/2-抢活动.bat | N/A | 全部 | 启动器/打包资产/依赖清单,判据不适用;密钥治理已核 | 轮1 |
| local/launchers/3-检查登录和活动.bat | N/A | 全部 | 启动器/打包资产/依赖清单,判据不适用;密钥治理已核 | 轮1 |
| local/launchers/4-图形界面.bat | N/A | 全部 | 启动器/打包资产/依赖清单,判据不适用;密钥治理已核 | 轮1 |
| local/launchers/_py.bat | N/A | 全部 | 启动器/打包资产/依赖清单,判据不适用;密钥治理已核 | 轮1 |
| local/launchers/install.bat | N/A | 全部 | 启动器/打包资产/依赖清单,判据不适用;密钥治理已核 | 轮1 |
| local/launchers/启动不了点我.txt | N/A | 全部 | 启动器/打包资产/依赖清单,判据不适用;密钥治理已核 | 轮1 |
| local/launchers/遇到问题先看我.txt | N/A | 全部 | 启动器/打包资产/依赖清单,判据不适用;密钥治理已核 | 轮1 |
| local/login_relay.py | 合规 | §4 | 4 处 except-pass 注释 100% 在场(根级自扫裁决) | 根级自扫 |
| local/requirements-advanced-ocr.txt | N/A | 全部 | 启动器/打包资产/依赖清单,判据不适用;密钥治理已核 | 轮1 |
| local/requirements-advanced-phone.txt | N/A | 全部 | 启动器/打包资产/依赖清单,判据不适用;密钥治理已核 | 轮1 |
| local/requirements.txt | N/A | 全部 | 启动器/打包资产/依赖清单,判据不适用;密钥治理已核 | 轮1 |
| local/runtime_paths.py | 合规 | §6 | 迁移 mkstemp+copy2+os.replace+finally unlink;0 盘符 | 批3 扫描 |
| local/signup_plan.py | 合规 | §1/§3/§4 | 轮1 深审合格;根级自扫 0 命中 | 轮1 D 报告;根级自扫 |
| local/signup_signing.py | 合规 | §1/§4/§5 | CNG 签名轮1 深审合格;自扫 0 命中 | 轮1 D 报告 |
| local/signup_transport.py | 已改 | §4 | :170 裁决注释(std-9b):不吞会顶掉 except 的 return 致重复 failed/completed 缺失 | std-9b-grab.patch;质检员抽查 |
| local/site_target.py | 合规 | §6/§8 | 域名唯一真源;自扫 0 命中 | 根级自扫;轮1 L4/M8 |
| local/tests/fixtures/business_clock.py | 已改 | §2 | TestWallClock→WallClockStub(std-18a:pytest Test* 形状误导,非 TestCase,65 处引用 8 文件同步改名,计数守恒) | std-18a-rename.patch;批5 §2 |
| local/tests/fixtures/runtime_bridge.js | 合规 | §7 | 桥夹具,经 test_qa_bridge_contract 执行覆盖 | 批5;轮1 |
| local/tests/test_advanced_features.py | 合规 | §7 | 批5:夹具 dir= 全合法、0 恒真断言、0 脆弱日期、except-pass 15 处全为窄类型清理轮询形态 | 批5 判据命令 |
| local/tests/test_application_services.py | 合规 | §7 | 批5:夹具 dir= 全合法、0 恒真断言、0 脆弱日期、except-pass 15 处全为窄类型清理轮询形态 | 批5 判据命令 |
| local/tests/test_auto_relogin.py | 合规 | §7 | 批5:夹具 dir= 全合法、0 恒真断言、0 脆弱日期、except-pass 15 处全为窄类型清理轮询形态 | 批5 判据命令 |
| local/tests/test_business_clock.py | 合规 | §7 | 批5:夹具 dir= 全合法、0 恒真断言、0 脆弱日期、except-pass 15 处全为窄类型清理轮询形态 | 批5 判据命令 |
| local/tests/test_business_clock_wiring.py | 合规 | §7 | 批5:夹具 dir= 全合法、0 恒真断言、0 脆弱日期、except-pass 15 处全为窄类型清理轮询形态 | 批5 判据命令 |
| local/tests/test_clock_tail.py | 合规 | §7 | 批5:夹具 dir= 全合法、0 恒真断言、0 脆弱日期、except-pass 15 处全为窄类型清理轮询形态 | 批5 判据命令 |
| local/tests/test_component_builder.py | 保留 | §7 | :25 <tmp>/C:/bad 为负向测试输入,J7.2 允许清单豁免 | 批5;STANDARD J7.2 允许清单 |
| local/tests/test_component_packages.py | 合规 | §7 | 批5:夹具 dir= 全合法、0 恒真断言、0 脆弱日期、except-pass 15 处全为窄类型清理轮询形态 | 批5 判据命令 |
| local/tests/test_credential_store.py | 合规 | §7 | 批5:夹具 dir= 全合法、0 恒真断言、0 脆弱日期、except-pass 15 处全为窄类型清理轮询形态 | 批5 判据命令 |
| local/tests/test_grab_log.py | 合规 | §7 | 批5:夹具 dir= 全合法、0 恒真断言、0 脆弱日期、except-pass 15 处全为窄类型清理轮询形态 | 批5 判据命令 |
| local/tests/test_installer_script.py | 合规 | §7 | 批5:夹具 dir= 全合法、0 恒真断言、0 脆弱日期、except-pass 15 处全为窄类型清理轮询形态 | 批5 判据命令 |
| local/tests/test_layer_boundaries.py | 合规 | §7 | 批5:夹具 dir= 全合法、0 恒真断言、0 脆弱日期、except-pass 15 处全为窄类型清理轮询形态 | 批5 判据命令 |
| local/tests/test_lifecycle_release.py | 合规 | §7 | 批5:夹具 dir= 全合法、0 恒真断言、0 脆弱日期、except-pass 15 处全为窄类型清理轮询形态 | 批5 判据命令 |
| local/tests/test_login_probe.py | 合规 | §7 | 批5:夹具 dir= 全合法、0 恒真断言、0 脆弱日期、except-pass 15 处全为窄类型清理轮询形态 | 批5 判据命令 |
| local/tests/test_login_relay.py | 合规 | §7 | 批5:夹具 dir= 全合法、0 恒真断言、0 脆弱日期、except-pass 15 处全为窄类型清理轮询形态 | 批5 判据命令 |
| local/tests/test_login_relay_service.py | 合规 | §7 | 批5:夹具 dir= 全合法、0 恒真断言、0 脆弱日期、except-pass 15 处全为窄类型清理轮询形态 | 批5 判据命令 |
| local/tests/test_network_policy.py | 合规 | §7 | 批5:夹具 dir= 全合法、0 恒真断言、0 脆弱日期、except-pass 15 处全为窄类型清理轮询形态 | 批5 判据命令 |
| local/tests/test_phone_http.py | 合规 | §7 | 批5:夹具 dir= 全合法、0 恒真断言、0 脆弱日期、except-pass 15 处全为窄类型清理轮询形态 | 批5 判据命令 |
| local/tests/test_phone_rules.py | 合规 | §7 | 批5:夹具 dir= 全合法、0 恒真断言、0 脆弱日期、except-pass 15 处全为窄类型清理轮询形态 | 批5 判据命令 |
| local/tests/test_phone_service.py | 合规 | §7 | 批5:夹具 dir= 全合法、0 恒真断言、0 脆弱日期、except-pass 15 处全为窄类型清理轮询形态 | 批5 判据命令 |
| local/tests/test_phone_session_store.py | 合规 | §7 | 批5:夹具 dir= 全合法、0 恒真断言、0 脆弱日期、except-pass 15 处全为窄类型清理轮询形态 | 批5 判据命令 |
| local/tests/test_phone_ui.py | 合规 | §7 | 批5:夹具 dir= 全合法、0 恒真断言、0 脆弱日期、except-pass 15 处全为窄类型清理轮询形态 | 批5 判据命令 |
| local/tests/test_qa_bridge_contract.py | 合规 | §7 | 批5:夹具 dir= 全合法、0 恒真断言、0 脆弱日期、except-pass 15 处全为窄类型清理轮询形态 | 批5 判据命令 |
| local/tests/test_real_data_contract.py | 已改 | §2 | TestWallClock→WallClockStub import/实例化同步(std-18a/18b/18c,65↔65 守恒,模块测试+289 契约全绿) | std-18a/18b/18c-rename.patch |
| local/tests/test_release_audit.py | 合规 | §7 | 批5:夹具 dir= 全合法、0 恒真断言、0 脆弱日期、except-pass 15 处全为窄类型清理轮询形态 | 批5 判据命令 |
| local/tests/test_retry_events.py | 合规 | §7 | 批5:夹具 dir= 全合法、0 恒真断言、0 脆弱日期、except-pass 15 处全为窄类型清理轮询形态 | 批5 判据命令 |
| local/tests/test_retry_phone_integration.py | 合规 | §7 | 批5:夹具 dir= 全合法、0 恒真断言、0 脆弱日期、except-pass 15 处全为窄类型清理轮询形态 | 批5 判据命令 |
| local/tests/test_retry_phone_policy.py | 已改 | §2 | TestWallClock→WallClockStub import/实例化同步(std-18a/18b/18c,65↔65 守恒,模块测试+289 契约全绿) | std-18a/18b/18c-rename.patch |
| local/tests/test_retry_policy.py | 已改 | §7/§2 | docstring <tmp> 口径(std-5)+TestWallClock 改名(std-18b) | std-5-tests/std-18b-rename.patch |
| local/tests/test_runtime_bundle.py | 已改 | §2 | TestWallClock→WallClockStub import/实例化同步(std-18a/18b/18c,65↔65 守恒,模块测试+289 契约全绿) | std-18a/18b/18c-rename.patch |
| local/tests/test_school_contract.py | 合规 | §7 | 批5:夹具 dir= 全合法、0 恒真断言、0 脆弱日期、except-pass 15 处全为窄类型清理轮询形态 | 批5 判据命令 |
| local/tests/test_session_persistence.py | 已改 | §2 | TestWallClock→WallClockStub import/实例化同步(std-18a/18b/18c,65↔65 守恒,模块测试+289 契约全绿) | std-18a/18b/18c-rename.patch |
| local/tests/test_session_writer.py | 合规 | §7 | 批5:夹具 dir= 全合法、0 恒真断言、0 脆弱日期、except-pass 15 处全为窄类型清理轮询形态 | 批5 判据命令 |
| local/tests/test_signup_plan.py | 已改 | §2 | TestWallClock→WallClockStub import/实例化同步(std-18a/18b/18c,65↔65 守恒,模块测试+289 契约全绿) | std-18a/18b/18c-rename.patch |
| local/tests/test_signup_reply.py | 合规 | §7 | 批5:夹具 dir= 全合法、0 恒真断言、0 脆弱日期、except-pass 15 处全为窄类型清理轮询形态 | 批5 判据命令 |
| local/tests/test_signup_signing.py | 合规 | §7 | 批5:夹具 dir= 全合法、0 恒真断言、0 脆弱日期、except-pass 15 处全为窄类型清理轮询形态 | 批5 判据命令 |
| local/tests/test_signup_transport.py | 合规 | §7 | 批5:夹具 dir= 全合法、0 恒真断言、0 脆弱日期、except-pass 15 处全为窄类型清理轮询形态 | 批5 判据命令 |
| local/tests/test_site_target.py | 合规 | §7 | 批5:夹具 dir= 全合法、0 恒真断言、0 脆弱日期、except-pass 15 处全为窄类型清理轮询形态 | 批5 判据命令 |
| local/tests/test_terms_consent.py | 合规 | §7 | 批5:夹具 dir= 全合法、0 恒真断言、0 脆弱日期、except-pass 15 处全为窄类型清理轮询形态 | 批5 判据命令 |
| local/tests/test_time_contract.py | 合规 | §7 | 批5:夹具 dir= 全合法、0 恒真断言、0 脆弱日期、except-pass 15 处全为窄类型清理轮询形态 | 批5 判据命令 |
| local/tests/test_tunnel_manager.py | 合规 | §7 | 批5:夹具 dir= 全合法、0 恒真断言、0 脆弱日期、except-pass 15 处全为窄类型清理轮询形态 | 批5 判据命令 |
| local/tests/test_ui_contract.py | 合规 | §7 | 批5:夹具 dir= 全合法、0 恒真断言、0 脆弱日期、except-pass 15 处全为窄类型清理轮询形态 | 批5 判据命令 |
| local/tests/test_ui_reliability.py | 合规 | §7 | 批5:夹具 dir= 全合法、0 恒真断言、0 脆弱日期、except-pass 15 处全为窄类型清理轮询形态 | 批5 判据命令 |
| local/tests/test_update_check.py | 已改 | §2 | TestWallClock→WallClockStub import/实例化同步(std-18a/18b/18c,65↔65 守恒,模块测试+289 契约全绿) | std-18a/18b/18c-rename.patch |
| local/tests/test_updater.py | 已改 | §7 | :51 docstring <tmp>→gettempdir 口径(std-5) | std-5-tests.patch;批5 J7.2 |
| local/tests/test_worker_boundaries.py | 合规 | §7 | 批5:夹具 dir= 全合法、0 恒真断言、0 脆弱日期、except-pass 15 处全为窄类型清理轮询形态 | 批5 判据命令 |
| local/time_contract.py | 合规 | §3/§4 | UTC+8 唯一口径轮1 合格;自扫 0 命中 | 轮1 D 报告 |
| local/ui/app.js | 已改 | §4 | :67/:397/:503 吞异常补注释(std-4a);armedAt 死字段为观察项 | std-4a-ui.patch;批4 V3-V5 |
| local/ui/brand/app.ico | N/A | 全部 | 二进制图标资产 | 批4 N/A |
| local/ui/brand/favicon.ico | N/A | 全部 | 二进制图标资产 | 批4 N/A |
| local/ui/controllers/bridge.js | 合规 | §1/§2/§3/§4/§6 | 批4 扫描:无 fs、无硬路径、businessNowMs 架构完整、文案为 1:1 契约 | 批4 判据命令 |
| local/ui/controllers/clock.js | 合规 | §1/§2/§3/§4/§6 | 批4 扫描:无 fs、无硬路径、businessNowMs 架构完整、文案为 1:1 契约 | 批4 判据命令 |
| local/ui/controllers/plan-events.js | 合规 | §1/§2/§3/§4/§6 | 批4 扫描:无 fs、无硬路径、businessNowMs 架构完整、文案为 1:1 契约 | 批4 判据命令 |
| local/ui/controllers/plan.js | 已改 | §4/§2 | :265 吞异常补注释(std-4b);armedAt 死键 :84/:220 删除(std-16) | std-4b-ui/std-16-armedat.patch |
| local/ui/controllers/prefs.js | 合规 | §1/§2/§3/§4/§6 | 批4 扫描:无 fs、无硬路径、businessNowMs 架构完整、文案为 1:1 契约 | 批4 判据命令 |
| local/ui/controllers/refresh.js | 已改 | §3/§2 | :69 armedAt 死键删除(std-16);:309 Date.now 回退带注释仅显示同步窗 | std-16-armedat.patch;批4 研判 |
| local/ui/controllers/terms.js | 合规 | §1/§2/§3/§4/§6 | 批4 扫描:无 fs、无硬路径、businessNowMs 架构完整、文案为 1:1 契约 | 批4 判据命令 |
| local/ui/controllers/tick.js | 合规 | §1/§2/§3/§4/§6 | 批4 扫描:无 fs、无硬路径、businessNowMs 架构完整、文案为 1:1 契约 | 批4 判据命令 |
| local/ui/controllers/update.js | 已改 | §4 | :65/:118 吞异常补注释(std-4b) | std-4b-ui.patch;批4 V7/V8 |
| local/ui/controllers/window.js | 合规 | §1/§2/§3/§4/§6 | 批4 扫描:无 fs、无硬路径、businessNowMs 架构完整、文案为 1:1 契约 | 批4 判据命令 |
| local/ui/index.html | 合规 | §1/§2/§3/§4/§6 | 批4 扫描:无 fs、无硬路径、businessNowMs 架构完整、文案为 1:1 契约 | 批4 判据命令 |
| local/ui/led.js | 合规 | §1/§2/§3/§4/§6 | 批4 扫描:无 fs、无硬路径、businessNowMs 架构完整、文案为 1:1 契约 | 批4 判据命令 |
| local/ui/m/app.js | 合规 | §1/§2/§3/§4/§6 | 批4 扫描:无 fs、无硬路径、businessNowMs 架构完整、文案为 1:1 契约 | 批4 判据命令 |
| local/ui/m/apple-touch-icon.png | N/A | 全部 | 二进制图标资产 | 批4 N/A |
| local/ui/m/favicon.ico | N/A | 全部 | 二进制图标资产 | 批4 N/A |
| local/ui/m/index.html | 合规 | §1/§2/§3/§4/§6 | 批4 扫描:无 fs、无硬路径、businessNowMs 架构完整、文案为 1:1 契约 | 批4 判据命令 |
| local/ui/m/styles.css | N/A | 全部 | 纯样式 | 批4 |
| local/ui/state/clock.js | 合规 | §1/§2/§3/§4/§6 | 批4 扫描:无 fs、无硬路径、businessNowMs 架构完整、文案为 1:1 契约 | 批4 判据命令 |
| local/ui/state/filters.js | 合规 | §1/§2/§3/§4/§6 | 批4 扫描:无 fs、无硬路径、businessNowMs 架构完整、文案为 1:1 契约 | 批4 判据命令 |
| local/ui/state/labels.js | 合规 | §1/§2/§3/§4/§6 | 批4 扫描:无 fs、无硬路径、businessNowMs 架构完整、文案为 1:1 契约 | 批4 判据命令 |
| local/ui/state/login.js | 合规 | §1/§2/§3/§4/§6 | 批4 扫描:无 fs、无硬路径、businessNowMs 架构完整、文案为 1:1 契约 | 批4 判据命令 |
| local/ui/state/plan.js | 已改 | §2 | armedAt 死键 :59/:81 删除(std-16,全仓零读取核verified,契约测试反而禁止该字段) | std-16-armedat.patch;批4 观察项 |
| local/ui/state/rounds.js | 合规 | §1/§2/§3/§4/§6 | 批4 扫描:无 fs、无硬路径、businessNowMs 架构完整、文案为 1:1 契约 | 批4 判据命令 |
| local/ui/state/store.js | 合规 | §1/§2/§3/§4/§6 | 批4 扫描:无 fs、无硬路径、businessNowMs 架构完整、文案为 1:1 契约 | 批4 判据命令 |
| local/ui/state/task-display.js | 合规 | §1/§2/§3/§4/§6 | 批4 扫描:无 fs、无硬路径、businessNowMs 架构完整、文案为 1:1 契约 | 批4 判据命令 |
| local/ui/state/time.js | 合规 | §1/§2/§3/§4/§6 | 批4 扫描:无 fs、无硬路径、businessNowMs 架构完整、文案为 1:1 契约 | 批4 判据命令 |
| local/ui/styles.css | N/A | 全部 | 纯样式,无路径/逻辑 | 批4 |
| local/ui/views/clock-pop.js | 合规 | §1/§2/§3/§4/§6 | 批4 扫描:无 fs、无硬路径、businessNowMs 架构完整、文案为 1:1 契约 | 批4 判据命令 |
| local/ui/views/clock.js | 合规 | §1/§2/§3/§4/§6 | 批4 扫描:无 fs、无硬路径、businessNowMs 架构完整、文案为 1:1 契约 | 批4 判据命令 |
| local/ui/views/help.js | 合规 | §1/§2/§3/§4/§6 | 批4 扫描:无 fs、无硬路径、businessNowMs 架构完整、文案为 1:1 契约 | 批4 判据命令 |
| local/ui/views/list.js | 合规 | §1/§2/§3/§4/§6 | 批4 扫描:无 fs、无硬路径、businessNowMs 架构完整、文案为 1:1 契约 | 批4 判据命令 |
| local/ui/views/log.js | 合规 | §1/§2/§3/§4/§6 | 批4 扫描:无 fs、无硬路径、businessNowMs 架构完整、文案为 1:1 契约 | 批4 判据命令 |
| local/ui/views/login.js | 合规 | §1/§2/§3/§4/§6 | 批4 扫描:无 fs、无硬路径、businessNowMs 架构完整、文案为 1:1 契约 | 批4 判据命令 |
| local/ui/views/phone.js | 合规 | §1/§2/§3/§4/§6 | 批4 扫描:无 fs、无硬路径、businessNowMs 架构完整、文案为 1:1 契约 | 批4 判据命令 |
| local/ui/views/plan-panel.js | 合规 | §1/§2/§3/§4/§6 | 批4 扫描:无 fs、无硬路径、businessNowMs 架构完整、文案为 1:1 契约 | 批4 判据命令 |
| local/ui/views/relogin.js | 已改 | §4 | :74 取消重登失败静默→addLog 留痕(P2);空 flow 哨兵=轮1 Fix E 在位 | std-4a-ui.patch;批4 V1 |
| local/ui/views/selection.js | 合规 | §1/§2/§3/§4/§6 | 批4 扫描:无 fs、无硬路径、businessNowMs 架构完整、文案为 1:1 契约 | 批4 判据命令 |
| local/ui/views/settings.js | 合规 | §1/§2/§3/§4/§6 | 批4 扫描:无 fs、无硬路径、businessNowMs 架构完整、文案为 1:1 契约 | 批4 判据命令 |
| local/ui/views/status-cards.js | 合规 | §1/§2/§3/§4/§6 | 批4 扫描:无 fs、无硬路径、businessNowMs 架构完整、文案为 1:1 契约 | 批4 判据命令 |
| local/ui/views/terms.js | 已改 | §4 | :363 空 catch 补注释(std-4a) | std-4a-ui.patch;批4 V2 |
| local/ui/views/tour.js | 合规 | §1/§2/§3/§4/§6 | 批4 扫描:无 fs、无硬路径、businessNowMs 架构完整、文案为 1:1 契约 | 批4 判据命令 |
| local/ui/views/update.js | 合规 | §1/§2/§3/§4/§6 | 批4 扫描:无 fs、无硬路径、businessNowMs 架构完整、文案为 1:1 契约 | 批4 判据命令 |
| local/update_check.py | 合规 | §4/§6 | no_installer 三分类;自扫 0 except-pass | 根级自扫;轮1 L1/#4 |
| local/updater.py | 保留 | §6 | :33-36 <tmp> 死分支(F-01b,恒回退无害);改=生产行为,轮1 记录未动 | 根级自扫;轮1 F-01b |
| server/README.md | 保留 | 全部 | 未匹配批次规则,人工复核项 | - |
| server/bot/bot.js | 已改 | §4/§6 | :114 补策略分歧裁决注释(std-13,C9:低价值缓存降级 vs handled_messages 显式抛错);:123 users.json 直写(P3)仍保留 | std-13-server-js-comments.patch;批6 V7/V8 |
| server/bot/handled_messages.js | 合规 | §4/§6 | tmp+rename 原子写、解析失败显式抛:正面样板 | 批6 |
| server/bot/package.json | 保留 | 全部 | 未匹配批次规则,人工复核项 | - |
| server/bot/test_bot_runtime.js | 保留 | §7 | :30 <tmp> 常量带系统临时目录回退,改涉测试行为(P3) | 批6 V13 |
| server/bot/test_handled_messages.js | 合规 | §7 | 批6 合规 | 批6 |
| server/config.example.json | 保留 | 全部 | 未匹配批次规则,人工复核项 | - |
| server/deploy/README.md | 保留 | 全部 | 未匹配批次规则,人工复核项 | - |
| server/deploy/atomic_json.js | 合规 | §6 | wx+rename 正面样板 | 批6 |
| server/deploy/auto_login.py | 已改 | §4 | 7 处吞异常裁决注释(std-11,含计划外 :679 文件锁 __exit__);时间口径=运维允许类 | std-11-autologin-comments.patch;批6 |
| server/deploy/campus-autologin.service | 合规 | §5 | 轮转/单元配置合规(weekly/rotate 8/5M) | 批6 J5.2 |
| server/deploy/campus-autologin.timer | 合规 | §5 | 轮转/单元配置合规(weekly/rotate 8/5M) | 批6 J5.2 |
| server/deploy/campus-login.service | 合规 | §5 | 轮转/单元配置合规(weekly/rotate 8/5M) | 批6 J5.2 |
| server/deploy/deploy.sh | 合规 | §6 | 占位符模板 | 批6 |
| server/deploy/grab_signup.py | 保留 | §3/§4 | F-08/09/10/11 已记(涉行为,需真实回包);:746 已补注释(std-12);:721 有注释无限窄 | 批6;std-12-server-comments.patch;轮1 |
| server/deploy/legacy/README.md | 保留 | 全部 | 未匹配批次规则,人工复核项 | - |
| server/deploy/legacy/install_nginx_http_route.py | 保留 | §6 | 同上 | 批6 豁免记录 |
| server/deploy/legacy/install_nginx_route.py | 保留 | §6 | 直写;legacy/README 明示已停用备查,豁免 | 批6 豁免记录 |
| server/deploy/logrotate/campus | 合规 | §5 | 轮转/单元配置合规(weekly/rotate 8/5M) | 批6 J5.2 |
| server/deploy/make_template.sh | 合规 | §5/§6 | 占位符模板 | 批6 |
| server/deploy/remote_install.sh | 合规 | §5/§6 | env 注入,占位符 | 批6;轮1 密钥治理 |
| server/deploy/server_refresh.js | 已改 | §4/§6 | :87/:90 evaluate 内回退补裁决注释(std-13,tokenWorks 下游核验已实读);atomic_json 全量使用 | std-13-server-js-comments.patch;批6 |
| server/deploy/set_credentials.py | 合规 | §6 | os.replace | 批6 |
| server/deploy/sync_token.sh | 已改 | §6 | :28 机器特定 <用户目录> 绝对路径→参数化+command -v 兜底(std-6) | std-6-server.patch;批6 V9 |
| server/deploy/test_atomic_json.js | 保留 | 全部 | 未匹配批次规则,人工复核项 | - |
| server/requirements.txt | 保留 | 全部 | 未匹配批次规则,人工复核项 | - |
| server/scripts/activity_watch.py | 合规 | §1/§2/§3/§4/§5/§6 | 批6 扫描:business_now 注入/原子写/指纹化/命名合规 | 批6 判据命令 |
| server/scripts/card.py | 合规 | §1/§2/§3/§4/§5/§6 | 批6 扫描:business_now 注入/原子写/指纹化/命名合规 | 批6 判据命令 |
| server/scripts/common.py | 合规 | §1/§2/§3/§4/§5/§6 | 批6 扫描:business_now 注入/原子写/指纹化/命名合规 | 批6 判据命令 |
| server/scripts/dev/README.md | 保留 | 全部 | 未匹配批次规则,人工复核项 | - |
| server/scripts/dev/explore.py | 合规 | §1/§2/§3/§4/§5/§6 | 批6 扫描:business_now 注入/原子写/指纹化/命名合规 | 批6 判据命令 |
| server/scripts/dev/probe_login.py | 合规 | §1/§2/§3/§4/§5/§6 | 批6 扫描:business_now 注入/原子写/指纹化/命名合规 | 批6 判据命令 |
| server/scripts/dev/push_card.py | 合规 | §1/§2/§3/§4/§5/§6 | 批6 扫描:business_now 注入/原子写/指纹化/命名合规 | 批6 判据命令 |
| server/scripts/fetch.py | 保留 | §6 | latest.md/latest.json 直写无原子替换(V5,P3):撕裂风险低(latest.json 无消费方) | 批6 V5 |
| server/scripts/grab_card.py | 保留 | §3 | :64/79 F-09 已记;:108 同链 | 批6;轮1 |
| server/scripts/login.py | 已改 | §4 | :89 截图吞补裁决注释(std-12) | std-12-server-comments.patch;批6 |
| server/scripts/net_probe.py | 合规 | §1/§2/§3/§4/§5/§6 | 批6 扫描:business_now 注入/原子写/指纹化/命名合规 | 批6 判据命令 |
| server/scripts/notify.py | 已改 | §4 | :325/:350 吞异常裁决注释(std-12);token 缓存直写(V4,P3)仍保留涉写盘行为 | std-12-server-comments.patch;批6 |
| server/scripts/query.py | 保留 | §3 | :115 naive now 进 classify(V2):改 business_now 涉行为,需服务器回归,保留 | 批6 V2 |
| server/scripts/regress.py | 合规 | §1/§2/§3/§4/§5/§6 | 批6 扫描:business_now 注入/原子写/指纹化/命名合规 | 批6 判据命令 |
| server/scripts/remind.py | 保留 | §3 | :40 naive now(V3):同上保留 | 批6 V3 |
| server/scripts/render.py | 合规 | §1/§2/§3/§4/§5/§6 | 批6 扫描:business_now 注入/原子写/指纹化/命名合规 | 批6 判据命令 |
| server/scripts/run.py | 合规 | §1/§2/§3/§4/§5/§6 | 批6 扫描:business_now 注入/原子写/指纹化/命名合规 | 批6 判据命令 |
| server/scripts/scan.py | 合规 | §1/§2/§3/§4/§5/§6 | 批6 扫描:business_now 注入/原子写/指纹化/命名合规 | 批6 判据命令 |
| server/scripts/selfcheck.py | 合规 | §1/§2/§3/§4/§5/§6 | 批6 扫描:business_now 注入/原子写/指纹化/命名合规 | 批6 判据命令 |
| server/scripts/site_target.py | 合规 | §1/§2/§3/§4/§5/§6 | 批6 扫描:business_now 注入/原子写/指纹化/命名合规 | 批6 判据命令 |
| server/scripts/token_probe.py | 合规 | §1/§2/§3/§4/§5/§6 | 批6 扫描:business_now 注入/原子写/指纹化/命名合规 | 批6 判据命令 |
| server/scripts/token_report.py | 保留 | §6 | :194 报告直写(V6,P3) | 批6 V6 |
| server/scripts/trigger_server.py | 合规 | §1/§2/§3/§4/§5/§6 | 批6 扫描:business_now 注入/原子写/指纹化/命名合规 | 批6 判据命令 |
| server/scripts/watchlist.py | 保留 | §3/§4 | :126 F-09 已记;_refresh_card 私有跨模块灰区(J2.4) | 批6;轮1 F-09 |
| server/scripts/watchlist_runner.py | 保留 | §3 | :137 naive now 进排班/错过判定(V1):同上保留 | 批6 V1 |
| server/tests/test_activity_watch.py | 已改 | §7 | :4 注释 <tmp>→gettempdir 口径(std-6) | std-6-server.patch;批6 V12 |
| server/tests/test_dedup.py | 保留 | 全部 | 未匹配批次规则,人工复核项 | - |
| server/tests/test_endpoints.py | 保留 | 全部 | 未匹配批次规则,人工复核项 | - |
| server/tests/test_grab_signup_retry.py | 合规 | §7 | 夹具走 gettempdir(轮1 Fix A) | 批6;轮1 |
| server/tests/test_login_resilience.py | 保留 | 全部 | 未匹配批次规则,人工复核项 | - |
| server/tests/test_notify.py | 保留 | 全部 | 未匹配批次规则,人工复核项 | - |
| server/tests/test_runtime_safety.py | 已改 | §7 | :8 注释 <tmp>→gettempdir 口径(std-6) | std-6-server.patch;批6 V12 |
| server/tests/test_watchlist_safety.py | 合规 | §7 | 同上 | 批6;轮1 |
| tools/qa_business_clock_worker.py | 已改 | §6 | :14 docstring <tmp>→%TEMP% 口径(std-7) | std-7-tools.patch;批7 P3-1 |
| tools/qa_runtime_reliability.py | 已改 | §4/§6 | :310/:2985 清理吞补注释(std-7);外呼零容忍+固定锚点为正面样板 | std-7-tools.patch;批7 P3-3/4 |
| tools/release.py | 合规 | §2/§3/§4/§5/§8 | 发布门禁链为正面样板;built_at/created=J3.2d;manifest 非原子但 publish 双核验兜住 | 批7 台账 |
| tools/split_branches.py | 已改 | §5 | run() 失败输出经 _redact 打码远端 URL 凭证段(std-19,端到端实测 no-secret);:112 时间戳=J3.2d | std-19-splitbranches-redact.patch;批7 P3-6 闭环 |
| tools/verify_autologin_loop.py | 已改 | §4/§6 | :82-83 宽 except→窄(OSError,subprocess.SubprocessError)+注释(std-7) | std-7-tools.patch;批7 P3-2 |

## 未改说明汇总

- **保留(服务器侧行为类)**:V1-V3 naive now、F-08/09/10/11、bot.js :123 users.json 直写、auto_login :679 收口——全部涉行为且无服务器真实回归能力,待排期(DEFERRED/RISK)。注释级部分已在批 10-13 补齐。
- **保留(条款 r5)**:条款入口路径+直发清理=C8/B9 用户已拍板待排期。
- **保留(其余未做)**:fetch/token_report/notify V4 原子写与 bot.js :123 直写(涉服务器行为)、phone_session_store TTL 时钟(意见性)、gui.py 整体(B7 待删)。
- **保留(历史/归档)**:decisions/evidence/archive/superpowers/proposals 按 J8.3 不追改。
- **质检**:33 处吞异常批注经独立质检员全查 0 不符(26 相符/7 措辞修正已落 std-15a/15b);armedAt 清理经契约测试自证(该字段本就在禁用清单)。
- **N/A**:原型基准物、图像资产、样式表、契约样例 JSON、启动器与依赖清单。

---

## 提交映射(2026-11-05 07:3x,用户授权后落库;099ded3..HEAD 共 25 笔,均未 push)

099ded3=收第一轮五修。其后 25 笔 std 提交(sha 前缀):C1 批1 cbed58d(§4)/C2 批2+15b c96b7a9(§4)/C3 批3+15b d7a40fd(§4)/C4 批4a 6585135(§4)/C5 批4b 089d283(§4)/C6 批16 883598e(§2)/C7 批5+18b 96d45f5(§7/§2)/C8 批6 2c706b2(§6/§7)/C9 批7 8bf59c2(§4/§6)/C10 批8a afb0c90(§8)/C11 批8b f9cf949(§8)/C12 批8c 09e48fe(§8)/C13 批8d 08cd1a7(§8)/C14 批9a+15a 9cb1613(§4)/C15 批9b+15b c7bac98(§4)/C16 批10 253197e(§4)/C17 批11 d0e8f94(§4)/C18 批12 f82b715(§4)/C19 批13 1650301(§4/§5)/C20 批17 3f9fea1(§8)/C21 批18a ef09a7b(§2)/C22 批18c 05ee3ad(§2)/C23 批19 90f4ca4(§5)/C24 衁遗 ad56a0d/C25 衁遗 189bf27(两笔为自查捕获的派单遗漏:plan_service/login_relay_service/test_updater 裁决注释、controllers/update.js 空 catch)。

混合文件入库方式:app.py/grab.py/app.js/refresh.js/plan.js/UI_SPEC/copywriting 为选择性暂存或重建法(HEAD+本轮替换对),存量 hunk 一律未入;泄漏抽查 0 命中(help() 文案、用词表)。**assistance-panels.md §3 状态表重写与存量 3 行纠缠,唯一跳过项**,随存量留工作区。

不入库(工作区保留,均有前提):relogin.js(存量 N1+Fix E+:74 批注)、update.js(存量文案重写+Fix D 渲染)、test_ui_contract 的 Fix E 用例、test_application_services/test_phone_ui 的 Fix A 遗留 hunk、27 项存量本体。分支 tip(189bf27)独立验证:1682 例恰 2 红且均已归因(test_mobile_layout_statics <tmp> 遗留 hunk 未入库 + F-30 HEAD 固有);工作树全量 1699 OK/122/37+8。

## 未完成项清单(全部有前提,非遗漏)

| # | 项 | 前提 | 归属 |
|---|---|---|---|
| 1 | server 行为类:F-08(4001 口径)/F-09~F-10(时区与连击)/F-11(is_joined 三态)/V1-V3(naive now 进判定链)/V4-V7(原子写)/bot.js:123 | 服务器真实回归能力 | DEFERRED/RISK |
| 2 | 条款 r5:入口路径+「直发→直接提交」清理 | 用户拍板排期(B9/C8),升版触发重新同意 | DEFERRED |
| 3 | gui.py 删除 | B7 决定(与 B5 重做流程绑定) | DEFERRED |
| 4 | BL-1 v1.1.1 远端追溯 | GitHub Release 侧证据(需网络授权) | BACKLOG |
| 5 | assistance-panels §3 表重写入库 | 与存量 3 行纠缠,随存量提交后自然入库 | 工作区 |
| 6 | relogin.js/update.js/Fix A 遗留 hunk/Fix E 用例入库 | 依赖存量 N1/文案重写先行提交 | 工作区 |
| 7 | docs/UI_SPEC:122 直发登记句同步 | 依赖第 2 项完成后更新 | DEFERRED |
| 8 | phone_session_store TTL 时钟/business_clock 读放大 | 意见性,无行为问题 | 记录 |
