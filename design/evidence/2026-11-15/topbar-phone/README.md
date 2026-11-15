# 顶栏的手机标识与手机详情卡（2026-11-15）

## 改了什么

顶栏那颗「手机」胶囊与点开的详情卡，从「只分开着/没开」升级成跟着后端 `link` 走的一张完整视图。

| 位置 | 之前 | 现在 |
|---|---|---|
| 顶栏标识 | 开着就绿底「手机已连接」，否则灰底「等手机连接」；开启/停止过程中被收起 | 五种样子：正在开启… / 正在停止…（灰底 + 转圈）、手机已连接（绿底）、等手机连接（琥珀底 + 图标慢闪）、已断开 · N 分钟前（灰底带时间）；没开收起。读屏名称随状态变 |
| 详情卡 | 只有「手机地址」「配对」两行，副句写通道名 | 小 chip 与小标（长期/临时地址）、大字、按状态写的副句、通道/地址/配对（或配对码倒计时）/手机最近访问四行、随通道变的底部提醒 |
| 连接状态推导 | `phoneLinkView` 只给标题、大字、小 chip、语气 | 多给一项「多久以前」（`ago`），供卡片写「手机最近访问」 |

为什么把开启/停止过程也画在标识上：这两个过程没有连接状态可读（`link` 还是 `off`），原来的写法是「收起」，用户点了「开启手机访问」后顶栏毫无反应。原型 `PhStartingTop` / `PhStopping` 两张画板要的就是这一段。

## 不变区

本批只看顶栏与卡片，不动抽屉、不动判定、不动后端。`local/tests/test_phone_link.py` 里「配过对没有」那几块（说明行、绿条、再配一台）用同一份配对快照换连接状态，除「手机最近访问」那一行外一个字不变；详情卡配对行看的是配过对没有，不是连着没有。

## 变化区由谁守

- `local/tests/test_topbar_phone.py`（14 条）：标识五种样子与「没开收起」、转圈只在过程中出现、读屏名称随状态变；卡片按三种连接状态各一条、Cloudflare/临时地址、没有配对码时的写法、没开时卡片为空、只有活动会话时不写「1 台手机」。
- `local/tests/test_phone_link.py`（9 条，改了观察点）：连接状态在抽屉、顶栏、卡片三处一致，手机回来会回到「手机已连接」。
- `design/evidence/2026-11-15/topbar-phone/scripts/shots.py`：在 Edge 里读真实计算值——转圈的 `animation-name` 不是 `none`、`waiting` 带 `is-warn` 与 `blink`、`connected` 带 `is-ok`、`#phone-badge-text` 的字色等于 `--ok`/`--warn` 且与叠出来的底色对比度 ≥ 4.5、`aria-label` 提到状态、卡片小标与 dt/dd 组数。**测试环境没有样式表**，颜色与慢闪只能这样核。

## 变异

`design/evidence/2026-11-15/topbar-phone/scripts/mutate_topbar.py`：**22 条变异全部变红、存活 0**。覆盖标识的五个样子（忙的两种、两种档、慢闪、转圈在/不在、没开收起）、读屏两句、卡片的四行与小标/副句/底部提醒/倒计时/地址去协议头、以及连接推导里「多久以前」与已断开标题的时间。

样式表那一条单独验过：把 `.pill.blink svg` 删掉，`shots.py --only app,waiting` 立刻报「等手机连接时 svg 的 animation-name 是 none」变红，恢复后全绿。

## 复跑

```bash
python -B -m unittest discover -s local/tests -p test_topbar_phone.py -v
python -B -m unittest discover -s local/tests -p test_phone_link.py -v
python -B design/evidence/2026-11-15/topbar-phone/scripts/shots.py
python -B design/evidence/2026-11-15/topbar-phone/scripts/mutate_topbar.py
python -B tools/code_shape/check.py
```

截图重出会覆盖 `shots/` 下的 PNG 与 `shots/pairs.md` 骨架；对照结论以提交里的 `shots/pairs.md` 为准。

## 与计划的偏差

1. 详情卡的「手机最近访问」按计划取后端秒数（画板写「刚刚」），见 `shots/pairs.md` 的说明。
2. 卡片地址去掉了协议头与结尾的斜杠，与画板一致（计划只说去协议头）。
3. 只有活动会话、还没真配过对时，配对行写「有手机连着」而不是「1 台手机」——原来会照抄画板的「1 台手机」，但 `paired_count` 是 0 时那句话不成立。
