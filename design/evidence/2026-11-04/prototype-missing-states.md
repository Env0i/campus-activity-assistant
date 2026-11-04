# 原型缺口清单（给 Claude 补齐高保真原型用）

- 日期：2026-11-04
- 对象：`design/prototype/workbench-2026-11/`（84 个 `.dc.html`，其中 82 个是界面画板）
- 依据：原型自身的 scene 枚举 + `local/ui` 的实现状态 + 学校学生端前端 bundle 的静态分析
- 结论先说：**原型覆盖的是一条「报名计划」主线**。这条线上状态很密，但线下缺四类——
  停止确认、单场结果明细、报名被服务端拒绝的具体原因、以及三个学校有而我们没有的功能（取消报名、
  签到签退、我的活动）。

---

## 一、现有覆盖

原型文件分两层：`Main.dc.html` / `Phone.dc.html` 是正文，其余 82 个画板只设初始 scene。
`Main.dc.html:854` 的 scene 枚举列出 **67 个场景**：

```
draft normal waiting editing running result unknown expired clock listerr first settings
tour tour2 tour4 phonesetup phonets phonewait phonelinked closerun closeask closeexit
closeidle closehidden update upavail updown upready upfail comp compwrong compok compfail
credform credsaved relogin rlcap rlconfirm rlbad loginshort termsupdate termsdoc
termsprivacy termsoff termswithdraw popclock poplogin popdown popphone prewarn netoff slept
broken helpkeys longname zeroact clockhold runexpired runauto runclick toastmin runphone
```

---

## 二、原型有这个 scene，但没有对应画板（4 个）

补起来最省事，只要加一个 `.dc.html` 设 scene 就行。

| scene | 是什么 | 建议画板名 |
|---|---|---|
| `listerr` | 活动列表加载失败（`s.list = 'error'`） | `ListErr` |
| `clock` | 时间校准中（`s.clock = 'down'`） | `ClockDown` |
| `expired` | 登录明确失效（`s.login = 'expired'`），和 `loginshort` 不是一回事 | `Expired` |
| `normal` | 正常态（不带任何预设条件） | `Normal` |

---

## 三、程序里有、原型完全没有场景（要新设计）

这些状态在 `local/ui` 里已经实现，但原型没有对应画面，所以两边没法对照，也没法判断谁对。

| 状态 | 程序位置 | 原型现状 | 需要设计什么 |
|---|---|---|---|
| **停止计划确认** | `index.html:351` `dialog#dlg-stop` | 无 | 弹窗：标题、正在跑几场、停止会怎样、两个按钮。现在实现是一句话 + 取消/停止 |
| **单场任务的明细结果** | `views/plan-panel.js` 任务行 | `Result` 只有六类汇总大数字 | 每场一行：活动名 + 结论（已报名 / 名额已满 / 未提交 / 待核对 / 已取消 / 未成功）+ 一句说明 + 可做的动作 |
| **报名被服务端拒绝的具体提示** | 结果分类 + 运行记录 | 无 | 四种拒绝各是什么文案、显示在哪：名额已满、报名未开始、时间冲突（见第四节，这条是误导文案）、已截止 |
| **活动列表分页 / 加载更多** | 现在一次拉全量（`listActivity`） | 无 | 如果改用 `listPage` 分页，要设计「加载更多」和「到底了」 |
| **多开同一程序** | — | 无 | 第二个实例打开时提示什么、给什么出口 |
| **数据目录迁移提示** | `runtime_paths.py` 首次冻结启动会搬旧数据 | 无 | 搬完之后要不要告知、在哪说 |

---

## 四、学校学生端揭示的真实状态（新素材，2026-11-04 静态分析）

学校 SPA 的公开前端 bundle（主包 1.6 MB + 430 个懒加载 chunk，本轮按范围取 11 个，只取公开静态文件、未登录、未调接口）
里有三条对原型设计有直接影响的事实。

### 1. 「时间冲突」是误导文案

报名按钮的判断只有一句：

```js
1 !== e || 0 !== _.value.sfkybm
  ? E({ content: 1===e ? "是否确认报名此活动？" : "是否确认取消报名此活动？", ... })
  : E({ title:"提示", content:"本活动时间与你已参与活动时间冲突，不可报名！", showCancel:false })
```

只要 `sfkybm !== 0` 就弹「本活动时间与你已参与活动时间冲突，不可报名！」——
**已截止、已报名、真冲突、名额满，全都弹这一句**。所以不能把它当成「真冲突」的证据。

原型和实现都不该照抄这句话。我们需要自己分清楚是哪种拒绝。

### 2. 取消报名比报名简单得多

```js
const t = 1===e ? getActivitySignUp : getActivityCancelSignUp;
const l = 1===e ? N.encrypt(`${id},${Date.now()}`) : id;   // 取消：明文 id，不加密
```

