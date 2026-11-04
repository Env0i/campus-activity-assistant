# 学校学生端前端静态分析（补充）

- 日期：2026-11-04
- 范围：只读公开静态文件（主包 1.6 MB + **11 个按范围挑的 chunk**，未登录、未调用任何接口）。
  站点共 430 个动态 chunk / 325 条路由，其余 419 个是教师端和其他学生模块（心理/就业/宿舍/勤工助学），
  与活动报名无关，按用户 2026-11-04 拍板不挖。
  已下载清单：活动列表/详情/结果、我的活动/参与信息、稿件列表/详情/投稿、登录、忘记密码 + 主包。
- 原始文件：`D:\@temp\js-bundle-20261104\`（不入库）
- 目的：给原型补齐和产品决策提供事实，不替代真实回包

---

## 一、加密机制（已确认）

报名的 hash 是 AES 加密出来的：

```js
E0 = {
  encrypt: function (e) {
    const t = I0();                                  // 密钥
    return S0.AES.encrypt(e, S0.enc.Utf8.parse(t), {
      mode: S0.mode.ECB,
      padding: S0.pad.Pkcs7
    });
  }
}
// 调用处：N.encrypt(`${活动id},${Date.now()}`)
```

- 算法：**AES / ECB / PKCS7**
- 密钥：`I0()` 返回的字符串，来自运行时安全配置
- 明文：`"${活动id},${时间戳毫秒}"`
- 取消报名**不用**这套：`GET /rjyHdCyr/cancel/{活动id}` 传明文 id

密钥来源是 `/upms/security/runtime/profile`——请求拦截器里对除该路径外的所有请求调用
`ensureRuntimeSecurity()`。这和我们代码里的「运行时密钥」是同一套机制。

---

## 二、接口全集（34 条）

主包里以字面量出现的路径，按用途分类：

### 认证与账号（8）
| 路径 | 用途 |
|---|---|
| `/auth/captcha` | 验证码图 |
| `/auth/login` | 登录 |
| `/auth/logout` | 退出 |
| `/auth/info` / `/auth/info/edit` | 用户信息 / 改资料 |
| `/auth/client` | 客户端配置（缓存） |
| `/auth/change/pwd` / `/auth/change/pwd/sms/*` | 改密码 / 短信验证码 |
| `/upms/security/runtime/profile` | **运行时安全配置（密钥来源）** |
| `/upms/account/student/infoById` | 学生信息 |

### 活动（rjyHd，3）
| 路径 | 用途 |
|---|---|
| `/rjyHd/listActivity` | 全部活动（我们在用） |
| `/rjyHd/listPage` | 分页列表 |
| `/rjyHd/getInfo/{id}` | 详情 |
| `/rjyHd/audit` | 活动审核 |

### 参与与签到（rjyHdCyr，7）
| 路径 | 用途 |
|---|---|
| `/rjyHdCyr/getJoinInfo/{id}` | 我报没报 |
| `/rjyHdCyr/signUp/{hash}` | 报名 |
| `/rjyHdCyr/cancel/{id}` | 取消报名 |
| `/rjyHdCyr/signIn` / `signOut` | 签到 / 签退（POST，带 data） |
| `/rjyHdCyr/listMyActivity` | 我的活动 |
| `/rjyHdCyr/countCyqk` / `countHdlx` | 参与情况 / 活动类型统计 |
| `/rjyHdCyr/track/{id}` | 轨迹 |
| `/rjyHdCyr/evaluate` | 评价 |

### 文件上传（dms，4）
`/dms/file/upload/check`、`/chunk`、`/merge`、`/dms/enclosure/preview/single`
——分块上传，签到拍照或稿件附件用。

### 评论（rjyHdPl，3）
`/rjyHdPl/addSpeak`、`/checkMgc`、`/listPage`

### 其他模块
`/rjySjcj/detail`、`/rjyXngzd/getMonthList` —— 数据采集、学年规划相关。

---

## 三、页面路由（14 个，完整功能树）

```
/secondClassroom/student/index                        首页
/secondClassroom/student/activity/studentActivity/index          活动列表
/secondClassroom/student/activity/studentActivity/activityDetails 活动详情
/secondClassroom/student/activity/studentActivity/result          结果（签到签退结果页）
/secondClassroom/student/activity/myActivity/index               我的活动
/secondClassroom/student/activity/myActivity/participateIn       参与
/secondClassroom/student/manuscript/index                        稿件列表
/secondClassroom/student/manuscript/addManuscript                投稿
/secondClassroom/student/manuscript/manuscriptDetail             稿件详情
/secondClassroom/student/myPayroll/index                         薪资
/secondClassroom/student/myPayroll/detail                        薪资明细
/secondClassroom/student/qualityprofile/index                    素质画像
/secondClassroom/student/ranking/index                           排行榜
/secondClassroom/student/reportCard/index                        成绩单
```

**这是学校的完整产品**：活动 + 稿件投稿 + 薪资 + 素质画像 + 排行榜 + 成绩单。
我们的工具只切了「活动报名」一个角。

值得注意：**「我的活动」是独立页面**，不是活动列表里的一个标记。我们的实现在列表里标「已报名」，
和学校的组织方式不同。

---

## 四、分页与筛选（纠正上一轮的说法）

上一轮说「有 `listPage` 分页接口，我们一次拉全量」——**这条是错的**，挖到列表页 chunk 后更正：

学校 App 的列表页调的也是 `getAllActivity` → `POST /rjyHd/listActivity`，传的是：

```js
U = ref({
  pageSize: 4,      // 学校 App 每页 4 条（手机上）
  pageNum: 1,
  hdmc: "",         // 活动名称（搜索词）
  hdzt: null,       // 活动状态：null=全部 / 0=未开始 / 1=进行中 / 2=已结束
  kssj: "",         // 活动开始时间（时间范围）
  jssj: ""          // 活动结束时间
})
```

**我们的实现传的参数和它完全一样**（`grab.py:797`：`{pageSize: 50, pageNum, hdmc: "", hdzt: None, kssj: "", jssj: ""}`），
已经在分页（最多 30 页 × 50 条）。所以「一次拉 318 场全量」的说法不成立。

真正可优化的是**筛选**：我们现在 `hdzt` 恒为 `None`（拉全部），如果改成只拉 `0`（未开始），
数据量会小很多；代价是「进行中」的场次拉不到，要看产品要不要。

`listPage` 是另一个接口，用途未确认（可能是管理端）。

### 前端的相对时间怎么算

```js
// 活动状态：以后台给的活动起止时间和本机当前时间比
hdkssj > now ? "活动未开始" : hdjssj < now ? "活动已结束" : "活动进行中"

// 报名状态与倒计时
bmsj = now < bmkssj ? "未开始"
     : now > bmjssj ? "已结束"
     : "X天 Y小时 Z分"      // 距报名截止
```

注意它先把 `bmkssj` / `bmjssj` 里的 `-` 换成 `/` 再 `new Date()`——那是 iOS 的日期解析兼容写法。

列表页每 **30 秒**重算一次这些相对时间（`setInterval(G, 3e4)`），**不重新请求接口**。

---

## 五、签到与签退的请求体

```js
const c = 1 === lx ? getActivityQd : getActivityQt;   // lx: 1=签到 2=签退
const body = 1 === lx
  ? { hdId, qddz: dz, qdtp: fs === 1 ? tp : null }   // 签到：地址 + 拍照图
  : { hdId, qtdz: dz, qttp: fs === 1 ? tp : null };  // 签退：地址 + 拍照图
```

| 字段 | 含义 |
|---|---|
| `hdId` | 活动 id |
| `qddz` / `qtdz` | 签到 / 签退地址（由定位换算，带经纬度） |
| `qdtp` / `qttp` | 签到 / 签退照片，只有「拍照」方式才带，扫码为 `null` |

方式 `fs`：`1` 拍照 / `2` 扫码 / `3` 空。扫码走另一条路径（`uni.scanCode`）。
地理围栏的判定在**服务端**，客户端只负责传地址和照片；超范围的提示「您当前位置超出打卡范围」是服务端文案。

---

## 六、学校的系统全貌（顺带挖到的）

主包里有 **178 个页面路由**、**326 个动态 chunk**。按一级目录分：

| 模块 | 学生端 | 教师端 |
|---|---|---|
| 学生工作 `stuWorker` | 10 | 33 |
| 思想工作 `ideologyWork` | 2 | 24 |
| 素质教育 `qualityEducation` | 22 | 22 |
| 心理健康 `mentalHealth` | 11 | 5 |
| 就业服务 `employmentService` | 10 | — |
| 第二课堂 `secondClassroom` | 8 | — |
| 宿舍服务 `dormService` | 4 | 8（+2 新生） |
| 勤工助学 `workStudy` | 2 | — |

学校跑的是一整套「学生工作管理系统」，**第二课堂只是其中一个模块**，我们只用了它的 4 个接口
（`listActivity` / `getInfo` / `getJoinInfo` / `signUp`）。其余模块（心理、就业、宿舍、勤工助学）
和我们的产品无关，但说明：接口变更的风险来自整个系统升级，不只是第二课堂。

---

## 七、对我们有实际价值的发现

| # | 发现 | 影响 |
|---|---|---|
| 1 | 加密是 AES/ECB/PKCS7，密钥来自 runtime profile | 我们已在用，这里只是**确认算法**，可以写进文档，不用再猜 |
| 2 | 取消报名传明文 id、不需要 hash | 「改选 / 退掉再报」成本比报名低很多，可以做 |
| 3 | `listActivity` 本身就是分页接口，参数有 `hdmc` / `hdzt` / `kssj` / `jssj` | 我们已在分页；可优化的是按 `hdzt` 只拉未开始，减少数据量 |
| 4 | 签到/签退的请求体已拿到（`hdId` + 地址 + 可选照片） | 如果要做签到，字段够了；围栏判定在服务端 |
| 5 | **已撤销（sfcx=1）在我们 `is_joined` 会被误判成已报名**（见 9.3） | 建议判据改成 `sfbm && !sfcx`，需要 Claude 拍板 |
| 6 | 「时间冲突」文案在前端写死，条件仅是 `sfkybm===0`（见 9.4） | 我们收到时间冲突类报错时，不能按文案推断原因 |
| 7 | getJoinInfo 回包 16 字段全集 + 详情页三按钮状态机（见 9.2） | 做签到/状态展示时字段和判定逻辑都有了 |

---

## 八、还能挖的（按价值排序）

1. ~~`listPage` 到底干什么~~——已挖：`secondActivity.getActivityList` 包装了它，但学生端 4 个已下载 chunk 里**无人调用**；调用方在未下载的 chunk（疑似教师端/管理端），对学生端无影响
2. ~~完整错误码~~——已挖到客户端分发表（见 10.1）：`0`/`500`/`4001`/`4002`/`4004`/`4005`；message 文案仍在服务端，只能继续攒真实回包
3. `countCyqk` / `countHdlx` 的字段——在素质画像/成绩单 chunk 里，与活动报名无关，暂不挖
4. ~~「我的活动」「稿件」等 chunk 未下载~~——已补抓（见 11.1/11.2）；稿件投稿动作（附件上传+敏感字段加密）确认不做，只读列表

第 2 条要登录态才能确认，第 4 条要补抓 chunk，其余已挖完。

---

## 九、详情页状态机（getJoinInfo 深挖，2026-11-04 补）

### 9.1 getJoinInfo 的调用与回包

- **方法**：POST（bundle 里 `d1` = POST，id 拼在 URL 路径上）。我们 `grab.py:849` 用 `_post`，一致。
- **回包 data 字段全集（16 个）**，前端初值即完整字段表：

| 字段 | 含义 | 备注 |
|---|---|---|
| `sfbm` | 是否报名 | 0/1 |
| `sfcx` | 是否撤销（取消过报名） | **关键**，见 9.3 |
| `bmsj` | 报名时间 | |
| `qdzt` / `qdsj` | 签到状态 / 签到时间 | |
| `qtzt` / `qtsj` | 签退状态 / 签退时间 | |
| `rdzt` / `rdsj` | 入场(认定)状态 / 时间 | `dqrdjd` 当前签到进度 |
| `pjzt` / `pjf` / `pjsj` | 评价状态 / 评分 / 评价时间 | |
| `dzbs` | 点赞数（0/1 切换） | |
| `cylx` | 参与类型 | `[1,2]` 时隐藏报名按钮；`=2` 时未报名也可签到。含义未证实（疑似组织者/直接拉入） |
| `sjdf` | 实际得分 | |

- 未报名时 `data` 为 `null`（与我们实测一致）。

### 9.2 详情页三按钮状态机（原样提取）

```js
// 报名按钮 re：0=不显示 / 1=可报名 / 2=可取消报名
bmzt = sfcx ? 2 : sfbm ? 1 : 0        // 页面顶部的报名状态标记
re   = 在「活动要求」tab && getJoinInfo 已返回 && cylx ∉ [1,2]
     ? ( (!sfbm || sfcx === 1) 在报名窗口内 → 1
       : sfbm && !sfcx && qxbm 在报名窗口内 → 2
       : 0 )

// 签到按钮 ve：返回值 = qdfs（签到方式，可显可隐）
ve = sfxyqd && (sfbm && !sfcx || cylx === 2) && qdzt === 0 && 在签到窗口内
   ? qdfs : 0

// 签退按钮 me：同上换 sfxyqt / qtzt / qtfs / qt 窗口

// 评价点赞区 fe：(sfbm && !sfcx || cylx ∈ [1,2]) && now > bmjssj
```

时间窗口全部用**本机时间和 getInfo 的起止字段比**，30 秒 setInterval 重算，不重新请求。

### 9.3 ⚠️ 对我们代码的一个真实风险（给 Claude 决策，未改代码）

学校前端把**「已撤销」（sfcx=1）视为可以再次报名**（re 的第一个分支 `(!sfbm || sfcx===1) → 1`）。
已撤销时 `getJoinInfo` 的 `data` **不是 null**（记录还在，sfbm/sfcx 有值）。

我们的 `is_joined()`（`grab.py:853`）判据是 `data not in (None, {}, [])`——
**用户报了名又取消后，我们也会把他判成「已报名」**：

1. 预检阶段：把可报的「已撤销」状态当成已报名 → 不再发提交 → 该抢的没抢；
2. 收尾核对：把「已撤销」改判成「报名成功」→ 结果造假。

判据应改成与学校前端对齐：`data 非空 && sfbm && !sfcx` 才算已报名。
（`test_real_data_contract.py` 的三条夹具都只覆盖 sfbm/sfcx 的正向组合，没测已撤销。）

### 9.4 「时间冲突」文案的代码级证据

```js
ge = async e => {  // e: 1=报名 2=取消
  1 !== e || 0 !== _.value.sfkybm
    ? 弹确认框（"是否确认报名/取消报名此活动？"）
    : 弹「本活动时间与你已参与活动时间冲突，不可报名！」（写死，showCancel: false）
}
```

即：`sfkybm === 0` 时前端**自己**弹时间冲突文案，和服务器没有任何交互——
第八节「误导文案」的推测现在是实锤：文案在前端写死，真实原因只在服务端。

### 9.5 报名/取消/评价/点赞的请求细节

| 操作 | 方法 | 请求 | 成功后 |
|---|---|---|---|
| 报名 | GET `/rjyHdCyr/signUp/{hash}` | hash = AES(`{id},{Date.now()}`) | 重新拉详情 `q(id)`，toast message |
| 取消 | GET `/rjyHdCyr/cancel/{id}` | **明文 id** | 同上 |
| 评价 | POST `/rjyHdCyr/evaluate` | `{id, pjf}`（星级），仅 `sfyxpj===1` 显示入口 | toast message |
| 点赞 | GET `/rjyHdCyr/thumbsUp/{id}` | 500ms 防抖，仅 `sfyxdz===1` 显示 | 本地翻转 dzbs |
| 评论 | POST `/rjyHdPl/checkMgc` → `/rjyHdPl/addSpeak` | 先敏感词检查 | 刷新评论列表（pageSize 4） |

### 9.6 扫码签到的完整链路（新发现）

```js
// 签到码本身是 "{加密串},{lx}" 两段格式，扫出来 split(",")
x = e => { const t = e.split(",")[0], a = +e.split(",")[1];
           k === a ? 发签到(t, a, fs=2) : toast("请扫正确签到/签退码！") }
// 拍照/无设备方式走 _.value.id；扫码方式把**加密串**当 hdId 传
signIn body = { hdId: 加密串或活动id, qddz: 定位逆编码的地址串, qdtp: fs===1 ? 拍照图 : null }
```

- 签到/签退的 `hdId` 字段在扫码方式下传的是**扫码解出的加密串**，不是数字 id（服务端两种都收）。
- 定位：uni 定位拿经纬度 → 逆地理编码换成地址字符串；围栏判定在服务端。
- 结果页 `result` 纯靠 URL 参数（`result/qdqtlx/fs/id/message`）展示成功失败图，**不重新查接口**——
  服务端 signIn 的返回只有 `code/message`，没有业务数据。

### 9.7 本轮静态挖掘的边界

主包 + 活动列表/详情/结果 3 个 chunk 之外，`myActivity` / 稿件 3 页 chunk 已于当晚补抓（见十一节）。
`listPage` 的调用方仍在未下载的教师端/管理端 chunk（学生端可见调用点都只用 `getAllActivity`）。
`sfqd` 疑虑已解除：`grab.py:694` 读的就是真实字段 `sfxyqd`/`sfxyqt`，`sfqd` 只是别名兜底列表。

### 9.8 参与信息页（participateIn，最终补挖）

「我的活动 → 参与信息」页 = `getJoinInfo(activityId)` + `track(cylId)` 两个接口，展示字段全是 9.1 的表。
**新情报——qdzt / qtzt 是三态**：

```
1  = 已签到（显示 qdsj 时间）
0  = 未签到
-1 = 无需签到        ← 之前不知道的第三态
```

我们 `_tri_state()`（grab.py:624）只把 0/1 归一化，-1 会落进 None——目前没消费 qdzt/qtzt 所以无影响，
**做签到状态展示时必须先处理 -1**。报名时间列的展示逻辑也是 sfcx 优先：`sfbm&&!sfcx→bmsj`、
`sfbm&&sfcx→「报名已取消」`、未报名→「未报名」（与 9.3 的判据再次互证）。

---

## 十、请求层：拦截器、错误码、字段级加密（补挖）

### 10.1 业务码分发表（拦截器里写死的，这是「码表」的客户端半边）

| code | 客户端行为 |
|---|---|
| `1` | 成功（默认路径，页面自己处理 data） |
| `0` | toast `message`（1500ms），**业务失败**（如「账号或密码错误！」） |
| `500` | toast `message`（1000ms） |
| `4001` | 清本地存储（保留 app_version）→ 弹「身份验证失败」→ 跳登录页 |
| `4002` / `4004` | **完全静默**，页面按失败处理 |
| `4005` | 弹「密码已过期请即时更新」→ 跳改密页 |

对照我们已攒的真实回包：`0`=账号密码错（已在 C1 处理）、`4001`=登录失效（已有 LOGIN_RECHECK）。
新增情报：`4005` 是**改密码后才出现**的码——收到它时提示用户改密，比「重新登录」更准确。

### 10.2 字段级加解密（敏感字段列表，34 个）

请求发送前，`data`/`params` 里**命中下列字段名的值**会被 AES 加密；
响应回包里同名字段会被前端解密。活动字段（hdmc/bmkssj 等）不在列表内，所以我们拿到的都是明文：

```
sjh, dzyx, zjh, lxrdh, lxryx, hzlxfs, hzzjh, sfzh, phone, lxdh, mail, bzrsjh,
czsjh, fdysjh, fsjsjh, fzrsjh, jzlxdh, lzsjh, sszsjh, qyyx, lxrsjh, dh, jzsjh,
lxfs, tbfqlxdh, tbfqsfzh, tbmqlxdh, tbmqsfzh, fqsjh, mqsjh, fzrdh, xqczdh, xqlxdh
```

全是手机号/证件号/邮箱类。**对活动的报名/签到无影响**；做「稿件投稿」（里面有联系人）才需要解密。

### 10.3 token 与密钥时序

- 请求头 `token: ${xgUniToken}`（本地存储）；`/auth/client` 不带。
- 除 `/upms/security/runtime/profile` 和 `/auth/client` 外，**所有请求发出前都先 await 密钥就绪**
  （`ensureRuntimeSecurity`）——和我们「先取运行时密钥再发报名」的顺序一致。
- token 变化时清空已缓存的运行时密钥（`z0`：新 token ≠ 旧 token → `clearRuntimeSecurity`）。
  我们切账号后也必须重取密钥，不能沿用。

---

### 10.4 登录页的完整提交体（mainPages-login，最终补挖）

```js
// 验证码：先 getClient()（客户端配置，有缓存），再 captcha({client, userType})
// 回包：data.key = uuid（登录时带回），data.image = base64 图

// 登录提交体（与我们的 _http_login 对照）：
{ userName, pwd, code, uuid, userType: "1", client, grantType: "pwd" }

// 失败分支：code !== 1 → 3 秒后自动刷新验证码再试（用户重输）
// 成功分支：按 e.data.userType 路由—— 1/4=教师端, 2=学生端, 10=新生端
// 前端门槛：必须勾选《隐私协议》，否则不提交
```

- 登录失败自动换验证码的节奏（3 秒）与我们 `CAPTCHA_ERROR_MESSAGES` 换图重试的思路一致。
- 忘记密码页（补挖）：手机验证码重置（`getPhoneCode` → `getPhoneEdit`，都带 client）；
  **密码规则 = 大小写字母 + 数字组合，6-20 位**——登录中继给用户提示密码规则时可以用。

---

## 十一、两个候选新功能的技术素材（2026-11-04 补抓 chunk 后）

> 用户意向（2026-11-04）：工具范围锁定「学生活动报名自动化」；**撤销报名**是想要的能力，
> **查看可投稿的稿件**是唯一可再加的新功能，其余不做。**两项都需与 Claude 共同决策后才动代码。**
> 待拍板项已汇总进同目录 `decision-agenda.md`（D1/D2/D3）。
> 本节只是素材，不改任何实现。
> 补抓 chunk：`manuscript-index.20f740f2.js`、`manuscriptDetail.9b185a66.js`、`addManuscript.22db01e5.js`、
> `secondClassroom myActivity-index.71745585.js`（`/stu/assets/` 直下，静态资源无需登录态）。

### 11.1 撤销报名（「报名了不想去了」）

**接口**（已确认，技术成本极低）：

```
GET /rjyHdCyr/cancel/{活动id}    # 明文 id，不带 hash，不带请求体
```

**学校前端的撤销前置条件**（详情页 re 状态机，见 9.2）：

```
sfbm && !sfcx && qxbm === 1 && now ∈ [bmkssj, bmjssj]
```

- `qxbm`：活动本身允不允许取消（getInfo 字段，1=允许）——**撤销前必须查详情确认**，
  也要确认不在「已撤销」状态（`sfcx===1` 时按钮就没了）。
- 学校前端撤销前弹确认框，成功后重拉详情并 toast 服务端 message。

**「我的活动」接口**（撤销前让用户看到自己报了什么）：

```
POST /rjyHdCyr/listMyActivity
参数：{hdmc: 搜索词, pageNum, pageSize(校用8), rdzt: null|0待认定|1已认定|2不认定, xn: 学年, xq: 学期}
回包：{count, list: [{id, cylId, hdlx, hdmc, sjdf(实践学分), termName, ...}]}
```

点击列表项跳详情（`activityId` + `from=myList`）；「参与信息」按钮带 `cyrId` 进 participateIn 页。
rdzt 筛选的学年学期列表来自 `POST /upms` 的 `getTermList`。

**注意**：撤销后 `getJoinInfo` 的 data **不会变 null**（记录保留，`sfcx=1`）——做撤销后
必须按 `sfbm && !sfcx` 判状态，否则自己的 `is_joined` 会把撤销过的活动又判成已报名（见 9.3）。

### 11.2 查看可投稿的稿件（「文稿征集」）

**接口**（稿件模块服务名 `wgzj`，页面无登录外的额外门槛）：

```
POST /rjyWgzj/listMine      # 「文稿征集」列表（可投稿的征文）
参数：{pageNum, pageSize(校用15)}
回包：{count, list: [...]}
```

**每条字段**（列表页渲染用到的全部）：

| 字段 | 含义 | 页面用法 |
|---|---|---|
| `id` | 征集 id | 投稿时用 |
| `wgzt` | 文稿主题 | 标题 |
| `zjzt` | 征集状态 | **「进行中」/「已结束」**，进行中才可投 |
| `zjxq` | 征集详情 | 两行省略的正文 |
| `jzrq` | 截止日期 | 底部展示 |
| `sftg` | 我是否已投稿 | 注意是**字符串 "1"**（前端 `"1"===t.sftg`） |
| `wglx` | 文稿类型 | 投稿跳转携带 |

「我的投稿」用 `POST /rjyWg/list`（参数 `{xh, pageNum, pageSize}`，回包字段 `zt`(2=未通过可编辑)、
`sfcn`(-1 审核中/0 未采纳/1 采纳)、`sjdf` 实践学分、`xngz` 虚拟工资）——**只读「文稿征集」列表的话用不到**。

投稿动作本身（`POST /rjyWg/add`，附件走 dms 分块上传 + 34 个敏感字段加密）**不在本次范围**：
我们只「查看」，不代投。

### 11.3 服务端我们能进吗——不能，也不需要

- 服务端是学校机房里的系统，我们没有也不应该有服务器/数据库的任何访问凭证；
  尝试「进服务端」属于越权，本项目不做。
- 我们的能力上限 = **学生端等价**：拿学生账号登录后，调用学生端页面会调用的同一批接口
  （这正是本工具一直的做法，bundle 挖掘只是把「学生端会调什么、怎么调」抄下来）。
- 因此名额余量、风控阈值、真实拒绝原因、message 文案这些**只在服务端**的东西，永远只能靠攒真实回包；
  静态分析能给的（接口形状、字段、前端判定逻辑）本文件已挖完。
- 静态资源（`/stu/assets/*.js`）无需登录即可下载——这也是本轮能补抓 chunk 的原因；
  接口调用则需要登录态，素材真实性以实测回包为准。

## 十二、不能做的事

- bundle 里没有名额、性别、错误码文案——这些**只在服务端**，客户端只 toast 服务端给的 `message`
- 不能从 bundle 推出「某个活动为什么不能报名」——`sfkybm` 只是一个 0/非 0 的标志，
  真正原因在服务端，客户端那句「时间冲突」是复用的误导文案
- 不能用 bundle 里的加密算法直接算 hash：密钥来自 `/upms/security/runtime/profile`，
  仍然要在线取一次，省不掉
