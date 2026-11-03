# 文档索引

## 现行工程文档

| 文档 | 适合谁看 | 内容 |
|------|----------|------|
| [../README.md](../README.md) | 第一次接触项目 | 功能、快速开始、两版怎么选、常见问题 |
| [FEISHU_BOT.md](FEISHU_BOT.md) | 第一次配飞书 | 群机器人 vs 自建应用、权限、事件订阅、拿 chat_id/open_id、错误码对照 |
| [CONFIG.md](CONFIG.md) | 要填配置的人 | config.json 全字段、13 个环境变量、三套可抄示例、配置类故障 |
| [ARCHITECTURE.md](ARCHITECTURE.md) | 要改代码的人 | 数据流、模块职责、接口清单、去重与推送节奏、告警链路 |
| [OPERATIONS.md](OPERATIONS.md) | 日常运维 | 服务器布局、systemd、crontab、日志、部署更新、回滚、故障处理、迁移记录 |
| [LOGIN.md](LOGIN.md) | 处理登录态问题 | token 寿命实测、守护进程续期、验证码 OCR 无人值守登录、凭据管理、人工兜底 |
| [GRAB.md](GRAB.md) | 预报名/抢报名 | 状态机、时间线、卡片快照、边界 |
| [RETRY_POLICY_GUIDE.md](RETRY_POLICY_GUIDE.md) | 普通使用者（图解） | 报名截止硬上限、重试时长/次数怎么选、「第 N 次提交」计数、八种终态，Mermaid 时间线一看就懂 |
| [TIMING_AND_DEDUP_ANALYSIS.md](TIMING_AND_DEDUP_ANALYSIS.md) | 想理解"为什么是这个时点/这套去重" | 完整推导与请求量账本 |
| [UI_SPEC.md](UI_SPEC.md) | 改界面、接界面的人 | 本机版界面任务书与实现契约（§5 是事件与字段契约） |
| [PHONE_ACCESS.md](PHONE_ACCESS.md) | 改手机页、查手机访问问题的人 | 手机受限访问：可选高级功能、默认关闭、8 项操作、重登 |
| [USER_AGREEMENT.md](USER_AGREEMENT.md) | 想看协议原文 | 用户协议（程序内同一版本号） |
| [PRIVACY_POLICY.md](PRIVACY_POLICY.md) | 想看隐私政策原文 | 隐私政策（程序内同一版本号） |

## 现行设计稿（superpowers/specs/）

已获批准的设计稿，实现计划和验收都以它们为准：

| 设计稿 | 内容 |
|------|------|
| [superpowers/specs/2026-10-31-phone-access-channel-design.md](superpowers/specs/2026-10-31-phone-access-channel-design.md) | 手机访问通道与组件分发设计 |
| [superpowers/specs/2026-11-02-workbench-ui-redesign-design.md](superpowers/specs/2026-11-02-workbench-ui-redesign-design.md) | 本机版新工作台与手机页重做设计 |
| [superpowers/specs/2026-11-03-architecture-revision-design.md](superpowers/specs/2026-11-03-architecture-revision-design.md) | 报名链路、登录态与服务器版的架构修订设计 |

## 归档

### archive/

历史文档，保留备查，**内容可能已过时**：

| 文档 | 说明 |
|------|------|
| [archive/README-full-20261022.md](archive/README-full-20261022.md) | 重构前的完整 README（752 行，含大量实现细节与平台配置） |
| [archive/BUILD_FROM_SCRATCH.md](archive/BUILD_FROM_SCRATCH.md) | 从零搭建指南（旧流程，服务器路径已变） |
| [archive/WORKBUDDY_LOGIN_PROMPT.md](archive/WORKBUDDY_LOGIN_PROMPT.md) | 早期交给云端助手的登录恢复提示词 |
| [archive/ASK_CODEX_REVIEW.md](archive/ASK_CODEX_REVIEW.md) / [archive/REVIEW_PROMPT.md](archive/REVIEW_PROMPT.md) | 代码评审用的提问清单 |
| [archive/UI_DESIGN.md](archive/UI_DESIGN.md) | 报名时间队列的早期设计（设计归档，实际字段以 UI_SPEC.md 为准） |

### archive/process/

已完成的计划、交接、发现清单和讨论材料，按日期分组，**只是过程记录，不是现行规则**。
说明和文件清单见 [archive/process/README.md](archive/process/README.md)。

## 路径迁移对照表（2026-11-03）

2026-11-03 整理项目文件夹时挪过的文件，旧路径 → 新路径，一行一个。仓库内的引用已全部改到新路径，
这张表给仓库外的旧记忆、旧计划、旧聊天记录查路径用。只写文件名、没带目录的提法
（比如 CHANGELOG 里的 `build_exe.py`）没有改，文件名本身没变。

