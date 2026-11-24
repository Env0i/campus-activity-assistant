# 界面翻新原型截图证据（2026-11-24）

- **日期**：2026-11-24
- **来源原型**：[design/prototype/workbench-2026-11/](../../../prototype/workbench-2026-11/README.md)（共留存 **59 张** PNG：27 张本轮新增画板 + 32 张受影响既有画板重截；同日复核调整后全部按原尺寸重截）
- **状态/文案基线来源**：列表分组与状态判定对照 [local/ui/state/filters.js](../../../../local/ui/state/filters.js)、[local/ui/views/list.js](../../../../local/ui/views/list.js)、[local/ui/features/shell/view-banners.js](../../../../local/ui/features/shell/view-banners.js)；精简前后文案核对自 `local/ui/features/**`、`local/ui/m/**` 与 [design/specs/copywriting.md](../../../specs/copywriting.md)。

## 复现方式

在仓库根目录启动本地原型服务并使用无头 Edge 按 `canvas.json` 对应画板尺寸截图（示例为 `1280×800`）：

```powershell
python -m http.server 8790 --bind 127.0.0.1 --directory design/prototype/workbench-2026-11
"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe" --headless=new --disable-gpu --hide-scrollbars --user-data-dir="%TEMP%\edge-prof" --window-size=1280,800 --virtual-time-budget=6000 --screenshot="design/evidence/2026-11-24/ui-refresh/TimelineWide.png" "http://127.0.0.1:8790/TimelineWide.dc.html"
```

（注：Windows 下 Edge 无头窗口有最小窗口宽度限制，窄档 `430×900` 与手机页 `390×844` 画板内嵌原型容器仍严格按 `430px` / `390px` 渲染。）

## 新增画板清单（27 张）

| 截图文件名 | 覆盖事项 | 画板尺寸 |
|---|---|---|
| `TimelineWide.png` | 时间轴竖线 + 4 层卡片 + 类型标签（宽档） | 1280×800 |
| `TimelineFilters.png` | 更多筛选内「活动类型」多选标签 | 1280×800 |
| `TimelineCompact.png` | 1040px 宽窄临界（第 3 层一行四格不裁时间） | 1040×800 |
| `TimelineMed.png` | 中档两行两格第 3 层 + 底部停靠条 | 900×800 |
| `TimelineNarrow.png` | 窄档时间轴 + 两行两格第 3 层 | 430×900 |
| `TimelineShort.png` | 矮窗口时间轴与短点阵盘 | 1280×600 |
| `PhoneTimeline.png` | 手机页时间轴 + 类型标签 + 两行两格卡片 | 390×844 |
| `DescNormal.png` | `?` 详情浮层：标题是活动名，关键事实在前，面向范围按年级/分公司拆行并折叠 | 1280×800 |
| `DescLong.png` | `?` 详情浮层：长简介限高 + 「展开全文」 | 1280×800 |
| `DescEmpty.png` | `?` 详情浮层：学校未提供活动简介 | 1280×800 |
| `DescFail.png` | `?` 详情浮层：简介同步失败 + 重试 | 1280×800 |
| `NarrowDesc.png` | 窄窗口 `?` 详情浮层 | 430×900 |
| `DescScope.png` | `?` 详情浮层：面向范围代码不认识时原样显示文字 | 1280×800 |
| `LoginStepTwo.png` | 失效后自动登录：还差 2 步 | 1280×800 |
| `LoginStepCred.png` | 失效后自动登录：还差保存账号密码 | 1280×800 |
| `LoginStepOcr.png` | 失效后自动登录：还差安装验证码识别 | 1280×800 |
| `LoginStepEnable.png` | 失效后自动登录：组件已装待点「启用」 | 1280×800 |
| `LoginStepReady.png` | 失效后自动登录：两步均就绪 | 1280×800 |
| `LoginStepBadPwd.png` | 失效后自动登录：保存密码失效提示 | 1280×800 |
| `ProgCard.png` | 设置「程序」组统一一张卡（含展开飞书提醒） | 1280×800 |
| `ListSkel.png` | 首次加载时间轴骨架屏 | 1280×800 |
| `ListRefreshing.png` | 有数据时刷新：保留旧行 + 顶部进度条 + 刷新中 | 1280×800 |
| `ListRefreshFail.png` | 刷新失败：保留旧列表，列表上方一行提示带「重试」，不占全局横幅 | 1280×800 |
| `TopTransitions.png` | 顶栏四类状态切换规范展示（180ms / 1.5s） | 1280×800 |
| `BannerNotice.png` | 一次性通知横幅（「知道了」） | 1280×800 |
| `BannerCollapse.png` | 持续告警横幅「收起」后顶栏留状态提示点 | 1280×800 |
| `BannerInlineClose.png` | 设置内联状态提示带 `×` 关闭钮 | 1280×800 |

## 受影响既有画板重截清单（32 张）

- **列表与响应档位**：`Main.png`、`Narrow.png`、`Short.png`、`ConflictTip.png`、`CrossDay.png`、`CancelAsk.png`
- **设置与凭据**：`Settings.png`、`NarrowSettings.png`、`AdvCheck.png`、`CredForm.png`、`CredSaved.png`、`UpdateAvail.png`、`TermsWithdraw.png`
- **空态与横幅**：`ListErr.png`、`ZeroAct.png`、`NoResult.png`、`Slept.png`、`TermsOff.png`、`Broken.png`、`SecondRun.png`、`Migrated.png`
- **文案更新重截（含桌面弹窗与手机页）**：`FirstUse.png`、`HelpKeys.png`、`Running.png`、`Result.png`、`CloseAsk.png`、`Phone.png`、`PhoneApp.png`、`PhonePick.png`、`PhoneConflict.png`、`PhoneRun.png`、`PhoneResult.png`

## 同日复核调整（重截全部画板）

执行方画完后由审阅方复核视觉与一致性，直接改原型后全部重截。改了这些：

- **卡片**：类型标签从第一层移到第二层开头，改成不带框的小方点文字，第一层只留奖励；学分和工资合成一枚标签；四格改固定列宽，各卡片对齐；中档（1180px 以下）四格改两行；卡片内日期统一 `11-03` 短式。
- **颜色**：倒计时默认中性灰，只有下一批和 10 分钟内用琥珀；选中态底色减淡；「现在」线改细橙线加浅橙标签，不再用黑条。
- **第四层提示**：时间重叠改琥珀底一条；新增「电脑在 HH:MM 开放时睡着了，没有提交」淡红一条（`Slept.png`）。
- **窄档与手机页**：时刻从左侧窄栏挪到节点上方一行，竖线贴左，卡片拿回整行宽度；第二层不换行，截止时间放不下时省略。
- **简介浮层**：标题用活动名，副标题是类型和分组；活动时间、地点、报名时间、面向范围在简介正文前面。
- **其他**：刷新失败改成列表上方一行提示；登录清单第 2 步按钮改次要样式「去安装」，避免和高级功能卡的主按钮重复；收起的时钟胶囊改写「北京时间待校准」；17 条精简文案改回口语（见 [copy-simplification.md](../../../proposals/copy-simplification.md) 原则 4）。
