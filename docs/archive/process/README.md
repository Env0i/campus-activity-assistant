# 过程记录（已完成的计划、交接、发现、讨论）

> 这里放的是**已经做完**的工作过程：当时的实施计划、交接说明、问题清单、讨论材料。
> 它们只是过程记录，**不是现行规则**——里面的口径、路径、数字可能已被后来的实现取代，
> 引用前以现行文档和代码为准。

## 现行规则去哪看

| 想知道 | 去看 |
|---|---|
| 产品为什么这样定、用户看到什么 | [design/decisions/](../../../design/decisions/) |
| 字段、接口、验收标准 | [docs/](../../README.md) 里的 `UI_SPEC.md`、`ARCHITECTURE.md` 等 |
| 现行设计稿 | [docs/superpowers/specs/](../../superpowers/specs/) |
| 验收与取证记录 | [design/evidence/](../../../design/evidence/) |

## 怎么分组

按**文件名开头的日期**分目录：`<日期>/<类别>/<原文件名>`。类别沿用原来的子目录名：

| 类别 | 是什么 |
|---|---|
| `discuss/` | 讨论材料：方案取舍，交给别人定稿前的草稿 |
| `findings/` | 发现清单：审阅或验收时记下的问题 |
| `handoff/` | 交接：做到哪、卡在哪、下一步谁来接 |
| `plans/` | 实施计划：当时按它执行的任务拆分 |

这些文件 2026-11-03 整理前放在 `docs/superpowers/` 下的 discuss、findings、handoff、plans 四个子目录；
`docs/superpowers/` 现在只留 `specs/`（现行设计稿）。新旧路径对照见
[docs/README.md](../../README.md) 的「路径迁移对照表」。

## 2026-10-30

| 类别 | 文件 | 主题 |
|---|---|---|
| discuss | [2026-10-30-phone-access-channel.md](2026-10-30/discuss/2026-10-30-phone-access-channel.md) | 手机远程访问：通道分层与固定入口 |
| plans | [2026-10-30-phone-access-channel.md](2026-10-30/plans/2026-10-30-phone-access-channel.md) | 手机远程访问通道与持久会话 |
| plans | [2026-10-30-phone-ui-failure-repair.md](2026-10-30/plans/2026-10-30-phone-ui-failure-repair.md) | 手机帮助页与重登恢复失败修复 |

## 2026-10-31

| 类别 | 文件 | 主题 |
|---|---|---|
| findings | [2026-10-31-ui-findings.md](2026-10-31/findings/2026-10-31-ui-findings.md) | 手机页与桌面高级功能的 UI 问题记录 |
| handoff | [2026-10-31-codex-handoff-group2.md](2026-10-31/handoff/2026-10-31-codex-handoff-group2.md) | 组 2 卡在哪、这一轮改了什么 |
| handoff | [2026-10-31-mobile-ui-handoff.md](2026-10-31/handoff/2026-10-31-mobile-ui-handoff.md) | 手机页代码交接与不变量 |
| handoff | [2026-10-31-phone-access-handoff.md](2026-10-31/handoff/2026-10-31-phone-access-handoff.md) | 手机远程访问：执行结果与返修交接 |
| plans | [2026-10-31-phone-access-channel-redesign.md](2026-10-31/plans/2026-10-31-phone-access-channel-redesign.md) | 手机访问通道与组件分发 |
| plans | [2026-10-31-phone-access-repair-followup.md](2026-10-31/plans/2026-10-31-phone-access-repair-followup.md) | 手机访问返修与验收收口 |
| plans | [2026-10-31-phone-access-repair.md](2026-10-31/plans/2026-10-31-phone-access-repair.md) | 手机远程控制台与重登体验返修 |
| plans | [2026-10-31-phone-control-release-publication-repair.md](2026-10-31/plans/2026-10-31-phone-control-release-publication-repair.md) | 手机控制组件的发布与上传返修 |
