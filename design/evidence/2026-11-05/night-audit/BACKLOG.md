# BACKLOG — 卡住项(同一问题 2 轮未解,第 3 轮入此)(2026-11-05 夜审计)

按任务书机制,本文件记录"试了 2 轮仍卡住"的问题。本次审计**没有**触发该机制的项:五层全部有结论,修复链 A–E 全部一次通过。

唯一按任务书预告直接记 blocked(而非"试 2 轮卡住")的项:

## BL-1 v1.1.1 已发布声明不可追溯
- **现象**:CHANGELOG 标 1.1.1「已发布」,本机 `git tag | wc -l` = 0,本地无任何锚点。
- **试过什么**:git tag(0)、git for-each-ref refs/tags(空)、CHANGELOG/versioning spec 全文检索——本地侧证据已穷尽。
- **需要什么**:GitHub Release 侧证据(Release 列表/manifest/资产 SHA-256),需要网络授权后用 `gh release view` 或仓库 Releases 页核对;本次任务书禁止访问外部资源,故只能 blocked。
- **影响**:RELEASE-STATE.md 态 2;不阻塞其他结论。

## 第二轮(2026-11-05)增补:零新增 blocked
本轮 8 个目录批 + 根级补充批 9a/9b + docs 四子批全部一次通过,无触发「同一处卡两轮」机制的项。第一轮 BL-1(v1.1.1 远端追溯)仍未解除,仍需 GitHub 侧证据。

## 续作终态增补(2026-11-05 05:35)
- 批 18a-c(TestWallClock→WallClockStub,8 文件 65 处,计数守恒)与批 19(split_branches 失败输出 URL 凭证脱敏,端到端实测 no-secret)完成。至此**保留集内所有零行为变化项已清零**;剩余保留项全部带前提:服务器行为类需真实回归、条款 r5 待排期(C8/B9)、gui.py 待 B7、BL-1 需 GitHub 证据。
- armedAt 5 处删除经出处核验为 HEAD 死码(非用户未提交工作),std-16 patch 可完整恢复。
- 存量完整性终检通过:_map_activity/reloginSucceeded/_join_state/reloginRefreshedFlow/TOUR_STEPS/result.text 透传全部在位——用户 27 项未提交工作无一被标准批次破坏。
