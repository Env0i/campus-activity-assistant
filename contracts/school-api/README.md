# 学校接口契约样例（脱敏）

本目录只放**接口形状**：字段名、类型、状态取值。真实活动名、地点、组织单位、人名、
工号与经纬度都已替换，id 一律用 32 位明显假值。

用途：本机版（`local/`）与服务器版（`server/`）的测试共用同一份真实形状，
防止两边对同一个接口的字段假设各写一套。读取这些样例的测试在 B 计划
（`20261103-arch-b-core`）里，本计划只提供数据。

## 文件与来源

| 文件 | 对应接口 | 取得日期与证据 |
|---|---|---|
| `list-activity.items.json` | `POST /dr/api/rjyHd/listActivity` 的条目数组，**映射后**形状（每条 18 字段，字段名是程序内部的 `sign_start` 等） | 2026-11-03，`design/evidence/2026-11-02/live-check.md` 第三十一节 |
| `list-activity.raw-item.json` | 同一接口的**单条原始条目**（11 字段，字段名是学校的 `bmkssj` 等） | 2026-11-04，用户实测 `listActivity` 响应 |
| `get-info.data.json` | `GET /rjyHd/getInfo/<活动ID>` 返回的 `data`（49 字段） | 2026-11-03，同上第三十一节 |
| `get-join-info.json` | `POST /rjyHdCyr/getJoinInfo/<活动ID>`：未报名与已报名两种 | 2026-11-03，同上第三十四节 |
| `signup-replies.json` | `GET /rjyHdCyr/signUp/<hash>` 的业务回包分类 | 2026-11-02～03，同上第十四、二十八、三十九、四十节；规则见架构修订设计 3.3 |

### 原始 vs 映射后

`listActivity` 的条目有两层形态，两份都留，不要只留一份：

| 形态 | 文件 | 字段名 | 用途 |
|---|---|---|---|
| 学校原样 | `list-activity.raw-item.json` | `bmkssj`、`bmjssj`、`hdkssj`、`hdjssj`、`hdmc`、`hddd`、`hdlx`、`bmzt`、`cyrId`、`hbzj`、`id` | 验「学校真这么返回时，映射还对得上」；学校改字段名时这里先红 |
| 程序映射后 | `list-activity.items.json` | `sign_start`、`sign_end`、`act_start`、`act_end`、`name`、`place`、`type`、`signed` 等 18 个 | 验下游（计划、界面、测试替身）读到的形状 |

映射在 `local/grab.py` 的 `fetch_activities()`：
`bmkssj → sign_start`、`bmjssj → sign_end`、`hdkssj → act_start`、`hdjssj → act_end`、
`hdmc → name`、`hddd → place`、`hdlx → type`、`bmzt == 1 → signed`。

响应外壳（2026-11-04 实测）：
`{"code": 1, "message": "操作成功！", "data": {"count": N, "list": [...]}, "version": "1.0"}`。
`code=1` 成功；`code=4001` 登录失效；`code=0` 是业务拒绝（例：「账号或密码错误！」）。

`cyrId`、`hbzj` 程序目前没用到，但学校会返回，样例里保留形状。

## 脱敏规则

- **文本类**（活动名、地点、组织单位、简介、院系名等）→ `<文本>`；
- **身份类**（人名、工号、创建者姓名/工号、账号、经纬度）→ `<已遮>`；
- **id**：32 位明显假值（`00000000000000000000000000000000` / `111...`），不保留任何真实 id 片段；
- **状态字段**（`signed`、`sfbm`、`qddkfw`、`fbzt`、`state` 之类）与**时间字段**
  （报名窗口、活动时段、签到/签退窗口）保留真实取值形状，时间用真实日期；
- **一律不出现**：运行时密钥、token、hash、请求头、cookie、账号密码、真实站点地址与学校名。

## 学校改接口时怎么更新

1. 用已授权的方式按同一路径重新取一次真实回包（只取字段名与类型，不抄个人信息）；
2. 按上面的规则脱敏，替换对应文件；
3. 在本文件表格里补一行日期与 `live-check` 节号（没有新证据就写「本次运行观测」）；
4. 字段增删、改名或类型变化，在上面的表格下再加一行说明「改了哪个字段、哪次日期」——
   两份测试都以本目录为准，改了这里就等于改契约。
