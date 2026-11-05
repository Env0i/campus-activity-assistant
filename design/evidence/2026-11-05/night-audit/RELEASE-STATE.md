# RELEASE-STATE — L5 发布口径三态核对(2026-11-05 夜审计)

核对范围:`VERSION`、`CHANGELOG.md`、`design/specs/versioning-and-release.md`、`README.md`、git tag 状态。核对方式:直接读文件 + git 命令,全部可复现。

## 一、三态逐项(M=3,逐条有结论)

### 态 1:当前候选(1.2.0)

- `VERSION` = `1.2.0`(实测读文件)。
- `CHANGELOG.md` 顶部为「## 1.2.0(待发布:可选手机控制、电脑续登录与条款改版)」,且自带免责声明「自动化验证、既有用户验收与真实发布分开记录」。
- `versioning-and-release.md` :30 的版本规则(累计功能增强 → minor +1 → 1.2.0)与 1.2.0 内容一致。
- **判定:已验——VERSION 与 CHANGELOG 一致,1.2.0 处于"待发布候选"状态,三态自洽。【已复现】**

### 态 2:上一个正式版(v1.1.1)可追溯性

- CHANGELOG 将 1.1.1 标注为「已发布:…」并声明「本版本已发布到 GitHub Release」。
- 本机 `git tag | wc -l` = **0**(实测)。
- versioning-and-release.md :35-52 自述:Release tag 必须显式绑定已核验提交、tag 就是让那个 commit 可达的锚点;:78 记录「历史预览(含 v1.1.1 预览)不能改名复用」。
- **判定:任务书预告的结论成立——本机无任何 tag,v1.1.1 的"已发布"声明在本仓库内不可追溯,该条只能记【blocked】(需 GitHub Release 侧证据,本次审计无网络授权,不访问)。【已复现(本地侧)】+ blocked**

### 态 3:发布规则文档自洽性

- versioning-and-release.md :12 基线表「当前正式版本 v1.1.1」——按"最后已发布版本"口径成立(1.2.0 未发布)。
- 同文 :55-57 引用「v1.2.0 的 manifest 写的 commit 在本仓库历史里查不到(2026-11-03 记录)」——这是 GitHub 外部事实,本审计无网络授权核验,记【无法验证】;该句与 :12 基线表并存不构成规则冲突,但构成"文档同时引用两个版本事实"的观感不一致。
- `README.md` :77「当前正式版本为 1.1.1」(成立)与 :256「版本仍为未发布 1.1.1 候选」(**漂移**:与 VERSION=1.2.0、CHANGELOG 1.1.1 已发布 矛盾,属旧文案残留)。【已复现(读文件)】
- **判定:规则本体自洽;README:256 一处漂移。**

## 二、结论汇总

| 项 | 结论 | 三态 |
|---|---|---|
| VERSION=1.2.0 ↔ CHANGELOG 待发布 | 一致 | 已复现 |
| v1.1.1 已发布声明 | 本机不可追溯(tag=0),**记 blocked**,需 GitHub 侧证据 | 已复现(本地)/无法验证(远端) |
| versioning spec 规则本体 | 与发布纪律一致(唯一来源/显式绑 tag/授权边界) | 已复现(经 test_lifecycle_release.py:98/:207/:178/:216/:223/:234 钉住,L3 交叉确认) |
| v1.2.0 manifest commit 存在性 | 无法核验(外部事实,无网络授权) | 无法验证 |
| README:256 版本候选口径 | 漂移(建议改为"1.2.0 待发布"或删除该句;发布声明属产品口径,**未擅自改动**,记 DEFERRED) | 已复现 |
| 发版脚本 release.py | check/prepare/publish 契约被 test_lifecycle_release 钉住,check 默认只读 | 已复现(L3) |

## 三、今晚不动发布口径的说明

VERSION/CHANGELOG/README 的版本声明属发布口径,改动即对外承诺变化;本审计只记录漂移与 blocked,不做任何版本号/声明改动(与「未经授权不提交」同源的最小可逆原则)。建议动作清单见 DEFERRED.md。