- 报名：`GET /rjyHdCyr/signUp/{hash}`，hash = `encrypt("${id},${Date.now()}")`，点一次生成一条
- 取消：`GET /rjyHdCyr/cancel/{活动id}`，**明文 id，不需要 hash**

所以「改选 / 退掉再报」这条产品路径，成本比报名低。

### 3. 接口全集（`secondActivity` 模块）

| 方法 | 路径 | 用途 | 我们用了没 |
|---|---|---|---|
| POST | `/rjyHd/listActivity` | 全部活动 | ✅ 在用 |
| POST | `/rjyHd/listPage` | 分页列表（可按状态/时间/名称筛） | ❌ |
| GET | `/rjyHd/getInfo/{id}` | 活动详情 | ✅ 补签到签退窗口 |
| POST | `/rjyHdCyr/getJoinInfo/{id}` | 我报没报 | ✅ |
| GET | `/rjyHdCyr/signUp/{hash}` | 报名 | ✅ |
| GET | `/rjyHdCyr/cancel/{id}` | 取消报名 | ❌ |
| POST | `/rjyHdCyr/signIn` / `signOut` | 签到 / 签退（拍照、扫码、地理围栏） | ❌ |
| POST | `/rjyHdCyr/listMyActivity` | 我的活动 | ❌ |

### 4. 前端没有名额、性别、错误码表

- 客户端**没有任何**「名额」「性别」文案，这两类拒绝完全由服务端下发 `message`，界面只 toast。
- 前端只有 `code === 1` 一个成功分支，其余不处理，**没有错误码表**。

已攒到的真实回包（2026-11-02～04）：

| code | message | 场景 |
|---|---|---|
| 1 | 操作成功！ | 成功（列表、报名） |
| 0 | 账号或密码错误！ | 登录密码错 |
| 4001 | — | 登录失效 |
| 500 | 报名人数已满 | 名额满 |
| 500 | 报名未开始 | 未开始 |
| 500 | （时间冲突那句） | 见上文，多因共用 |

**这意味着**：想要完整的拒绝原因枚举，只能继续从真实响应里攒，前端推不出来。

---

## 五、我们功能没有、原型也没画（产品决策，不是画板问题）

**2026-11-04 19:02 用户已定口径**：工具范围 = 活动报名自动化；新功能最多两个候选——
**取消报名（想要）**和**查看可投稿的稿件（只读）**，其余不做。两项待与 Claude 共同决策
（汇总见同目录 `decision-agenda.md` D1/D2），定了再补画板。

| 功能 | 学校有 | 决定 | 备注 |
|---|---|---|---|
| 取消报名 | ✅ `cancel/{id}` 明文 id，前置 `sfbm && !sfcx && qxbm && 窗口内` | **候选要做**，待共同决策 | 技术素材齐（`school-frontend-analysis.md` 11.1）；连带修 `is_joined` 判据（D3） |
| 查看可投稿稿件 | ✅ `/rjyWgzj/listMine` | **候选要做（唯一新功能）**，待共同决策 | 只读不代投；素材齐（11.2） |
| 签到 / 签退 | ✅ 含拍照、扫码、地理围栏 | **不做**（用户 19:02 拍板） | 到场签到用户自己开学校 App |
| 我的活动视图 | ✅ `listMyActivity` | **不做**（除非做撤销时顺手，见 D1 要定项 2） | 现在列表里标「已报名」够用 |
| 分页改 `listPage` | ✅ 可按状态筛 | **不做**；已在 `listActivity` 分页 | 见四节纠正——「一次拉 318 场全量」的说法不成立 |

---

## 六、建议的补齐顺序

1. **先补第二节那 4 个画板**（`ListErr` / `ClockDown` / `Expired` / `Normal`）——半小时的活，补完整度立刻上来。
2. **再补第三节的停止确认和单场任务明细**——这两块是现在实现有、原型没有，用户真会看到的。
3. **报名被拒的四种提示**——素材还不全（只有名额满、未开始两条真回包），建议等攒齐再画，别先编文案。
4. **第五节的两个候选功能**（取消报名 / 稿件查看）——`decision-agenda.md` D1/D2 定了才画，画了也才有用。

---

## 附：证据位置

- 共同决策清单（撤销报名 / 稿件查看等全部待拍板项）：`design/evidence/2026-11-04/decision-agenda.md`
- 现有 82 个画板的原型截图：`design/evidence/2026-11-04/ui-gap/proto-all/`
- 程序侧 20 个可构造状态：`design/evidence/2026-11-04/ui-gap/app-states/`
- 99 处代码级差距：`design/evidence/2026-11-04/prototype-gap.md`
- 学校 bundle 静态分析：`D:\@temp\js-bundle-20261104\`（不入库），结论摘要在
  `design/evidence/2026-11-04/school-frontend-analysis.md`
