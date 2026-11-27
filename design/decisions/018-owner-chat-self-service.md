# 018 · 私聊自助：我的报名、预报名查冲突、私聊取消、开始与签退提醒、变动通知

- **状态**：implemented（A–F 项已上线并真机验收正常；原提案 G 项「服务器直发签名报名」单列并在[决策 015](015-signup-path-and-replies.md) 2026-11-24 修订节承接）
- **日期**：2026-11-24
- **上游**：[决策 004](004-multi-activity-and-conflict.md)（时段冲突）、[决策 006](006-session-persistence.md)（单账号单会话边界）、[决策 012](012-independent-beijing-clock.md)（业务时间）、[决策 016](016-conflict-visibility-and-cancel.md)（私聊两步确认取消）

## 问题

owner 在外不方便打开学校网页或本机桌面工具时，在飞书私聊里仍缺少完整的自助闭环：看不到已报名活动的签到签退和退报条件、预报名时不查举办时间冲突、错不过开始与签退时段缺提醒、已报或排队场次改期下架没有私聊通知；同时本机桌面版报名结果也需要简洁配置的群机器人通知通道。

## 用户确认的规则

### 不变的边界

1. **只服务本人账号**：私聊内一切查询、预报名、取消与提醒只对 `PRIVATE_OWNER_OPEN_ID` 本人生效；公共群保持只读，群卡片不出现任何个人数据或写按钮。
2. **单一应用与身份分流**：沿用一个自建应用、一个长连接进程（`BOT_ROLE=combined`）按会话类型分流；别人私聊机器人问「我的报名」固定拒绝且不透露任何个人数据。
3. **不新增学校接口与不增登录频率**：只复用现有 `listActivity`、`getInfo`、`getJoinInfo`、`cancel`；服务器与本机共用一个账号登录，新增动作均为只读或单次写，不额外触发换新抢占。
4. **业务时间一致**：服务器沿用北京时间换算（`common.business_now()`），本机沿用独立业务时钟（决策 012）。

### 已上线六项（A–F）

- **A. 我的报名卡片补全（服务器）**：私聊发送「我的」「已报名」等关键词或点私聊菜单首项「我的报名」（群菜单无此项），列出尚未结束的本人已报名场次（超过上限顶部写「还有 N 场没展开」），含活动名、举办时段（跨天如实展开）、地点、签到/签退要求与时段及可取消状态；签到、签退与取消条件源自 `getInfo`（`sfxyqd`/`sfxyqt`/`qxbm`），学校没写明一律写「未知」，绝不猜成「无需」。可取消且在窗口内带「取消报名」按钮。
- **B. 预报名加入时查时段冲突（服务器）**：`watchlist.py add` 将新场次举办时段与「已报名场次（`bmzt == 1`）」及「预报名清单内 `queued` 场次」逐一比对，半开区间重叠即拒绝并写清冲突对象与双方时段；已报名场次时间未知时按可能冲突拒绝；待队列场次若举办时间未公布，允许入队并在卡片注明暂时无法查冲突，待公布后由 E 项监测冲突再通知（不自动移出）。
- **C. 私聊取消已报名（服务器）**：扩展[决策 016](016-conflict-visibility-and-cancel.md) 口径（2026-11-24 修订）到 owner 私聊：点「取消报名」只出确认卡（含 10 分钟有效期），确认后单飞执行前置核对、单次 `cancel`、`getJoinInfo` 复查、结果四类回写卡片，若在预报名清单内则一并移出；手机页与公共群仍禁取消。
- **D. 开始与签退提醒（服务器）**：`attend_remind.py` 由 cron 每 5 分钟唤醒，仅在已报名场次落入提醒窗口（活动开始前 30 分钟；需要签退者在签退时段开始时，无签退时段则在结束前 10 分钟）时才查 `getInfo` 并按天缓存当天结果，无临近场次不查详情；按「场次 + 提醒类型」原子去重，发送成功才落盘，错过窗口不补发，07:05 当日提醒保持不变。
- **E. 个人变动通知（服务器）**：`activity_watch.py` 在公共动态推送同一轮内联动 `personal_notice.py`，仅对本人已报名或预报名清单内场次的改期/换地点/类型等变动私聊通知（旧值 → 新值），连续三轮从列表消失（下架）发私聊提醒，排队场次公布时间或已报名改期后重新比对冲突并私聊提醒（不自动改清单）；未配 `PRIVATE_OWNER_OPEN_ID` 时只记日志，公共群消息保持零个人信息。
- **F. 本机版飞书提醒设置（本机）**：设置抽屉「程序」卡片内提供「飞书提醒」一行（说明「建一个只有你的群，加个自定义机器人，把地址贴在下面。报名结果和登录失效都发到这个群。」），支持填写 `https://` 地址、「发测试消息」与「保存」；只合并改写本机 `config.json` 里的 `feishu_webhook` 键（空串清空；配置损坏拒绝覆盖），与报名结果及登录失效既有推送复用同一通道。

