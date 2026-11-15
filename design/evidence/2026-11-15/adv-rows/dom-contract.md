# 高级功能「一项一行」：元素去向表

依据：`design/prototype/workbench-2026-11/Main.dc.html` 的「高级功能」组模板（`section.set.adv-sec` 两段、`advHead`、`phView`、`ocrView`），以及计划里的状态与标题行对照表。下面两节按原型的分块写：`.adv-h`（标题行）、`.adv-bar`（进度条）、`.adv-n`（小字）、`.ph-err.adv-e`（红条）、`.adv-d`（展开区）。

规则：能保留 id 就保留、只换位置与样子；换不了的才删。删掉的只有三种——原型专门用状态句表达的（`#ocr-title-chip`、四个进度文字元素）、随 `.ph-slot` 一起消失的容器、合并进小字槽的元素。

## 一、手机访问（`section[aria-label="手机访问"]`）

| 现状元素 | 去向 | 依据 |
| --- | --- | --- |
| `section.help-tools.help-advanced.ph-sec` | 保留，类名换成 `help-tools adv-sec ph-sec` | 原型 `section.set.adv-sec`：一项一张卡 |
| `div.set-h` + `b` 手机访问 | 换成 `div.adv-h`，名称挪进 `.adv-t b` | 原型 `.adv-h` 第一段 |
| `span.ph-slot` | 删除（按钮直接进标题行按钮位） | 原型 `.adv-h` 里按钮是行内直接子元素 |
| — | 新增 `span.adv-ic` + 手机图标 svg | 原型 `.adv-ic` |
| `#phone-feature-status`（`span.ph-st`） | 保留 id，改成 `span.adv-s`：`<i>` 圆点 + `#phone-feature-status-text` 状态句；始终显示 | 原型 `.adv-s`「圆点 + 一句状态」 |
| `#btn-phone-feature-install` | 保留 id，挪进标题行按钮位；文字「启用手机控制」 | 原型 disabled 档 |
| `#btn-phone-component-install` | 保留 id，挪进标题行按钮位 | 原型「下载并安装 / 更新组件 / 重新安装 / 重新下载」 |
| `#btn-phone-component-cancel` | 保留 id，挪进标题行按钮位 | 原型「取消 / 校验中…」 |
| `#btn-phone-component-retry` | 保留 id，挪进标题行按钮位 | 原型 timeout、unreadable 两档的「重试」 |
| `#btn-phone-start` | 从 `#phone-off` 挪进标题行按钮位；文字「开启」/「重新开启」 | 原型 `ph off` 档的实心按钮 |
| `#btn-phone-stop` | 从 `#phone-on` 底部挪进标题行按钮位；文字「关闭手机访问」 | 原型 `ph on` 档的线框按钮 |
| — | 新增 `#btn-phone-row-toggle`（`button.adv-x`，`aria-expanded`、`aria-label`「收起/展开手机访问详情」） | 原型 `.adv-x` 箭头 |
| `#phone-probe` | 保留 id，改成 `.adv-n` 小字：读状态三种、需要更新、坏了、刚装好 | 原型 `.adv-n`、`advHead` 的 note |
| `#phone-loading`（`div.ph-block`） | 保留 id，改成标题行下的 `div.adv-bar`（`role="progressbar"`、`aria-valuenow`、内含 `#phone-prog-fill`） | 原型 `.adv-bar` |
| `#phone-prog-text` | 删除（状态句已经说了「下载中 x / y MB」，见 `advHead`） | 原型 `advHead` 的 downloading 档 |
| `#phone-prog-num` | 删除（同上） | 同上 |
| `#phone-component-progress` | 删除（`#phone-loading` 自己就是进度条容器） | 原型 `.adv-bar` |
| `#phone-prog-fill` | 保留 id（`.adv-bar > i`） | 原型 `.adv-bar i` |
| `#phone-component-error` | 保留 id，留在标题行下（`p.ph-err.adv-e`） | 原型 `advHead` 的 `hasErr` 红条 |
| — | 新增 `#phone-row-detail`（展开区容器 `div.adv-d`），默认展开 | 原型 `.adv-d`；手机默认展开 |
| `#phone-feature-note` | 进展开区（lead，随状态变的那句） | 原型 `phV.lead` |
| `#phone-feature-error` | 进展开区 | 原型 `phV.hasErr` 在展开区里的那条 |
| `#phone-import-line` | 进展开区（导入兜底） | 原型 `phV.canImport` |
| `#phone-missing` | 进展开区（没装块） | 原型 `phV.isMissing` |
| `#phone-size-note` | 保留在 `#phone-missing` 里 | 原型 `phV.sizeNote` |
| `#phone-loc-before` | 保留在 `#phone-missing` 里 | 原型 `phV.loc` |
| `#phone-loading-note` | 新增容器，装下面两个 | 原型 `phV.isLoading` 那段 |
| `#phone-download-note` | 挪进 `#phone-loading-note` | 同一段 |
| `#phone-loading-error` | 挪进 `#phone-loading-note` | 同上（原型没有，代码里有真实信号，保留） |
| `#phone-access-detail` | 进展开区，包住 `#phone-off` 与 `#phone-on` | 原型 `.adv-d` 内容 |
| `#phone-off` | 保留（通道、重新检测、提示），去掉里面的开启按钮 | 原型 `phV.isOff` |
| `#phone-channel`、`#phone-chan-*`、`#phone-chan-*-status`、`#phone-chan-*-text` | 保留不动 | 原型 `phV.channels` |
| `#btn-tailscale-recheck` | 保留在 `#phone-off` 里 | 原型 `phV.canRecheck` |
| `#phone-channel-hint` | 保留在 `#phone-off` 里 | 原型 `phV.hint` |
| `#phone-off-error`、`#phone-off-note` | 保留在 `#phone-off` 里 | 代码里现有的两条（原型把失败原因放标题行红条） |
| `#phone-on` | 保留（配对、地址、通道说明、关闭确认、再配一台），去掉里面的关闭按钮 | 原型 `phV.isOn` |
| `#phone-ok`、`#phone-cred-tip`、`#phone-pair` 及其子元素、`#phone-address`、`#phone-address-alt`、`#phone-address-alt-line`、`#btn-phone-address-copy`、`#phone-channel-note`、`#phone-on-error`、`#phone-stop-confirm`、`#btn-phone-stop-cancel`、`#btn-phone-stop-confirm`、`#phone-stop-row`、`#btn-phone-add-pair` | 保留不动 | 原型 `phV.isOn` 各块 |
| `#phone-loc-after` | 保留在展开区末尾 | 原型 `phV.hasLoc` |
| `#phone-status`（`p.help-status`） | 保留在展开区末尾 | 原型没有，代码里有真实信号，保留 |

