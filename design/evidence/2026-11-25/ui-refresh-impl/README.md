# 界面翻新实现阶段验收截图与核对记录（2026-11-25 返工定稿）

- **日期**：2026-11-25
- **基线提交**：`fed6a64`（分支 `feat/ui-refresh`）
- **原型基准**：[design/evidence/2026-11-24/ui-refresh/](../../2026-11-24/ui-refresh/README.md)

## 演示窗口与静态服务核对分工

1. **真实桌面壳冒烟（`python local/app.py --demo`）**：验证真实 pywebview 组合根与本地内存样例启动链路无报错拉起窗口（`--demo` 处于内存演示模式，不走已登录 + NTP 真实校准分支，且窗口有最小尺寸约束）。
2. **多态与窄档可复现截图（`scripts/capture_evidence.py`）**：在本地回环 HTTP 服务上托管真实的 [local/ui/index.html](../../../../local/ui/index.html) 与 [local/ui/m/index.html](../../../../local/ui/m/index.html)，通过脚本注入有效登录态（`已登录`）、已校准北京时间快照（`2026-11-06 13:55:00`，顶栏显示 `13:55:xx ✓`）、条款式确认及全场景样例数据，驱动系统 Edge（Playwright `channel="msedge"`）稳定复现 19 张截图，并在脚本内断言桌面与手机端零横向溢出、430px / 390px 第二层不换行与收起提醒点可见。

## 复现方式

在仓库根目录执行：

```powershell
python design/evidence/2026-11-25/ui-refresh-impl/scripts/capture_evidence.py
python local/app.py --demo
```

## 截图清单与原型对照（19 张）

| 截图文件名 | 覆盖状态与视口 | 与 2026-11-24 原型对照 |
|---|---|---|
| `TimelineWide.png` | 1280×800 宽档；已登录、`13:55:00 ✓`、`正在开放`、`现在 13:55`、`14:00 同抢 2 场`、10 分钟内 `4 分 59 秒` 琥珀倒计时、选中行、时间冲突 `不可加入`、已报名 `可取消至` 与右侧点阵 LED | 奖励合为单外框 + 1px 细竖线（K2）；时间轴节点、分组、颜色档与原型一致 |
| `TimelineCompact.png` | 1040×800 临界宽度（列表仍呈一行四格） | 与原型 `TimelineCompact` 一致，第三层无裁剪 |
| `TimelineMed.png` | 900×800 中档布局与底部停靠计划栏 | 与原型 `TimelineMed` 一致 |
| `TimelineNarrow.png` | ≤430px 列表容器窄档（时间轴顶置、奖励进第二层、`.filters { flex: none; }` 完整显示、`.l2-l > *` 零换行） | 修复 `.filters` 窄档纵向压缩裁剪后与原型 `TimelineNarrow` 一致 |
| `TimelineShort.png` | 1280×600 矮窗口紧凑布局 | 点阵屏与列表区自适应，无溢出 |
| `TimelineFilters.png` | 1280×800 更多筛选 + 活动类型并集多选（选中「创新创业」与已不在列表中的「往期保留类别」） | 按 K5 保留不在当前列表中的已选类型并可点击取消 |
| `DescNormal.png` | 1280×800 `#dlg-desc` 正常态（`audience_code=3` 分公司折叠 + `展开全部`） | 按用户反馈对齐原型 `Main.dc.html`：深色点阵头、琥珀左竖线、去聚焦框与去右上角 `×` |
| `DescLong.png` | 1280×800 长简介限高与「展开全文」 | 与原型 `DescLong` 一致 |
| `DescEmpty.png` | 1280×800 空简介回落「学校未提供活动简介」 | 与原型 `DescEmpty` 一致 |
| `DescFail.png` | 1280×800 未同步警告底 +「重新获取」按钮 | 与原型 `DescFail` 一致 |
| `DescScope.png` | 1280×800 未知面向范围代码原样展示 | 与原型 `DescScope` 一致 |
| `SettingsLoginTwo.png` | 1280×800 设置抽屉「失效后自动登录 · 还差 2 步」 | 与原型 `LoginStepTwo` 一致 |
| `SettingsProgCard.png` | 1280×800 设置程序组五项统一卡片（「只有点“检查更新”才联网，下载前会再问你。」） | 按 K3 定稿文案落地，飞书/条款行纵向对齐与原型 `ProgCard` 一致 |
| `ListRefreshing.png` | 1280×800 已有列表刷新中保留旧行 + 顶部进度条 + 计划栏「正在加载」 | 按 D7/K4 同步顶栏、列表、计划栏、LED 为一致加载反馈 |
| `ListRefreshFail.png` | 1280×800 刷新失败保留旧列表 + 内联「重试」提示栏 | 不占全局横幅，文案与原型 `ListRefreshFail` 一致 |
| `BannerNotice.png` | 1280×800 `second_open` 通知档横幅（含「知道了」按 K3 定稿文案） | 与原型 `BannerNotice` 一致 |
| `BannerCollapse.png` | 1280×800 持续类告警横幅（登录已失效 +「收起」） | 与原型 `BannerCollapse` 一致 |
| `BannerCollapsedDot.png` | 1280×800 点击「收起」后横幅隐藏且 `#pill` 挂 `collapsed-warn` 角标圆点 | 与原型及 K4 收起圆点契约一致 |
| `PhoneTimeline.png` | 390×844 手机端真实 `local/ui/m/index.html`（已连接、`13:55:00`、睡眠错过双句式、`同抢 2 场`、`4 分 59 秒` 琥珀与 L2 单行不换行） | 按 K2 统一手机端 `.l2-l` 不换行与睡眠错过句式，其余与原型 `PhoneTimeline` 一致 |