### 不做与单列项

- **G 项单列**：服务器直发签名报名涉及新依赖 `cryptography` 与主动换新避让，已独立归入[决策 015](015-signup-path-and-replies.md) 2026-11-24 修订节。
- **不做项**：不在公共群加入任何个人数据或写功能；不做自动移出冲突场次或自动重新报名；不做学分、工时等统计汇总查询。

## 用户可见行为

- 飞书私聊发送「我的」或点菜单即可看到带完整签到签退时段与可退截止的个人活动卡片，并可直接两步确认取消；预报名若与已报/排队活动撞时间会被当场拦住。
- 活动开始前 30 分钟、签退临近以及已报/排队场次临时改期、下架或新撞时间时，owner 私聊会及时收到单条清晰提示，公共群完全不受干扰。
- 本机端可在设置抽屉直接测试并保存飞书群机器人 webhook 地址，报名结束或登录失效自动推到指定个人群。

## 工程契约链接

- 机器人权限、长连接、`BOT_ROLE=combined`、`users.json` 与私聊「我的报名」/取消规范：[docs/FEISHU_BOT.md](../../docs/FEISHU_BOT.md)（§0、§2、§2.10）
- 部署目录、crontab 定时（`activity_watch.py`、`attend_remind.py`）与环境变量说明：[docs/OPERATIONS.md](../../docs/OPERATIONS.md)（§3、§4、§6）
- 本机设置「飞书提醒」交互与校验契约：[docs/UI_SPEC.md](../../docs/UI_SPEC.md)（§5.21）
- 私聊取消两步确认与硬规则：[决策 016](016-conflict-visibility-and-cancel.md) 2026-11-24 修订节
- 服务器直发签名与主动换新避让：[决策 015](015-signup-path-and-replies.md) 2026-11-24 修订节

## 已知限制

- 飞书应用私聊依赖 owner 主动先给机器人发过消息以记录 `chat_id`，且部署环境必须在 systemd/crontab 中正确注入 `PRIVATE_OWNER_OPEN_ID`，缺失时私聊功能拒绝（或仅打日志）但群查询与公共推送不受影响。
- 开始/签退提醒（`attend_remind.py`）错过对应时间窗口（如服务器停机或 cron 暂停）时不补发过期提醒；若未配或拉不到 `getInfo` 详情则该轮跳过提醒、不凭空猜测。
- 冲突检查遇到学校已报名活动时间未知时采取保守拒绝；队列中未公布时间场次随后产生的新冲突仅私聊提醒，不自动踢出清单。
- 提案原文见 git 历史：提交 `899218a` 及之前版本的 `design/proposals/owner-chat-self-service.md`。

## 变更方式

- 改私聊卡片/冲突/取消/提醒行为：分别修改 `server/scripts/lib/mine_cards.py`、`mine_rules.py`、`server/scripts/signup/watchlist.py`、`cancel_signup.py`、`cancel_actions.js`、`server/scripts/push/attend_remind.py`、`personal_notice.py` 及 `server/bot/bot.js`，同步 `server/tests/test_owner_chat.py`、`server/tests/test_watchlist_safety.py`、`server/bot/test_bot_runtime.js` 与 `docs/FEISHU_BOT.md`、`docs/OPERATIONS.md`。
- 改本机飞书提醒设置：修改 `local/application/settings/feishu_settings.py`、`local/ui/features/shell/actions-settings.js`、`local/app.py`，并同步 `local/tests/desktop/test_application_services.py` 与 `docs/UI_SPEC.md` §5.21。