## 二、验证码识别（`section#set-ocr`）

| 现状元素 | 去向 | 依据 |
| --- | --- | --- |
| `section.help-tools.set-ocr.ph-sec#set-ocr` | 保留，类名换成 `help-tools adv-sec ph-sec` | 原型第二段 `section.set.adv-sec` |
| `div.set-h` + `b#set-ocr-title` | 换成 `div.adv-h`，名称挪进 `.adv-t b` | 原型 `.adv-h` |
| `#ocr-title-chip` | 删除（「已装没启用」由状态句说） | 原型 `advHead` 的 `!ph && st === 'off'` 档 |
| `span.ph-slot` | 删除 | 同手机节 |
| — | 新增 `span.adv-ic` + 屏幕图标 svg | 原型 `.adv-ic` |
| `#ocr-feature-status` | 保留 id，改成 `span.adv-s`：`<i>` + `#ocr-feature-status-text` | 原型 `.adv-s` |
| `#btn-ocr-download` | 保留 id，挪进标题行按钮位 | 原型「下载并安装 / 更新组件 / 重新安装 / 重新下载」 |
| `#btn-ocr-enable` | 保留 id，挪进标题行按钮位；文字「启用」 | 原型 `!ph && st === 'off'` 档 |
| `#btn-ocr-cancel` | 保留 id，挪进标题行按钮位 | 原型「取消 / 校验中…」 |
| `#btn-ocr-retry` | 保留 id，挪进标题行按钮位 | 原型 timeout、unreadable 的「重试」 |
| — | 新增 `#btn-ocr-row-toggle` | 原型 `.adv-x` |
| `#ocr-probe` | 保留 id，改成 `.adv-n` 小字（读不到、需要更新、坏了、刚装好那句绿字都写这里） | 原型 `.adv-n` |
| `#ocr-note` | 删除，内容并进 `#ocr-probe`（原型的 `advHead` 只有一个 note 槽） | 原型 `advHead` 的 note |
| `#ocr-loading`（`div.ph-block`） | 保留 id，改成标题行下的 `div.adv-bar`，内含 `#ocr-prog-fill` | 原型 `.adv-bar` |
| `#ocr-prog-text` | 删除 | 原型 `advHead` 的 downloading 档 |
| `#ocr-prog-num` | 删除 | 同上 |
| `#ocr-component-progress` | 删除（`#ocr-loading` 自己就是进度条） | 原型 `.adv-bar` |
| `#ocr-prog-fill` | 保留 id | 原型 `.adv-bar i` |
| `#ocr-download-error` | 保留 id，留在标题行下（`p.ph-err.adv-e`） | 原型 `advHead` 的 `hasErr` 红条 |
| — | 新增 `#ocr-row-detail`（`div.adv-d`），默认收起 | 原型 `.adv-d`；识别默认收起 |
| `#ocr-download-state` | 进展开区（lead） | 原型 `ocV.lead` |
| `#ocr-import-line` | 进展开区 | 原型 `ocV.canImport` |
| `#ocr-missing`、`#ocr-size-note`、`#ocr-loc-before` | 进展开区 | 原型 `ocV.isMissing` |
| `#ocr-off-note` | 进展开区 | 原型 `ocV.isOff` |
| `#ocr-loc-after` | 进展开区末尾 | 原型 `ocV.hasLoc` |

## 三、这次新增的元素（只有这些）

| 元素 | 用途 |
| --- | --- |
| `#phone-feature-status-text`、`#ocr-feature-status-text` | 状态句的文字节点（圆点 `i` 单独留着，换色只改外层 class） |
| `#btn-phone-row-toggle`、`#btn-ocr-row-toggle` | 展开箭头 |
| `#phone-row-detail`、`#ocr-row-detail` | 展开区容器 |
| `#phone-loading-note` | 手机行下载中那句说明与加载错误的容器 |
| `span.adv-ic`（两节各一个） | 图标位 |

## 四、不做的

- 原型里只为演示存在的「演示：…」按钮（`phDemoFail`、`phDemoTs`、`phDemoPair`、`phDemoLeave`、`phDemoGone`、`ocDemoFail`）不搬。
- 页面字体与断行照 Edge 实际渲染，不从原型抄字体栈。
- 顶栏手机标识的转圈与慢闪、手机详情卡属下一小批，这里不动。