| 旧路径 | 新路径 |
|------|------|
| `local/build_advanced.py` | `local/build/build_advanced.py` |
| `local/build_exe.py` | `local/build/build_exe.py` |
| `local/build_installer.py` | `local/build/build_installer.py` |
| `local/make_portable.py` | `local/build/make_portable.py` |
| `local/1-登录.bat` | `local/launchers/1-登录.bat` |
| `local/2-抢活动.bat` | `local/launchers/2-抢活动.bat` |
| `local/3-检查登录和活动.bat` | `local/launchers/3-检查登录和活动.bat` |
| `local/4-图形界面.bat` | `local/launchers/4-图形界面.bat` |
| `local/_py.bat` | `local/launchers/_py.bat` |
| `local/install.bat` | `local/launchers/install.bat` |
| `local/启动不了点我.txt` | `local/launchers/启动不了点我.txt` |
| `local/遇到问题先看我.txt` | `local/launchers/遇到问题先看我.txt` |
| `docs/superpowers/discuss/2026-10-30-phone-access-channel.md` | `docs/archive/process/2026-10-30/discuss/2026-10-30-phone-access-channel.md` |
| `docs/superpowers/findings/2026-10-31-ui-findings.md` | `docs/archive/process/2026-10-31/findings/2026-10-31-ui-findings.md` |
| `docs/superpowers/handoff/2026-10-31-codex-handoff-group2.md` | `docs/archive/process/2026-10-31/handoff/2026-10-31-codex-handoff-group2.md` |
| `docs/superpowers/handoff/2026-10-31-mobile-ui-handoff.md` | `docs/archive/process/2026-10-31/handoff/2026-10-31-mobile-ui-handoff.md` |
| `docs/superpowers/handoff/2026-10-31-phone-access-handoff.md` | `docs/archive/process/2026-10-31/handoff/2026-10-31-phone-access-handoff.md` |
| `docs/superpowers/plans/2026-10-30-phone-access-channel.md` | `docs/archive/process/2026-10-30/plans/2026-10-30-phone-access-channel.md` |
| `docs/superpowers/plans/2026-10-30-phone-ui-failure-repair.md` | `docs/archive/process/2026-10-30/plans/2026-10-30-phone-ui-failure-repair.md` |
| `docs/superpowers/plans/2026-10-31-phone-access-channel-redesign.md` | `docs/archive/process/2026-10-31/plans/2026-10-31-phone-access-channel-redesign.md` |
| `docs/superpowers/plans/2026-10-31-phone-access-repair-followup.md` | `docs/archive/process/2026-10-31/plans/2026-10-31-phone-access-repair-followup.md` |
| `docs/superpowers/plans/2026-10-31-phone-access-repair.md` | `docs/archive/process/2026-10-31/plans/2026-10-31-phone-access-repair.md` |
| `docs/superpowers/plans/2026-10-31-phone-control-release-publication-repair.md` | `docs/archive/process/2026-10-31/plans/2026-10-31-phone-control-release-publication-repair.md` |
| `docs/UI_DESIGN.md` | `docs/archive/UI_DESIGN.md` |
| `docs/acceptance/ACCEPTANCE-20261031.md` | `design/evidence/2026-10-31/ACCEPTANCE-20261031.md` |
| `docs/acceptance/UI-SPEC9-AND-D-STATUS-20261031.md` | `design/evidence/2026-10-31/UI-SPEC9-AND-D-STATUS-20261031.md` |
| `design/current-ui/README.md` | `design/archive/current-ui-2026-10-25/README.md` |
| `design/prototype/app.html` | `design/archive/prototype-2026-10-22/app.html` |
| `design/prototype/app/app.css` | `design/archive/prototype-2026-10-22/app/app.css` |
| `design/prototype/app/app.js` | `design/archive/prototype-2026-10-22/app/app.js` |
| `design/prototype/app/led.js` | `design/archive/prototype-2026-10-22/app/led.js` |
| `design/prototype/components.html` | `design/archive/prototype-2026-10-22/components.html` |
| `design/prototype/index.html` | `design/archive/prototype-2026-10-22/index.html` |
| `design/prototype/play.html` | `design/archive/prototype-2026-10-22/play.html` |
| `design/prototype/proto/mock-backend.js` | `design/archive/prototype-2026-10-22/proto/mock-backend.js` |
| `design/prototype/proto/play.css` | `design/archive/prototype-2026-10-22/proto/play.css` |
| `design/prototype/proto/play.js` | `design/archive/prototype-2026-10-22/proto/play.js` |
| `design/prototype/proto/sheet.css` | `design/archive/prototype-2026-10-22/proto/sheet.css` |
| `design/prototype/proto/shoot.py` | `design/archive/prototype-2026-10-22/proto/shoot.py` |
