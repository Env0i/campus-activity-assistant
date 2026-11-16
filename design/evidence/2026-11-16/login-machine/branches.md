# 登录胶囊原分支差别表

来源是 `features/login/view.js` 的 `paintLogin`。条件、文字和说明保持原文，状态机只承接结构。

| 原分支进入条件 | 阶段 | class 后缀 | 胶囊字 | 副句取法 | 详情说明取法 | `S.login.view.state` |
|---|---|---|---|---|---|---|
| `S.busy && !S.login.loginPending && !busyExpired && !S.autoLogin` | `plan_running` | `is-busy` | `present === false` 时「未登录」，否则「已登录」 | 空串 | `S.stopping` 时「正在停止计划；已报名的场次不受影响」，否则「登录状态保持不变；计划进度见报名区域」 | `present === false` 时 `none`，否则 `ok` |
| `S.demo` | `demo` | `is-warn` | 「演示模式」 | 「内存样例」 | 「不读取登录信息、不访问学校，只演示界面与流程」 | `demo` |
| `S.autoLogin` | `auto` | `is-busy` | 「自动登录中…」 | 空串 | 「学校说登录失效了，电脑正在用保存的账号自动登录」 | `pending` |
| `S.login.loginPending` | `logging_in` | `is-busy` | 「登录中…」 | 空串 | 「请在弹出的浏览器中完成登录；取消或关闭窗口后会保留原状态」 | `pending` |
| `S.login.checking || (ok === null && S.login.present === true)` | `checking` | `is-busy` | 「检查登录…」 | 空串 | 「正在检查登录状态，马上就好」 | `checking` |
| `S.login.present === false` | `never` | `is-none` | 默认「未登录」 | 空串 | 「打开顶栏的登录状态，点「登录」，在打开的浏览器中完成登录」 | `none` |
| `S.login.result === "unknown" && ok === false` | `unknown` | `is-none` | 「登录待确认」 | 空串 | 「暂时无法确认登录状态；检查网络后点「刷新」，先不用重新登录」 | `unknown` |
| `ok === false && S.login.present !== false` | `expired` | `is-bad` | 「登录已失效」 | 空串 | 「重新登录后可继续使用」 | `bad` |
| `ok === true` | `valid` | `is-ok` | 「已登录」 | `lastCheckText()` 有值时加「 校验」 | 有估算且以「约到」开头时拼「学校确认登录有效；预计」和「，以学校为准」，否则「学校确认登录有效」 | `ok` |
| 以上都不满足 | `unset` | 无 | 默认「未登录」 | 空串 | 默认「打开顶栏的登录状态，点「登录」开始使用」 | `none` |
| `termsLocked() && !S.demo && state !== "pending"` | `terms` | `is-none` | 「等同意条款」 | 空串 | 「同意使用条款后才会检查登录」 | `terms` |

## 死分支

- 登录按钮判断里保留 `state === "warn"`，但 `paintLogin` 原来从不产出 `warn`。
- `reloginHead` 保留 `step === "confirm"`，现有入口没有调用它。
