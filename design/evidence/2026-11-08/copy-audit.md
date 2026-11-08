# L5 文案真源比对：design/specs/copywriting.md ↔ local/ui/（2026-11-08）

只读盘点，没有改任何代码与规格。design/specs/copywriting.md 的用户可见字符串去重 462 条，逐条与 local/ui/** 比对；对抗复核补漏 1 条后全表 463 条，收录于下表，供后续修规格、改文案按条派工。

## 范围与方法

- **范围**：`design/specs/copywriting.md` 全部带引号字符串（「」含一层嵌套与『』、弯引号“”、ASCII 引号，按含 CJK 过滤为用户可见候选），去重后 462 条 ↔ `local/ui/**` 全部 .js/.html/.css（12,825 行：index.html、m/、views/、state/、controllers/、app.js、led.js 等）。
- **方法**：逐条 grep 四步匹配：① 逐字子串；② 模板归一（N/M/X/Y、<…>、HH:MM、数字时刻 → 代码变量 / ${} / 字符串拼接）；③ 空格容忍；④ 「A / B」枚举拆分。仍未命中的逐条人工 grep 复核给结论。两处补充证据来自 local/app.py（界面前端作用域之外，条目内已标明）。
- **基准**：commit `a85209e`，比对基于当时磁盘工作区；工作区另有其他协作者的未提交改动（含 local/ui/app.js、controllers/plan.js、refresh.js、tick.js、state/filters.js、state/labels.js、state/store.js 等），结论反映比对时刻的磁盘状态。
- **标注**：【已复现】＝检索/命令输出直接支持；个别【静态推断】在备注注明。
- **搬运与复核（2026-11-08）**：素材三列结构机械转为下表，条目文字逐字保留、462 条无增删，`\|`、`\<` 仅为表格转义。整理后抽样 grep 复核 13 条（条目 9/24/31/35/44/52/55/163/170/233/278/428/443，另含 L6 共 17 处），内容全部与素材一致，未改素材任何条目。行号三点观察：views/login.js:74 的内容实测在 73 行（login.js 自 a85209e 未变，素材行号差 1，内容逐字无误）；views/list.js:353/360、state/store.js:36 现盘分别漂移到 349/355/33（两文件带他人在途改动，行号随其继续漂移）；本表一律保留素材原行号，复核以内容为准。对抗复核后另有修订（推翻重判 3 条、证据修正 15 条、归类调整 1 条、补漏 1 条、漂移补注 7 处），见文末「修订记录（对抗审阅 2026-11-08）」与同目录 `ADVERSARIAL-L5.md`。

## 统计

| 类别 | 条数 |
|---|---|
| 一致（含模板归一/拼接/两参渲染） | 399 |
| 不一致 | 22 |
| 代码没有 | 4 |
| 规格禁止示例/已废止（代码未出现=符合） | 29 |
| 规格示例格式（「说估算就写约」的格式示例，非禁语） | 1 |
| 规格元描述 | 6 |
| 分发词表（非界面文案，不追） | 1 |
| 合计（唯一用户可见字符串） | 462 |

- 上表为对抗复核修订后的重算值（修订前：一致 402 / 不一致 22 / 代码没有 4 / 禁止示例+已废止 28 / 元描述 5 / 词表 1 = 462）；明细见文末「修订记录（对抗审阅 2026-11-08）」与同目录 `ADVERSARIAL-L5.md`。
- 对抗复核补漏 1 条（条目 463，spec:538『重新确认状态』，一致）不计入上表；含补漏全表 463 条，其中一致 400。
- NEEDS-HUMAN 共 9 条（spec:195、spec:262、spec:340、spec:370-375 六条），归并为 4 个议题，见文末专节；4 个议题经对抗复核独立证实，维持待决。

## 全量逐条表（原 462 条 + 对抗复核补漏 1 条 = 463 条）

「代码命中」列多条命中以 `<br>` 分行；「未检出」指 local/ui 全库无逐字/归一命中。

| # | 规格出处 | 规格字符串（逐字） | 代码命中（file:line ↳ 代码原文逐字） | 结论 | 备注 |
|---|---|---|---|---|---|
| 1 | spec:13,275 | 「已停止」 | local/ui/controllers/plan-events.js:96 ↳ 已停止<br>local/ui/views/list.js:433 ↳ 已停止 | **一致**【已复现】 |  |
| 2 | spec:13 | 「检查登录…」 | local/ui/views/login.js:47 ↳ 检查登录… | **一致**【已复现】 |  |
| 3 | spec:13,228,319 | 「正在停止…」 | local/ui/views/plan-panel.js:1237 ↳ 正在停止… | **一致**【已复现】 |  |
| 4 | spec:13,79 | 「登录成功」 | local/ui/index.html:376 ↳ 登录成功<br>local/ui/controllers/plan.js:454 ↳ 登录成功 | **一致**【已复现】 |  |
| 5 | spec:14,307 | 「报名成功」 | local/ui/index.html:131 ↳ 报名成功<br>local/ui/index.html:146 ↳ 报名成功 | **一致**【已复现】 | 对抗复核：引句为「不承诺无缺陷或报名成功」免责句的子串，非标签用法（结论仍成立）；真实标签用法见 state/labels.js:48、controllers/plan.js:471、views/plan-panel.js:650。 |
| 6 | spec:14 | 「等待开放」 | local/ui/state/labels.js:48 ↳ 等待开放<br>local/ui/state/task-display.js:52 ↳ 等待开放 | **一致**【已复现】 |  |
| 7 | spec:17,460 | 「约」 | local/ui/app.js:457 ↳ 约<br>local/ui/index.html:178 ↳ 约 | **一致**【已复现】 |  |
| 8 | spec:17 | 「约到 xx 过期」 | 未检出（local/ui 全库无逐字/归一命中） | **规格示例格式（「说估算就写约」的格式示例，非禁语）**【符合】 | 对抗复核改列：spec:17 将本串列为「说估算就写约」的格式示例而非禁语，故从禁止示例单列；逐字确未出现。另 state/login.js:62-63 有未接线的 expiryText()（「约到 」+whenText 拼接），全库无调用方，属死代码（条目 10 已引 63 行「以学校校验为准」分支，未提示此函数）。 |
| 9 | spec:17 | 「约剩 N 小时」 | 未检出（local/ui 全库无逐字/归一命中） | **规格禁止示例（红线：不编估算）**【符合】 | 红线示例词，代码未出现即符合。缺席由全库检索直接支持。 |
| 10 | spec:18 | 「以学校校验为准」 | local/ui/state/login.js:63 ↳ 以学校校验为准 | **一致**【已复现】 |  |
| 11 | spec:21 | 「北京时间 + 时分秒 + 状态图形」 | local/ui/state/clock.js:307-308 ↳ /* 顶栏唯一时间入口：正常只显示北京时间 + 时分秒 + 小状态图形。 */ | **规格元描述（描述性，非逐字文案）**【已复现】 | 最接近的代码注释用「小状态图形」，与规格差一个「小」字；实现按 §10 五态执行。 |
| 12 | spec:24 | 「适用于目标学校（校园）专升本学生使用的活动中心」 | 未检出（local/ui 全库无逐字/归一命中） | **代码没有（规格自述待补）**【已复现】 | 全库未检出；与规格 §1.8 自述「首次条款摘要还没有补上，待条款 r5」一致，非缺陷。 |
| 13 | spec:26 | 「为了用 AI 改了日期」 | 未检出（local/ui 全库无逐字/归一命中） | **规格禁止示例（不写开发者对话）**【符合】 |  |
| 14 | spec:36,79 | 「正在加载活动列表。」 | local/ui/controllers/plan.js:454 ↳ 正在加载活动列表。 | **一致**【已复现】 |  |
| 15 | spec:41,257,262 | 「待核对」 | local/ui/styles.css:917 ↳ 待核对<br>local/ui/controllers/plan-events.js:93 ↳ 待核对 | **一致**【已复现】 |  |
| 16 | spec:45,194,459 | 「报名截止」 | local/ui/index.html:71 ↳ 报名截止<br>local/ui/m/app.js:155 ↳ 报名截止 | **一致**【已复现】 |  |
| 17 | spec:47,155,168 | 「登录已失效」 | local/ui/m/index.html:43 ↳ 登录已失效<br>local/ui/state/conflict.js:159 ↳ 登录已失效 | **一致**【已复现】 |  |
| 18 | spec:49 | "刷新" | local/ui/app.js:130 ↳ 刷新<br>local/ui/index.html:26 ↳ 刷新 | **一致**【已复现】 |  |
| 19 | spec:51 | "重新选择未成功的场次" | local/ui/index.html:89 ↳ 重新选择未成功的场次<br>local/ui/controllers/plan.js:344 ↳ 重新选择未成功的场次 | **一致**【已复现】 |  |
| 20 | spec:55 | 「浏览器」 | local/ui/app.js:446 ↳ 浏览器<br>local/ui/index.html:73 ↳ 浏览器 | **一致**【已复现】 |  |
| 21 | spec:55 | 「请」 | local/ui/index.html:143 ↳ 请<br>local/ui/index.html:144 ↳ 请 | **一致**【已复现】 |  |
| 22 | spec:64 | 「打开顶栏的登录状态，点「登录」，在打开的浏览器中完成登录」 | local/ui/views/login.js:54 ↳ 打开顶栏的登录状态，点「登录」，在打开的浏览器中完成登录 | **一致**【已复现】 |  |
| 23 | spec:65 | 「正在检查登录状态，马上就好」 | local/ui/views/login.js:48 ↳ 正在检查登录状态，马上就好 | **一致**【已复现】 |  |
| 24 | spec:66 | 「刚核对过，可以加载活动」 | local/ui/views/login.js:74 ↳     note = "学校确认登录有效；有效多久学校不公布，工具不估算"; | **不一致**【已复现】 | 规格附加句「刚核对过，可以加载活动」；代码附加句如引（上一行注释说明只报上次校验时刻）。对抗复核：引用行现盘为 73，内容逐字不变。 |
| 25 | spec:67 | 「重新登录后可继续使用」 | local/ui/views/login.js:66 ↳ 重新登录后可继续使用 | **一致**【已复现】 |  |
| 26 | spec:68 | 「暂时无法确认登录状态；检查网络后点「刷新」，先不用重新登录」 | local/ui/views/login.js:59 ↳ 暂时无法确认登录状态；检查网络后点「刷新」，先不用重新登录 | **一致**【已复现】 |  |
| 27 | spec:69,247 | 「正在停止计划；已报名的场次不受影响」 | local/ui/views/login.js:22 ↳ 正在停止计划；已报名的场次不受影响 | **一致**【已复现】 |  |
| 28 | spec:69,247 | 「登录状态保持不变；计划进度见报名区域」 | local/ui/views/login.js:23 ↳ 登录状态保持不变；计划进度见报名区域 | **一致**【已复现】 |  |
| 29 | spec:70 | 「不读取登录信息、不访问学校，只演示界面与流程」 | local/ui/views/login.js:30 ↳ 不读取登录信息、不访问学校，只演示界面与流程 | **一致**【已复现】 |  |
| 30 | spec:70 | 「内存样例」 | local/ui/views/login.js:29 ↳ 内存样例 | **一致**【已复现】 |  |
| 31 | spec:72 | 「约剩 17 小时」 | 未检出（local/ui 全库无逐字/归一命中） | **规格禁止示例（红线：不编估算）**【符合】 |  |
| 32 | spec:72 | 「过期 / 失效」 | 未检出（local/ui 全库无逐字/归一命中） | **规格禁止示例（unknown 一律不写成「过期 / 失效」）**【符合】 | 枚举拆分命中（tick.js、index.html 的「过期」「失效」）均属其他合法语境，本句未作为独立文案出现。 |
| 33 | spec:73 | 「正在处理」 | local/ui/views/login.js:19 ↳ /* 忙时胶囊只表达登录结论，不拿「正在处理」替换它（计划进度属于报名区域） */ | **规格禁止示例（忙时不拿「正在处理」替换登录结论）**【符合】 | 对抗复核改判：spec:73 为否定式提及，全库无用户可见「正在处理」；login.js:19 为重申该禁令的注释，原「一致」把注释命中当成了用户可见文案。 |
| 34 | spec:80 | 「演示模式不登录」 | local/ui/controllers/plan.js:411 ↳ 演示模式不登录 | **一致**【已复现】 |  |
| 35 | spec:80 | 「演示模式不联网。这里不会打开学校登录页。」 | local/ui/controllers/plan.js:411 ↳ setResult({ ok: "partial", title: "演示模式不登录", text: res.text \|\| "演示模式不联网。" });<br>local/app.py:2270 ↳     "text": "演示模式不联网：这里不会打开学校登录页。" | **不一致**【已复现】 | 规格为两句；前端兜底只有前半句，后端（界面前端作用域之外，补充证据）用冒号连成一句。 |
| 36 | spec:81 | 「再点一次「登录」试试。」 | local/ui/controllers/plan.js:430 ↳ 再点一次「登录」试试。 | **一致**【已复现】 |  |
| 37 | spec:81 | 「登录没能开始」 | local/ui/controllers/plan.js:430 ↳ 登录没能开始<br>local/ui/controllers/plan.js:438 ↳ 登录没能开始 | **一致**【已复现】 |  |
| 38 | spec:82 | 「登录窗口被关掉了」 | local/ui/controllers/plan.js:479 ↳ 登录窗口被关掉了 | **一致**【已复现】 |  |
| 39 | spec:82 | 「登录还没完成，窗口就关了。点「再试一次」重新打开。」 | local/ui/controllers/plan.js:479 ↳ 登录还没完成，窗口就关了。点「再试一次」重新打开。 | **一致**【已复现】 |  |
| 40 | spec:83 | 「浏览器窗口里一直没完成登录，超时了。」 | local/ui/controllers/plan.js:480 ↳ 浏览器窗口里一直没完成登录，超时了。 | **一致**【已复现】 |  |
| 41 | spec:83 | 「等了 10 分钟还没登录成功」 | local/ui/controllers/plan.js:480 ↳ 等了 10 分钟还没登录成功 | **一致**【已复现】 |  |
| 42 | spec:84 | 「打不开学校的登录页」 | local/ui/controllers/plan.js:481 ↳ 打不开学校的登录页 | **一致**【已复现】 |  |
| 43 | spec:84 | 「检查网络、校园网或代理，然后再试一次。」 | local/ui/controllers/plan.js:481 ↳ 检查网络、校园网或代理，然后再试一次。 | **一致**【已复现】 |  |
| 44 | spec:85 | 「登录后学校那边没校验通过」 | local/ui/controllers/plan.js:482 ↳ 登录后学校那边没校验通过 | **一致**【已复现】 |  |
| 45 | spec:85 | 「登录状态存下来了，但学校那边没校验通过。再登录一次试试。」 | local/ui/controllers/plan.js:482 ↳ 登录状态存下来了，但学校那边没校验通过。再登录一次试试。 | **一致**【已复现】 |  |
| 46 | spec:86 | 「没找到能用的浏览器」 | local/ui/controllers/plan.js:483 ↳ 没找到能用的浏览器 | **一致**【已复现】 |  |
| 47 | spec:86 | 「这台电脑上要有 Chrome 或 Edge，装好以后再试。」 | local/ui/controllers/plan.js:483 ↳ 这台电脑上要有 Chrome 或 Edge，装好以后再试。 | **一致**【已复现】 |  |
| 48 | spec:87 | 「登录没完成」 | local/ui/controllers/plan.js:484 ↳ 登录没完成 | **一致**【已复现】 |  |
| 49 | spec:95 | 「组件有问题，处理办法看页面顶部的提示。」 | local/ui/views/list.js:295 ↳ 组件有问题，处理办法看页面顶部的提示。 | **一致**【已复现】 |  |
| 50 | spec:96 | 「恢复网络后点「刷新」重试。」 | local/ui/controllers/tick.js:121 ↳ 恢复网络后点「刷新」重试。 | **一致**【已复现】 |  |
| 51 | spec:96 | 「暂时无法加载」 | local/ui/controllers/tick.js:136 ↳ 暂时无法加载 | **一致**【已复现】 |  |
| 52 | spec:97 | 「一共 N 场，换个关键词，或清除筛选看完整列表。」 | local/ui/views/list.js:310 ↳ 一共 " + S.items.length + " 场，换个关键词，或清除筛选看完整列表。 | **一致（模板归一：占位/拼接写法归一后命中）**【已复现】 | 规格占位（N/M/\<…>/HH:MM 等）对应代码变量或字符串拼接。 |
| 53 | spec:98 | 「点「刷新」加载一次；需要登录时，顶部会提示下一步。」 | local/ui/views/list.js:325-327 ↳ text.innerHTML = termsLocked() ? … : \<span style="white-space:nowrap">点「刷新」加载一次；\</span>需要登录时，顶部会提示下一步。; | **一致（HTML span 不改 textContent）**【已复现】 | list.js 注释明说「textContent 一字不变（span 不产生文本）」，契约断言按原文比对。对抗复核：原引行 339-340 在现盘与基线 a85209e（275-277）均不含该代码，现盘实际 325-327，内容逐字不变。 |
| 54 | spec:99 | 「正在核对已保存的登录，稍等一下；这段时间先不用重新登录。」 | local/ui/views/list.js:343 ↳ text.innerHTML = 正在核对已保存的登录，稍等一下；\<span style="white-space:nowrap">这段时间先不用重新登录。\</span>; | **一致（HTML span 不改 textContent）**【已复现】 | 对抗复核：原引行 347 在现盘与基线 a85209e（293）均不含该代码，现盘实际 343，内容逐字不变。 |
| 55 | spec:100 | 「点右上角「登录」，在打开的浏览器中完成登录，然后点「刷新」。」 | local/ui/views/list.js:353 ↳ text.innerHTML = \<span style="white-space:nowrap">打开顶栏的登录状态，点「登录」，\</span>在打开的浏览器中完成登录，\<span style="white-space:nowrap">然后点「刷新」。\</span>; | **不一致**【已复现】 | 规格以「点右上角」开头；代码以「打开顶栏的登录状态」开头，其余一致。 |
| 56 | spec:101 | 「点右上角「重新登录」，完成后点「刷新」。」 | local/ui/views/list.js:360 ↳ text.innerHTML = \<span style="white-space:nowrap">打开顶栏的登录状态，点「重新登录」，完成后点「刷新」。\</span>; | **不一致**【已复现】 | 同上。 |
| 57 | spec:102 | 「请检查网络后点「刷新」。」 | local/ui/views/list.js:361 ↳ 请检查网络后点「刷新」。 | **一致**【已复现】 |  |
| 58 | spec:103 | 「登录是有效的，学校这次没有返回可报名活动；稍后点「刷新」再看。」 | local/ui/views/list.js:367-368 ↳ text.innerHTML = 这不是登录问题。\<span style="white-space:nowrap">稍后点“刷新”再看，\</span>学校发布新活动后会出现在这里。; | **不一致**【已复现】 | 规格句整句未采用；list.js:259 注释「“登录是有效的”比说“暂时无法确认”更伤人」可佐证是有意弃用。 |
| 59 | spec:105 | 「—」 | local/ui/app.js:18 ↳ $("#help-version").textContent = info && info.version ? String(info.version) : "—"; | **一致（占位值）**【已复现】 | 指标口径「未拉到或失败 → “—”」的占位值。 |
| 60 | spec:109 | 「已截止」 | local/ui/m/app.js:181 ↳ 已截止<br>local/ui/state/filters.js:160 ↳ 已截止 | **一致**【已复现】 |  |
| 61 | spec:109,202,510 | 「立即报名」 | local/ui/index.html:144 ↳ 立即报名<br>local/ui/controllers/plan.js:105 ↳ 立即报名 | **一致**【已复现】 |  |
| 62 | spec:109,110 | 「预报名」 | local/ui/index.html:6 ↳ 预报名<br>local/ui/index.html:17 ↳ 预报名 | **一致**【已复现】 |  |
| 63 | spec:111 | 「选择要报名的活动」 | 最接近 local/ui/state/store.js:36 ↳ { target: "row", interactive: true, title: "勾选想报的活动", | **代码没有**【已复现】 | §6 未选择提示；代码无此句。最接近为五步引导第 2 步标题（引导已改五步，见 spec:370 汇总条目）。 |
| 64 | spec:112 | 「先取消报名」 | 未检出（local/ui 全库无逐字/归一命中） | **规格禁止示例（不写「先取消报名」）**【符合】 |  |
| 65 | spec:112 | 「此活动已报名，请从本次计划中移除。」 | local/ui/views/selection.js:35 ↳ 此活动已报名，请从本次计划中移除。 | **一致**【已复现】 |  |
| 66 | spec:114 | 「这两场活动的举办时间重叠，只能选择其中一场」 | local/ui/state/filters.js:299 ↳ S.selectionNotice = "与「" + conflict.name + "」的活动时间重叠，同一计划只能选择其中一场。已保留原选择。"; | **不一致**【已复现】 | 规格「这两场活动的举办时间重叠，只能选择其中一场」；代码句如引并拼活动名与时段。 |
| 67 | spec:115,120 | 「报名时间待公布」 | local/ui/views/list.js:110 ↳ 报名时间待公布<br>local/ui/views/list.js:94 ↳ 报名时间待公布 | **一致**【已复现】 |  |
| 68 | spec:115 | 「活动信息已变化，请刷新后重新确认」 | 最接近 local/ui/views/list.js:110 ↳ if (unknown.length) html += groupHtml("报名时间待公布", unknown.sort(byStart), "unknown", "公布以后才能到点报名"); | **代码没有**【已复现】 | 同句后半「报名时间待公布」存在；前一句未实现。 |
| 69 | spec:116 | 「尚未公布」 | 未检出（local/ui 全库无逐字/归一命中） | **规格禁止示例（数据异常不自动写成「尚未公布」）**【符合】 | 代码在用词是「待公布」（合法场景），无「尚未公布」。 |
| 70 | spec:117,191,220 | 「待公布」 | local/ui/index.html:56 ↳ 待公布<br>local/ui/state/labels.js:82 ↳ 待公布 | **一致**【已复现】 |  |
| 71 | spec:117 | 「未知」 | local/ui/index.html:21 ↳ 未知<br>local/ui/controllers/tick.js:145 ↳ 未知 | **一致**【已复现】 |  |
| 72 | spec:119,192,220 | 「待校准」 | local/ui/controllers/tick.js:58 ↳ 待校准<br>local/ui/state/labels.js:82 ↳ 待校准 | **一致**【已复现】 |  |
| 73 | spec:119 | 「状态待确认」 | local/ui/views/plan-panel.js:327 ↳ 状态待确认 | **一致**【已复现】 |  |
| 74 | spec:120 | 「没有可报名场次」 | 未检出（local/ui 全库无逐字/归一命中） | **规格禁止示例（不得断言）**【符合】 | 代码在用的是「没有可报名的场次」标题（§6.1，另条一致），无本句。 |
| 75 | spec:121 | 「无法找到所需程序组件。请重新下载完整版本，再选择「重新检查」。」 | local/ui/controllers/refresh.js:296 ↳ 无法找到所需程序组件。请重新下载完整版本，再选择「重新检查」。 | **一致**【已复现】 |  |
| 76 | spec:122 | 「没跟着程序一起到位」 | 未检出（local/ui 全库无逐字/归一命中） | **规格禁止示例（开发对话口吻）**【符合】 |  |
| 77 | spec:123 | 「选择活动后可在此查看报名计划。」 | 未检出（local/ui 全库无逐字/归一命中） | **已废止旧句（规格声明不再写）**【符合】 |  |
| 78 | spec:124,172 | 「开始报名计划」 | local/ui/index.html:85 ↳ 开始报名计划<br>local/ui/index.html:119 ↳ 开始报名计划 | **一致**【已复现】 |  |
| 79 | spec:125 | 「选中后马上执行」 | 未检出（local/ui 全库无逐字/归一命中） | **规格禁止示例（不写「选中后马上执行」）**【符合】 |  |
| 80 | spec:140 | 「开放中」 | local/ui/state/labels.js:33 ↳ 开放中<br>local/ui/state/labels.js:40 ↳ 开放中 | **一致**【已复现】 |  |
| 81 | spec:140,146 | 「选这一场」 | local/ui/index.html:67 ↳ 选这一场<br>local/ui/styles.css:209 ↳ 选这一场 | **一致**【已复现】 |  |
| 82 | spec:142 | 「查看时间详情」 | local/ui/index.html:20 ↳ 查看时间详情<br>local/ui/views/clock.js:28 ↳ 查看时间详情 | **一致**【已复现】 |  |
| 83 | spec:144,168,169 | 「刷新」 | local/ui/app.js:130 ↳ 刷新<br>local/ui/index.html:26 ↳ 刷新 | **一致**【已复现】 |  |
| 84 | spec:148 | 「修改中」 | local/ui/views/plan-panel.js:124 ↳ 修改中<br>local/ui/controllers/tick.js:69 ↳ 修改中 | **一致**【已复现】 |  |
| 85 | spec:148 | 「已暂停」 | local/ui/index.html:63 ↳ 已暂停<br>local/ui/index.html:301 ↳ 已暂停 | **一致**【已复现】 |  |
| 86 | spec:148 | 「已选 N 场」 | local/ui/views/plan-panel.js:125 ↳ box.textContent = "已选 " + items.length + " 场";<br>local/ui/views/plan-panel.js:1323 ↳ title = "已选 " + items.length + " 场"; | **一致**【已复现】 | 对抗复核：原引行 122 为注释；实际渲染在 125/1323（拼接，同条目 91 归一口径），内容逐字不变。 |
| 87 | spec:148 | 「报名计划」 | local/ui/index.html:17 ↳ 报名计划<br>local/ui/index.html:51 ↳ 报名计划 | **一致**【已复现】 |  |
| 88 | spec:149 | 「X 场立即报名，Y 场预报名等开放」 | local/ui/views/plan-panel.js:130-135 ↳ return [instant ? instant + " 场立即报名" : "", pre ? pre + " 场预报名等开放" : ""].filter(Boolean).join("，"); | **一致**【已复现】 | 对抗复核：原引行 129 为注释；实际渲染在 selectionSummary（130-135），为 0 的一半不写，拼接归一后命中（同条目 91 归一口径），内容逐字不变。 |
| 89 | spec:150,190,220 | 「明天 / 后天 / N 天后」 | local/ui/state/time.js:94 ↳ if (diff === 1) return "明天";<br>local/ui/state/time.js:95 ↳ if (diff === 2) return "后天";<br>local/ui/state/time.js:106 ↳ if (diff > 2) return diff + " 天后"; | **一致**【已复现】 | 对抗复核：原引 time.js:102、plan-panel.js:137 均为注释；实际渲染在 time.js:94/95/106（枚举拆分口径，同条目 32 处理），内容逐字不变。 |
| 90 | spec:150 | 「现在」 | local/ui/index.html:222 ↳ 现在<br>local/ui/index.html:269 ↳ 现在 | **一致**【已复现】 |  |
| 91 | spec:150 | 「立即报名 N 场」 | local/ui/views/plan-panel.js:472 ↳ 立即报名 " + count + " 场 | **一致（模板归一：占位/拼接写法归一后命中）**【已复现】 | 规格占位（N/M/\<…>/HH:MM 等）对应代码变量或字符串拼接。 |
| 92 | spec:150,191 | 「预报名 1 场」 | local/ui/views/plan-panel.js:473 ↳ 预报名 1 场 | **一致**【已复现】 |  |
| 93 | spec:150 | 「预报名，同时提交 N 场」 | local/ui/views/plan-panel.js:473 ↳ 预报名，同时提交 " + count + " 场 | **一致（模板归一：占位/拼接写法归一后命中）**【已复现】 | 规格占位（N/M/\<…>/HH:MM 等）对应代码变量或字符串拼接。 |
| 94 | spec:151 | 「修改」 | local/ui/app.js:311 ↳ 修改<br>local/ui/index.html:68 ↳ 修改 | **一致**【已复现】 |  |
| 95 | spec:151 | 「尝试 \<时长>，\<最多 N 次 / 不限次数>」 | local/ui/index.html:68 ↳ 尝试 2 分钟，<br>local/ui/views/plan-panel.js:485 ↳ 尝试 2 分钟， | **一致（模板归一：占位/拼接写法归一后命中）**【已复现】 | 规格占位（N/M/\<…>/HH:MM 等）对应代码变量或字符串拼接。 |
| 96 | spec:151 | 「收起」 | local/ui/app.js:311 ↳ 收起<br>local/ui/index.html:13 ↳ 收起 | **一致**【已复现】 |  |
| 97 | spec:153 | `!` | local/ui/views/plan-panel.js:346 ↳ 同上（c.ok ? "✓" : "!"） | **一致**【已复现】 |  |
| 98 | spec:153 | `✓` | local/ui/views/plan-panel.js:346 ↳ + '">\<i aria-hidden="true">' + (c.ok ? "✓" : "!") + "\</i>" + esc(c.text) + "\</span>").join("");<br>local/ui/views/plan-panel.js:651 ↳ frame: "ok", led: ["✓", "green"] }; | **一致**【已复现】 | 检查条小标记，与「!」同一三元输出。对抗复核：证据串引号形变已按原码修正（首段实为单引号 JS 串 `'">\<i aria-hidden="true">'`）。 |
| 99 | spec:154 | 「条款状态没能确认」 | local/ui/views/plan-panel.js:322 ↳ 条款状态没能确认<br>local/ui/views/plan-panel.js:1350 ↳ 条款状态没能确认 | **一致**【已复现】 |  |
| 100 | spec:154 | 「程序组件缺失」 | local/ui/controllers/refresh.js:296 ↳ 程序组件缺失<br>local/ui/state/conflict.js:148 ↳ 程序组件缺失 | **一致**【已复现】 |  |
| 101 | spec:154 | 「还没有同意使用条款」 | local/ui/views/plan-panel.js:322 ↳ 还没有同意使用条款<br>local/ui/views/plan-panel.js:1355 ↳ 还没有同意使用条款 | **一致**【已复现】 |  |
| 102 | spec:154 | 「还没有同意新版条款」 | local/ui/views/plan-panel.js:322 ↳ 还没有同意新版条款 | **一致**【已复现】 |  |
| 103 | spec:155 | 「北京时间待校准」 | local/ui/views/plan-panel.js:330 ↳ 北京时间待校准 | **一致**【已复现】 |  |
| 104 | spec:155,168 | 「正在登录」 | local/ui/index.html:390 ↳ 正在登录<br>local/ui/state/conflict.js:146 ↳ 正在登录 | **一致**【已复现】 |  |
| 105 | spec:155 | 「登录状态待确认」 | local/ui/views/plan-panel.js:327 ↳ 登录状态待确认 | **一致**【已复现】 |  |
| 106 | spec:155,168 | 「还没有登录」 | local/ui/views/plan-panel.js:328 ↳ 还没有登录<br>local/ui/views/plan-panel.js:432 ↳ 还没有登录 | **一致**【已复现】 |  |
| 107 | spec:156 | 「登录、北京时间和举办时间都没问题」 | local/ui/views/plan-panel.js:333 ↳ 登录、北京时间和举办时间都没问题 | **一致**【已复现】 |  |
| 108 | spec:156 | 「登录和北京时间都没问题」 | local/ui/views/plan-panel.js:333 ↳ 登录和北京时间都没问题 | **一致**【已复现】 |  |
| 109 | spec:158,172 | 「仍然开始报名计划」 | local/ui/m/app.js:1027 ↳ 仍然开始报名计划<br>local/ui/views/plan-panel.js:1234 ↳ 仍然开始报名计划 | **一致**【已复现】 |  |
| 110 | spec:159 | 「现在连不上网。到开放时间还没恢复，就提交不出去。」 | local/ui/views/plan-panel.js:373 ↳ 现在连不上网。到开放时间还没恢复，就提交不出去。 | **一致**【已复现】 |  |
| 111 | spec:160 | 「北京时间在用上次的校准结果，误差\<…>，工具正在自动重试校准。」 | local/ui/views/plan-panel.js:378 ↳     const err = Number.isFinite(ms) && ms > 0 ? "，误差" + clockUncertaintyText(ms) : "";<br>local/ui/views/plan-panel.js:379 ↳     list.push({ tone: "warn", text: "北京时间在用上次的校准结果" + err + "，工具正在自动重试校准。" }); | **一致（拼接；无误差时段落整段省略）**【已复现】 | 与规格「拿不到误差就去掉「，误差\<…>」一段」一致。 |
| 112 | spec:160 | 「，误差\<…>」 | local/ui/views/plan-panel.js:378 ↳ ，误差 | **一致（模板归一：占位/拼接写法归一后命中）**【已复现】 | 规格占位（N/M/\<…>/HH:MM 等）对应代码变量或字符串拼接。 |
| 113 | spec:161 | 「要等到\<[明天 / 后天 / N 天后 ]HH:MM>，\<原因>。中途登录失效要你\<输验证码 / 重新登录>；开放前 100 秒内失效，那场就结束。」 | local/ui/views/plan-panel.js:389 ↳ const missing = has ? "验证码识别没装" : (cred.paused ? "保存的密码学校不认" : "自动登录没开");<br>local/ui/views/plan-panel.js:392-394 ↳ text: "要等到" + (/^\d/.test(until) ? " " : "") + until + "，" + missing + "。中途登录失效要你" + (has ? "输验证码" : "重新登录") + "；开放前 100 秒内失效，那场就结束。", | **一致（拼接）**【已复现】 | \<[明天 / 后天 / N 天后 ]HH:MM> 由 hmsDay 生成（跨天才带前缀）；原因三选一与规格 §6.1 一致。 |
| 114 | spec:162 | 「保存的密码学校不认」 | local/ui/index.html:301 ↳ 保存的密码学校不认<br>local/ui/views/plan-panel.js:389 ↳ 保存的密码学校不认 | **一致**【已复现】 |  |
| 115 | spec:162,415 | 「去保存」 | local/ui/index.html:244 ↳ 去保存<br>local/ui/views/plan-panel.js:395 ↳ 去保存 | **一致**【已复现】 |  |
| 116 | spec:162 | 「去安装」 | local/ui/views/plan-panel.js:395 ↳ 去安装<br>local/ui/app.js:315 ↳ 去安装 | **一致**【已复现】 |  |
| 117 | spec:162 | 「自动登录没开」 | local/ui/m/app.js:371 ↳ 自动登录没开<br>local/ui/views/plan-panel.js:389 ↳ 自动登录没开 | **一致**【已复现】 |  |
| 118 | spec:162 | 「输验证码」 | local/ui/index.html:244 ↳ 输验证码<br>local/ui/views/phone.js:346 ↳ 输验证码 | **一致**【已复现】 |  |
| 119 | spec:162,168,225 | 「重新登录」 | local/ui/index.html:148 ↳ 重新登录<br>local/ui/index.html:283 ↳ 重新登录 | **一致**【已复现】 |  |
| 120 | spec:162 | 「验证码识别没装」 | local/ui/views/plan-panel.js:389 ↳ 验证码识别没装 | **一致**【已复现】 |  |
| 121 | spec:163 | 「「\<第一场名>」[等 N 场]没给报名截止时间，“直到报名截止”对它只会尝试 2 分钟。」 | local/ui/views/plan-panel.js:401-402 ↳ text: "「" + noEnd[0].name + "」" + (noEnd.length > 1 ? "等 " + noEnd.length + " 场" : "") + "没给报名截止时间，“直到报名截止”对它只会尝试 2 分钟。" }); | **一致（拼接+可选段）**【已复现】 |  |
| 122 | spec:163 | 「直到报名截止」 | local/ui/index.html:71 ↳ 直到报名截止<br>local/ui/m/app.js:375 ↳ 直到报名截止 | **一致**【已复现】 |  |
| 123 | spec:163 | “直到报名截止” | local/ui/index.html:71 ↳ 直到报名截止<br>local/ui/m/app.js:375 ↳ 直到报名截止 | **一致**【已复现】 |  |
| 124 | spec:164 | 「有场次在 24 小时以后才开放，计划要一直运行到那时。这段时间电脑不能关机或睡眠。」 | local/ui/views/plan-panel.js:406 ↳ 有场次在 24 小时以后才开放，计划要一直运行到那时。这段时间电脑不能关机或睡眠。 | **一致**【已复现】 |  |
| 125 | spec:166 | 「还差一步：\<缺什么>」 | local/ui/views/phone.js:581 ↳ 还差一步：<br>local/ui/views/phone.js:582 ↳ 还差一步： | **一致（模板归一：占位/拼接写法归一后命中）**【已复现】 | 规格占位（N/M/\<…>/HH:MM 等）对应代码变量或字符串拼接。 |
| 126 | spec:167 | 「先同意使用条款」 | local/ui/state/conflict.js:147 ↳ 先同意使用条款<br>local/ui/views/plan-panel.js:427 ↳ 先同意使用条款 | **一致**【已复现】 |  |
| 127 | spec:167 | 「先同意新版条款」 | local/ui/views/plan-panel.js:427 ↳ 先同意新版条款 | **一致**【已复现】 |  |
| 128 | spec:167 | 「先重新确认条款」 | local/ui/views/plan-panel.js:427 ↳ 先重新确认条款 | **一致**【已复现】 |  |
| 129 | spec:167 | 「查看条款」 | local/ui/index.html:320 ↳ 查看条款<br>local/ui/views/list.js:326 ↳ 查看条款 | **一致**【已复现】 |  |
| 130 | spec:167 | 「程序组件缺失，看顶部提示」 | local/ui/state/conflict.js:148 ↳ 程序组件缺失，看顶部提示<br>local/ui/views/plan-panel.js:422 ↳ 程序组件缺失，看顶部提示 | **一致**【已复现】 |  |
| 131 | spec:168 | 「去登录」 | local/ui/views/plan-panel.js:432 ↳ 去登录<br>local/ui/app.js:344 ↳ 去登录 | **一致**【已复现】 |  |
| 132 | spec:168 | 「正在自动登录」 | local/ui/m/app.js:354 ↳ 正在自动登录<br>local/ui/m/app.js:1046 ↳ 正在自动登录 | **一致**【已复现】 |  |
| 133 | spec:168 | 「登录状态还没确认」 | local/ui/views/plan-panel.js:434 ↳ 登录状态还没确认<br>local/ui/views/plan-panel.js:436 ↳ 登录状态还没确认 | **一致**【已复现】 |  |
| 134 | spec:169 | 「北京时间还没校准」 | local/ui/views/plan-panel.js:439 ↳ 北京时间还没校准<br>local/ui/views/plan-panel.js:1383 ↳ 北京时间还没校准 | **一致**【已复现】 |  |
| 135 | spec:169 | 「活动列表还没加载」 | local/ui/views/plan-panel.js:440 ↳ 活动列表还没加载 | **一致**【已复现】 |  |
| 136 | spec:169 | 「重新校准」 | local/ui/controllers/clock.js:33 ↳ 重新校准<br>local/ui/m/app.js:366 ↳ 重新校准 | **一致**【已复现】 |  |
| 137 | spec:170 | 「先在时刻表勾选活动」 | local/ui/views/plan-panel.js:442 ↳ 先在时刻表勾选活动 | **一致**【已复现】 |  |
| 138 | spec:170 | 「学校还没有可选的活动」 | local/ui/views/plan-panel.js:442 ↳ 学校还没有可选的活动 | **一致**【已复现】 |  |
| 139 | spec:170 | 「已选场次有问题，看上面的提醒」 | local/ui/views/plan-panel.js:445 ↳ 已选场次有问题，看上面的提醒 | **一致**【已复现】 |  |
| 140 | spec:172,354 | 「北京时间未校准」 | local/ui/views/plan-panel.js:1233 ↳ 北京时间未校准 | **一致**【已复现】 |  |
| 141 | spec:172 | 「重新开始计划」 | local/ui/views/plan-panel.js:1233 ↳ 重新开始计划 | **一致**【已复现】 |  |
| 142 | spec:173 | 「正在提交…」 | local/ui/views/plan-panel.js:1232 ↳ 正在提交… | **一致**【已复现】 |  |
| 143 | spec:173,255,255 | 「正在确认是否启动…」 | local/ui/views/plan-panel.js:1231 ↳ 正在确认是否启动… | **一致**【已复现】 |  |
| 144 | spec:173 | 「计划运行中」 | local/ui/index.html:307 ↳ 计划运行中<br>local/ui/index.html:323 ↳ 计划运行中 | **一致**【已复现】 |  |
| 145 | spec:175 | 「已结束的 N 场不受影响。」 | local/ui/views/plan-panel.js:278 ↳ 已结束的 " + done + " 场不受影响。 | **一致（模板归一：占位/拼接写法归一后命中）**【已复现】 | 规格占位（N/M/\<…>/HH:MM 等）对应代码变量或字符串拼接。 |
| 146 | spec:175 | 「计划已暂停，重新开始前不会自动报名。」 | local/ui/index.html:63 ↳ 计划已暂停，重新开始前不会自动报名。<br>local/ui/views/plan-panel.js:276 ↳ 计划已暂停，重新开始前不会自动报名。 | **一致**【已复现】 |  |
| 147 | spec:176 | 「放弃修改，按原计划继续」 | local/ui/index.html:87 ↳ 放弃修改，按原计划继续 | **一致**【已复现】 |  |
| 148 | spec:176 | 「离最近一场开放只剩 \<时长>。」 | local/ui/views/plan-panel.js:288 ↳ 离最近一场开放只剩 " + durText(gap) + "。 | **一致（模板归一：占位/拼接写法归一后命中）**【已复现】 | 规格占位（N/M/\<…>/HH:MM 等）对应代码变量或字符串拼接。 |
| 149 | spec:178 | 「同意条款后才能报名」 | local/ui/views/plan-panel.js:44 ↳ 同意条款后才能报名<br>local/ui/views/plan-panel.js:977 ↳ 同意条款后才能报名 | **一致**【已复现】 |  |
| 150 | spec:178,347 | 「时间待校准」 | local/ui/views/plan-panel.js:105 ↳ 时间待校准<br>local/ui/views/plan-panel.js:106 ↳ 时间待校准 | **一致**【已复现】 |  |
| 151 | spec:178 | 「正在加载」 | local/ui/controllers/plan.js:454 ↳ 正在加载<br>local/ui/views/list.js:70 ↳ 正在加载 | **一致**【已复现】 |  |
| 152 | spec:178 | 「活动未加载」 | local/ui/views/plan-panel.js:987 ↳ 活动未加载 | **一致**【已复现】 |  |
| 153 | spec:178 | 「重新确认条款后才能报名」 | local/ui/views/plan-panel.js:44 ↳ 重新确认条款后才能报名<br>local/ui/views/plan-panel.js:977 ↳ 重新确认条款后才能报名 | **一致**【已复现】 |  |
| 154 | spec:179 | 「下一批开放 \<时刻>」 | local/ui/views/plan-panel.js:1002 ↳ paintLedLabel("下一批开放", hmsDay(first)); | **一致（两参渲染）**【已复现】 | LED 标签与值分两参，呈现为「下一批开放 \<时刻>」。 |
| 155 | spec:179 | 「已开放，可以立即报名 现在」 | local/ui/views/plan-panel.js:1012 ↳ paintLedLabel("已开放，可以立即报名", "现在");<br>local/ui/views/plan-panel.js:1019 ↳ paintLedLabel("已开放，可以立即报名", "现在"); | **一致（两参渲染）**【已复现】 |  |
| 156 | spec:179 | 「开放时间 待公布」 | local/ui/views/plan-panel.js:944 ↳ paintLedLabel("开放时间", "待公布");<br>local/ui/views/plan-panel.js:950 ↳ paintLedLabel("开放时间", "待校准"); | **一致（两参渲染）**【已复现】 |  |
| 157 | spec:180 | 「暂时没有目标」 | local/ui/views/plan-panel.js:1030 ↳ 暂时没有目标 | **一致**【已复现】 |  |
| 158 | spec:180 | 「最近开放 \<时刻>」 | local/ui/index.html:56 ↳ 最近开放 \<b id="metric-next"> | **一致（模板归一：占位/拼接写法归一后命中）**【已复现】 | 规格占位（N/M/\<…>/HH:MM 等）对应代码变量或字符串拼接。 |
| 159 | spec:184 | 「尝试时长」 | local/ui/index.html:71 ↳ 尝试时长<br>local/ui/m/app.js:375 ↳ 尝试时长 | **一致**【已复现】 |  |
| 160 | spec:185 | 「最多提交次数（0=不限）」 | local/ui/index.html:72 ↳ 最多提交次数（0=不限）<br>local/ui/m/index.html:96 ↳ 最多提交次数（0=不限） | **一致**【已复现】 |  |
| 161 | spec:186 | 「已提交 N 次（上限 M 次）」 | local/ui/views/plan-panel.js:1092 ↳ const head = "已提交 " + attempts + " 次（" + (limited ? "上限 " + cap + " 次" : "不限次数") + "）"; | **一致**【已复现】 | 对抗复核：原引行 1085 为注释；实际渲染在 1092（同条目 162 证据行，拼接归一后命中），内容逐字不变。 |
| 162 | spec:186 | 「已提交 N 次（不限次数）」 | local/ui/views/plan-panel.js:1092 ↳ const head = "已提交 " + attempts + " 次（" + (limited ? "上限 " + cap + " 次" : "不限次数") + "）"; | **一致（拼接）**【已复现】 | 同函数覆盖规格另一变体「已提交 N 次（上限 M 次）」。 |
| 163 | spec:188 | 「已开放，准备提交」 | local/ui/state/task-display.js:101 ↳ if (phase === "preparing") return "已开放，正在准备提交";<br>local/ui/views/plan-panel.js:831 ↳ countDown.textContent = "已开放 · 准备提交 " + view.count + " 场"; | **不一致**【已复现】 | 规格「已开放，准备提交」；代码两处分别为「已开放，正在准备提交」（list.js:421、plan-panel.js:175 同）与「已开放 · 准备提交 N 场」。 |
| 164 | spec:189 | 「本次尝试到 HH:MM:SS」 | local/ui/views/plan-panel.js:925 ↳ paintLedLabel("本次尝试到", "待定");<br>local/ui/views/plan-panel.js:932 ↳ paintLedLabel("本次尝试到", hmsDay(view.retryUntil)); | **一致**【已复现】 | 对抗复核：原引行 921 为注释；实际渲染在 925/932（paintLedLabel 两参，前缀+空格，同条目 169 证据行），内容逐字不变。 |
| 165 | spec:189 | 「正在提交 N 场」 | local/ui/views/list.js:424 ↳ 正在提交 " + view.count + " 场<br>local/ui/views/plan-panel.js:168 ↳ 正在提交 " + count + " 场 | **一致（模板归一：占位/拼接写法归一后命中）**【已复现】 | 规格占位（N/M/\<…>/HH:MM 等）对应代码变量或字符串拼接。 |
| 166 | spec:190 | 「HH:MM:SS · 预报名，同时提交 N 场」 | local/ui/views/plan-panel.js:471-475 ↳ 同上（hmsDay(at) + note 两节点） | **不一致（缺「·」分隔符）**【已复现】 | 同上；m/app.js:175 的 bits.join(" · ") 是手机页另一处状态拼接，与本条无关。 |
| 167 | spec:190 | 「现在 · 立即报名 N 场」 | local/ui/views/plan-panel.js:471-475 ↳ const note = instant ? "立即报名 " + count + " 场" : (count > 1 ? "预报名，同时提交 " + count + " 场" : "预报名 1 场"); … \<div class="bh">\<b>现在\</b>\<span>立即报名 N 场\</span>\</div><br>local/ui/styles.css:882 ↳ .bh { display: flex; align-items: baseline; gap: 8px; … } | **不一致（缺「·」分隔符）**【已复现】 | 批次头是「现在」+「立即报名 N 场」两个节点、CSS 8px 间距；代码无「·」字符（.bh 无 ::after content，【静态推断】基于 styles.css 检索）。 |
| 168 | spec:191 | 「开放时间」 | local/ui/index.html:38 ↳ 开放时间<br>local/ui/index.html:39 ↳ 开放时间 | **一致**【已复现】 |  |
| 169 | spec:194,196,459 | 「本次尝试到」 | local/ui/views/plan-panel.js:925 ↳ 本次尝试到<br>local/ui/views/plan-panel.js:932 ↳ 本次尝试到 | **一致**【已复现】 |  |
| 170 | spec:195 | 「待启动 / 待打开 / 待发生」 | local/ui/views/plan-panel.js:773 ↳ { name: "本次启动", time: runStarted ? routeTime(runStarted) : "待启动", done: runStarted !== null },<br>local/ui/views/plan-panel.js:774 ↳ … : "待准备", done: ready !== null },<br>local/ui/views/plan-panel.js:758 ↳ * 显示「待启动/待打开/待开始」，不得拿计划时刻或当前时间编造 | **不一致**【NEEDS-HUMAN】 | 时间线未发生占位：代码实际用「待启动 / 待准备 / 待定」(773-778)，注释写「待启动/待打开/待开始」，规格写「待启动 / 待打开 / 待发生」——三方不一致。 |
| 171 | spec:196 | 「原定开放」 | local/ui/views/plan-panel.js:775 ↳ 原定开放<br>local/ui/state/task-display.js:27 ↳ 原定开放 | **一致**【已复现】 |  |
| 172 | spec:196 | 「本次启动」 | local/ui/views/clock-pop.js:95 ↳ 本次启动<br>local/ui/views/plan-panel.js:773 ↳ 本次启动 | **一致**【已复现】 |  |
| 173 | spec:197 | 「签到 19:00–19:40」 | local/ui/state/filters.js:47-52 ↳ const timeRange = (start, end) => { … return " " + hm(startTs * 1000) + (endTs && endTs > startTs ? "–" + hm(endTs * 1000) : ""); };<br>local/ui/state/filters.js:56 ↳ else if (item.checkin_required === true) add("签到" + timeRange(item.checkin_start, item.checkin_end), false); | **一致（拼接）**【已复现】 | timeRange 前导空格 + en-dash，渲染即「签到 19:00–19:40」。 |
| 174 | spec:197 | 「签退 21:00–21:20」 | local/ui/state/filters.js:60 ↳ else if (item.checkout_required === true) add("签退" + timeRange(item.checkout_start, item.checkout_end), false); | **一致（拼接）**【已复现】 |  |
| 175 | spec:197 | 「要求 + 时间段」 | local/ui/state/filters.js:43 ↳ /* 真实字段来自详情接口：签到/签退要求 + 时间段。 | **规格元描述（描述性，非逐字文案）**【已复现】 | 对抗复核改判：spec:197「签到/签退按「要求 + 时间段」说」为格式元描述；唯一出现 filters.js:43 为注释，无用户可见命中（同条目 11/262 口径）。 |
| 176 | spec:198 | 「无需签到」 | local/ui/state/filters.js:55 ↳ 无需签到 | **一致**【已复现】 |  |
| 177 | spec:198 | 「无需签退」 | local/ui/state/filters.js:59 ↳ 无需签退 | **一致**【已复现】 |  |
| 178 | spec:198 | 「签到信息同步中」 | local/ui/state/filters.js:57 ↳ 签到信息同步中 | **一致**【已复现】 |  |
| 179 | spec:198 | 「签退信息同步中」 | local/ui/state/filters.js:61 ↳ 签退信息同步中 | **一致**【已复现】 |  |
| 180 | spec:199 | 「无需」 | local/ui/index.html:40 ↳ 无需<br>local/ui/index.html:41 ↳ 无需 | **一致**【已复现】 |  |
| 181 | spec:199 | 「签到时间待确认」 | local/ui/state/filters.js:58 ↳ 签到时间待确认 | **一致**【已复现】 |  |
| 182 | spec:199 | 「签退时间待确认」 | local/ui/state/filters.js:62 ↳ 签退时间待确认 | **一致**【已复现】 |  |
| 183 | spec:200 | 「报名已确认，学校列表正在同步」 | local/ui/views/list.js:178 ↳ 报名已确认，学校列表正在同步 | **一致**【已复现】 |  |
| 184 | spec:201 | 「列表没更新说明没报上」 | 未检出（local/ui 全库无逐字/归一命中） | **规格禁止示例（不说「列表没更新说明没报上」）**【符合】 |  |
| 185 | spec:202 | 「等待报名开放」 | local/ui/views/plan-panel.js:1115 ↳ 等待报名开放 | **一致**【已复现】 |  |
| 186 | spec:203 | 「提前 N 秒打开页面」 | 未检出（local/ui 全库无逐字/归一命中） | **规格禁止示例（已开放场次不得出现）**【符合】 |  |
| 187 | spec:212 | 「，最近：\<原因>」 | local/ui/views/plan-panel.js:172 ↳ ，最近： | **一致（模板归一：占位/拼接写法归一后命中）**【已复现】 | 规格占位（N/M/\<…>/HH:MM 等）对应代码变量或字符串拼接。 |
| 188 | spec:214 | 「即将开放」 | local/ui/m/index.html:48 ↳ 即将开放<br>local/ui/m/index.html:60 ↳ 即将开放 | **一致**【已复现】 |  |
| 189 | spec:216 | 「正在准备报名」 | local/ui/views/plan-panel.js:84 ↳ 正在准备报名<br>local/ui/controllers/plan.js:402 ↳ 正在准备报名 | **一致**【已复现】 |  |
| 190 | spec:216 | 「计划已经接管，正在核对每一场的开放时间。」 | local/ui/views/plan-panel.js:87 ↳ 计划已经接管，正在核对每一场的开放时间。 | **一致**【已复现】 |  |
| 191 | spec:217 | 「正在汇总结果」 | local/ui/views/plan-panel.js:84 ↳ 正在汇总结果<br>local/ui/views/plan-panel.js:851 ↳ 正在汇总结果 | **一致**【已复现】 |  |
| 192 | spec:217 | 「每一场都结束了，正在汇总这一轮的结果。」 | local/ui/views/plan-panel.js:86 ↳ 每一场都结束了，正在汇总这一轮的结果。 | **一致**【已复现】 |  |
| 193 | spec:219 | 「已开放，准备报名 N 场 准备中」 | local/ui/views/plan-panel.js:938 ↳ paintLedLabel("已开放，准备报名 " + view.count + " 场", "准备中"); | **一致（两参渲染）**【已复现】 |  |
| 194 | spec:219 | 「待定」 | local/ui/views/list.js:188 ↳ 待定<br>local/ui/views/plan-panel.js:209 ↳ 待定 | **一致**【已复现】 |  |
| 195 | spec:219 | 「本次尝试到 \<HH:MM:SS>」 | local/ui/views/plan-panel.js:932 ↳ paintLedLabel("本次尝试到", hmsDay(view.retryUntil)); | **一致（模板归一：占位/拼接写法归一后命中）**【已复现】 | 对抗复核：原引行 921 为注释；实际渲染在 932（paintLedLabel 两参，前缀+空格），内容逐字不变。规格占位（N/M/\<…>/HH:MM 等）对应代码变量或字符串拼接。 |
| 196 | spec:220 | 「开放时间 \<HH:MM:SS>」 | local/ui/views/plan-panel.js:955 ↳ paintLedLabel("开放时间", hmsDay(view.openAt)); | **一致（两参渲染）**【已复现】 |  |
| 197 | spec:220 | 「计划状态 准备中 / 汇总中」 | local/ui/views/plan-panel.js:960 ↳ paintLedLabel("计划状态", view.phase === "settling" ? "汇总中" : "准备中"); | **一致（两参渲染）**【已复现】 |  |
| 198 | spec:223 | 「登录失效了，电脑正在自动登录。计划照常等开放，不用你管。」 | local/ui/views/plan-panel.js:562 ↳ 登录失效了，电脑正在自动登录。计划照常等开放，不用你管。 | **一致**【已复现】 |  |
| 199 | spec:223 | 「登录失效了，电脑正在自动登录（最多约 20 秒），成功后接着提交。」 | local/ui/views/plan-panel.js:561 ↳ 登录失效了，电脑正在自动登录（最多约 20 秒），成功后接着提交。 | **一致**【已复现】 |  |
| 200 | spec:224 | 「后面的场次等它结束后重新登录就行。」 | local/ui/views/plan-panel.js:575 ↳ 后面的场次等它结束后重新登录就行。 | **一致**【已复现】 |  |
| 201 | spec:224,225 | “登录失效” | local/ui/index.html:146 ↳ 登录失效<br>local/ui/index.html:148 ↳ 登录失效 | **一致**【已复现】 |  |
| 202 | spec:224 | 「登录失效了。\<正在提交 / 离开放不到 100 秒>，来不及重新登录，\<正在提交的场次 / 这一批>会以“登录失效”结束。」 | local/ui/views/plan-panel.js:573-575 ↳ text = "登录失效了。" + (submitting ? "正在提交" : "离开放不到 100 秒") + "，来不及重新登录，" + (submitting ? "正在提交的场次" : "这一批") + "会以“登录失效”结束。" + (later ? "后面的场次等它结束后重新登录就行。" : ""); | **一致（拼接）**【已复现】 |  |
| 203 | spec:225 | 「登录失效了，计划还在等。只要在 \<时刻> 前重新登录，计划照常继续；否则 \<时刻> 开放的那批会以“登录失效”结束。」 | local/ui/views/plan-panel.js:577-579 ↳ text = "登录失效了，计划还在等。只要在 " + hmsDay(first - LATE_WINDOW_S) + " 前重新登录，计划照常继续；否则 " + hmsDay(first) + " 开放的那批会以“登录失效”结束。"; act = { act: "login", label: "重新登录" }; | **一致（拼接）**【已复现】 |  |
| 204 | spec:227 | 「可以最小化窗口，但不要关闭工具或让电脑睡眠。」 | local/ui/state/store.js:38 ↳ 可以最小化窗口，但不要关闭工具或让电脑睡眠。<br>local/ui/views/plan-panel.js:595 ↳ 可以最小化窗口，但不要关闭工具或让电脑睡眠。 | **一致**【已复现】 |  |
| 205 | spec:227 | 「这个计划是从手机开始的，在电脑和手机上都能看进度、停止。」 | local/ui/views/plan-panel.js:596 ↳ 这个计划是从手机开始的，在电脑和手机上都能看进度、停止。 | **一致**【已复现】 |  |
| 206 | spec:228 | 「修改计划」 | local/ui/index.html:90 ↳ 修改计划<br>local/ui/controllers/plan.js:340 ↳ 修改计划 | **一致**【已复现】 |  |
| 207 | spec:228,273,315 | 「停止计划」 | local/ui/index.html:90 ↳ 停止计划<br>local/ui/index.html:94 ↳ 停止计划 | **一致**【已复现】 |  |
| 208 | spec:230 | 「有场次 100 秒内开放，工具已在准备，现在不能修改。」 | local/ui/views/plan-panel.js:603 ↳ 有场次 100 秒内开放，工具已在准备，现在不能修改。 | **一致**【已复现】 |  |
| 209 | spec:230 | 「有场次正在提交，现在不能修改。」 | local/ui/views/plan-panel.js:602 ↳ 有场次正在提交，现在不能修改。 | **一致**【已复现】 |  |
| 210 | spec:231 | 「还没提交的场次可以放回草稿，改完要重新开始。」 | local/ui/views/plan-panel.js:604 ↳ 还没提交的场次可以放回草稿，改完要重新开始。 | **一致**【已复现】 |  |
| 211 | spec:241 | 「等待提交结果」 | local/ui/views/plan-panel.js:1097 ↳ 等待提交结果<br>local/ui/views/plan-panel.js:1087 ↳ 等待提交结果 | **一致**【已复现】 |  |
| 212 | spec:244 | 「已准备好」 | local/ui/state/task-display.js:98 ↳ 已准备好<br>local/ui/views/phone.js:1080 ↳ 已准备好 | **一致**【已复现】 |  |
| 213 | spec:244 | 「立即报名 · 」 | local/ui/state/task-display.js:72 ↳ 同上 | **一致（拼接前缀）**【已复现】 |  |
| 214 | spec:244 | 「预报名 · 」 | local/ui/state/task-display.js:72 ↳ return RUNNING_STATUSES.indexOf(state) >= 0 && modeText(mode) ? modeText(mode) + " · " : ""; | **一致（拼接前缀）**【已复现】 | 任务卡说明前的模式前缀，modeText 出「预报名/立即报名」。 |
| 215 | spec:245 | 「取消这一场」 | local/ui/controllers/plan.js:272 ↳ 取消这一场<br>local/ui/m/app.js:987 ↳ 取消这一场 | **一致**【已复现】 |  |
| 216 | spec:245 | 「改用页面点击[：\<原因>]。活动页已提前打开」 | local/ui/views/plan-panel.js:1073-1074 ↳ return '\<small class="t-via" data-tone="warn">改用页面点击' + (why ? "：" + esc(why) : "") + "。活动页已提前打开\</small>";<br>local/ui/m/app.js:355 ↳ const via = t.path === "click" ? "；改用页面点击" + (t.path_reason ? "：" + t.path_reason : "") | **一致（拼接+可选原因；HTML 标签包裹）**【已复现】 | 对抗复核：证据串补回丢失的字符串定界引号，已按原码逐字修正。 |
| 217 | spec:245 | 「直接提交，不经过活动页」 | local/ui/views/plan-panel.js:1070 ↳ 直接提交，不经过活动页 | **一致**【已复现】 |  |
| 218 | spec:247,249 | 「已登录」 | local/ui/state/store.js:10 ↳ 已登录<br>local/ui/views/login.js:20 ↳ 已登录 | **一致**【已复现】 |  |
| 219 | spec:248 | 「自动登录中…」 | local/ui/views/login.js:35 ↳ 自动登录中…<br>local/ui/views/login.js:14 ↳ 自动登录中… | **一致**【已复现】 |  |
| 220 | spec:249 | 「登录待确认」 | local/ui/views/login.js:58 ↳ 登录待确认 | **一致**【已复现】 |  |
| 221 | spec:251 | 「未确认」 | local/ui/controllers/plan.js:155 ↳ 未确认<br>local/ui/controllers/terms.js:274 ↳ 未确认 | **一致**【已复现】 |  |
| 222 | spec:256 | 「5 秒内没有确认计划是否启动」 | local/ui/controllers/plan.js:163 ↳ unknown("本机 5 秒内没有回应这次对账。"); | **不一致**【已复现】 | 规格「5 秒内没有确认计划是否启动」；代码「本机 5 秒内没有回应这次对账。」 |
| 223 | spec:256,257 | 「报名失败」 | 未检出（local/ui 全库无逐字/归一命中） | **规格禁止示例（对账不得说成报名失败）**【符合】 |  |
| 224 | spec:256 | 「检查计划状态」 | local/ui/controllers/plan.js:156-158 ↳ text: prefix + "先看下面的任务区或点「刷新」确认当前计划，确认没有在跑再重新开始。", action: { label: "重新确认", run: () => reconcileStart(requestId) }, | **不一致**【已复现】 | 规格动作「检查计划状态」（只读查询）；代码按钮「重新确认」，动作同为只读对账 reconcileStart。 |
| 225 | spec:256 | 「结果未确认」 | local/ui/controllers/plan.js:155 ↳ 结果未确认<br>local/ui/controllers/terms.js:274 ↳ 结果未确认 | **一致**【已复现】 |  |
| 226 | spec:257 | 「已提交 N 次，没有拿到确定回应」 | local/ui/controllers/plan-events.js:93 ↳ addLog("[?] 结果待核对：" + name + " · 已提交 " + tried + " 次，没有确定回应"); | **不一致**【已复现】 | 规格「没有拿到确定回应」；代码少「拿到」二字，且该句在运行记录（addLog）不在任务卡；任务卡待核对说明（spec:306）逐字一致。 |
| 227 | spec:257 | 「没抢到」 | local/ui/controllers/tick.js:102 ↳ 没抢到<br>local/ui/controllers/plan-events.js:91 ↳ 没抢到 | **一致**【已复现】 |  |
| 228 | spec:258,260 | 「报名未成功」 | local/ui/controllers/plan-events.js:112 ↳ 报名未成功<br>local/ui/controllers/plan-events.js:113 ↳ 报名未成功 | **一致**【已复现】 |  |
| 229 | spec:259,260,311 | 「未提交」 | local/ui/state/plan.js:159 ↳ 未提交<br>local/ui/state/task-display.js:61 ↳ 未提交 | **一致**【已复现】 |  |
| 230 | spec:259 | 「本场没有提交」 | local/ui/controllers/plan-events.js:101 ↳ 本场没有提交<br>local/ui/controllers/plan-events.js:104 ↳ 本场没有提交 | **一致**【已复现】 |  |
| 231 | spec:259 | 「登录失效」 | local/ui/index.html:146 ↳ 登录失效<br>local/ui/index.html:148 ↳ 登录失效 | **一致**【已复现】 |  |
| 232 | spec:259 | 「请重新登录」 | 未检出（local/ui 全库无逐字/归一命中） | **规格禁止示例（未提交态不得写「请重新登录」）**【符合】 |  |
| 233 | spec:262 | 「打开学校活动页核对」 | local/ui/views/plan-panel.js:661 ↳ text: "工具不会自动重发，到学校活动页核对。", frame: "warn", led: null };<br>local/ui/views/plan-panel.js:1147-1148 ↳ * 不做「打开活动页」（后端没有按活动打开学校页面的接口，b-amendment-007） | **不一致**【NEEDS-HUMAN】 | 规格 §8 红线固定下一步为「打开学校活动页核对」；代码按 b-amendment-007 有意只写「到学校活动页核对」。规格与代码决策冲突。 |
| 234 | spec:269,308 | 「已提交 N 次」 | local/ui/views/plan-panel.js:1092 ↳ const head = "已提交 " + attempts + " 次（" + (limited ? "上限 " + cap + " 次" : "不限次数") + "）"; | **一致**【已复现】 | 对抗复核：原引行 1085 为注释；实际渲染在 1092（同条目 162 证据行，拼接归一后命中），内容逐字不变。 |
| 235 | spec:272,314 | 「停止报名计划？」 | local/ui/index.html:94 ↳ 停止报名计划？ | **一致**【已复现】 |  |
| 236 | spec:273,315,316 | 「继续计划」 | local/ui/index.html:94 ↳ 继续计划<br>local/ui/app.js:354 ↳ 继续计划 | **一致**【已复现】 |  |
| 237 | spec:274 | 「已提交的场次保留原状态，还没提交的场次已取消。」 | local/ui/views/plan-panel.js:644 ↳ 已提交的场次保留原状态，还没提交的场次已取消。 | **一致**【已复现】 |  |
| 238 | spec:274 | 「报名计划已停止」 | local/ui/views/plan-panel.js:644 ↳ 报名计划已停止 | **一致**【已复现】 |  |
| 239 | spec:275 | 「失败」 | local/ui/app.js:130 ↳ 失败<br>local/ui/app.js:555 ↳ 失败 | **一致**【已复现】 |  |
| 240 | spec:275,293 | 「已停止，需确认」 | local/ui/views/plan-panel.js:643 ↳ 已停止，需确认 | **一致**【已复现】 |  |
| 241 | spec:276 | 「演示模式」 | local/ui/controllers/plan.js:411 ↳ 演示模式<br>local/ui/views/clock-pop.js:120 ↳ 演示模式 | **一致**【已复现】 |  |
| 242 | spec:280,302,320 | 「完成，回到活动列表」 | local/ui/index.html:89 ↳ 完成，回到活动列表<br>local/ui/controllers/plan.js:357 ↳ 完成，回到活动列表 | **一致**【已复现】 |  |
| 243 | spec:281,302 | 「重新选择未成功的场次」 | local/ui/index.html:89 ↳ 重新选择未成功的场次<br>local/ui/controllers/plan.js:344 ↳ 重新选择未成功的场次 | **一致**【已复现】 |  |
| 244 | spec:282 | 「清空」 | local/ui/index.html:52 ↳ 清空<br>local/ui/index.html:102 ↳ 清空 | **一致**【已复现】 |  |
| 245 | spec:285,306,307 | 「刷新核对」 | local/ui/m/app.js:748 ↳ 刷新核对<br>local/ui/m/app.js:958 ↳ 刷新核对 | **一致**【已复现】 |  |
| 246 | spec:306 | 「已提交 N 次，没拿到确定回应；结束时向学校核对也没查到结果。去活动页看一眼，或稍后刷新核对。工具不会再自动重发。」 | local/ui/views/plan-panel.js:1130 ↳ 已提交 " + tried + " 次，没拿到确定回应；结束时向学校核对也没查到结果。去活动页看一眼，或稍后刷新核对。工具不会再自动重发。 | **一致（模板归一：占位/拼接写法归一后命中）**【已复现】 | 规格占位（N/M/\<…>/HH:MM 等）对应代码变量或字符串拼接。 |
| 247 | spec:307 | 「刷新核对：学校列表还没显示已报名，可能有延迟，去活动页看一眼；本工具不会再自动重发」 | local/ui/views/plan-panel.js:1127 ↳ 刷新核对：学校列表还没显示已报名，可能有延迟，去活动页看一眼；本工具不会再自动重发 | **一致**【已复现】 |  |
| 248 | spec:307 | 「刷新核对：学校显示已报名」 | local/ui/views/plan-panel.js:1118 ↳ 刷新核对：学校显示已报名 | **一致**【已复现】 |  |
| 249 | spec:308 | 「名额已满」 | local/ui/m/app.js:349 ↳ 名额已满<br>local/ui/state/task-display.js:63 ↳ 名额已满 | **一致**【已复现】 |  |
| 250 | spec:308 | 「学校说报名人数已满，这一场到此结束，不再提交。不是工具出错。」 | local/ui/views/plan-panel.js:1120 ↳ 学校说报名人数已满，这一场到此结束，不再提交。不是工具出错。 | **一致**【已复现】 |  |
| 251 | spec:309 | 「你取消了这一场」 | local/ui/views/plan-panel.js:1123 ↳ 你取消了这一场 | **一致**【已复现】 |  |
| 252 | spec:309 | 「计划已停止，这一场没有提交」 | local/ui/views/plan-panel.js:1123 ↳ 计划已停止，这一场没有提交 | **一致**【已复现】 |  |
| 253 | spec:310 | “\<原话>” | local/ui/views/plan-panel.js:1143 ↳ detail = (said ? "学校回“" + said + "”，" : "") + "结束时向学校核对过：已报名"; | **一致（拼接，随全句）**【已复现】 | 独立弯引号候选的自动匹配落点有误，改按整句证据。 |
| 254 | spec:310 | 「学校回“\<原话>”，结束时向学校核对过：已报名」 | local/ui/views/plan-panel.js:1141-1143 ↳ /* 学校回包原话（last_reason）有就引用，去掉句末标点；没有就只说核对结论 */ … detail = (said ? "学校回“" + said + "”，" : "") + "结束时向学校核对过：已报名"; | **一致（拼接）**【已复现】 |  |
| 255 | spec:310 | 「已报名」 | local/ui/index.html:37 ↳ 已报名<br>local/ui/index.html:460 ↳ 已报名 | **一致**【已复现】 |  |
| 256 | spec:310 | 「结束时向学校核对过：已报名」 | local/ui/views/plan-panel.js:1143 ↳ 结束时向学校核对过：已报名 | **一致**【已复现】 |  |
| 257 | spec:311 | 「登录状态无法确认，本场没有提交 · 检查网络后刷新重试」 | local/ui/views/plan-panel.js:1132 ↳ 登录状态无法确认，本场没有提交 · 检查网络后刷新重试 | **一致**【已复现】 |  |
| 258 | spec:312 | 「报名已截止」 | local/ui/state/filters.js:160 ↳ 报名已截止<br>local/ui/views/plan-panel.js:1052 ↳ 报名已截止 | **一致**【已复现】 |  |
| 259 | spec:312 | 「提交了 N 次（\<结束结论>）」 | local/ui/views/plan-panel.js:1134-1138 ↳ if (task.attempts) bits.push("提交了 " + task.attempts + " 次"); … if (bits.length) detail = (detail ? detail + "（" : "") + bits.join("，") + (detail ? "）" : ""); | **不一致**【已复现】 | 独立呈现为「提交了 N 次，\<结论>」（逗号连接、无括号）；仅当已有前置说明时才包括号。 |
| 260 | spec:312 | 「达到最大提交次数」 | local/ui/views/plan-panel.js:1050 ↳ 达到最大提交次数 | **一致**【已复现】 |  |
| 261 | spec:314 | 「工具会停止后续尝试。已经发出的提交仍可能成功，停止不会取消已成功的报名。」 | local/ui/index.html:94 ↳ 工具会停止后续尝试。已经发出的提交仍可能成功，停止不会取消已成功的报名。 | **一致**【已复现】 |  |
| 262 | spec:324 | 「北京时间 + HH:MM:SS + 状态图形」 | local/ui/state/clock.js:307-308 ↳ /* 顶栏唯一时间入口：正常只显示北京时间 + 时分秒 + 小状态图形。 */ | **规格元描述（描述性）**【已复现】 | 同 spec:21 条目。 |
| 263 | spec:325,334 | 「演示时间」 | local/ui/state/clock.js:35 ↳ 演示时间<br>local/ui/views/clock-pop.js:81 ↳ 演示时间 | **一致**【已复现】 |  |
| 264 | spec:326 | 「与电脑日期差 N 天」 | 未检出（local/ui 全库无逐字/归一命中） | **规格禁止示例（主界面不出现）**【符合】 |  |
| 265 | spec:326 | 「点此重新校时」 | 未检出（local/ui 全库无逐字/归一命中） | **规格禁止示例（主界面不出现）**【符合】 |  |
| 266 | spec:330 | 「已校准」 | local/ui/state/clock.js:30 ↳ 已校准<br>local/ui/state/clock.js:220 ↳ 已校准 | **一致**【已复现】 |  |
| 267 | spec:330 | 「报名时间和倒计时均以北京时间为准。」 | local/ui/state/clock.js:30 ↳ 报名时间和倒计时均以北京时间为准。 | **一致**【已复现】 |  |
| 268 | spec:331 | 「正在校准…」 | local/ui/state/clock.js:31 ↳ 正在校准…<br>local/ui/state/clock.js:115 ↳ 正在校准… | **一致**【已复现】 |  |
| 269 | spec:331 | 「正在获取网络时间。报名计划需在校准完成后启动。」 | local/ui/state/clock.js:31 ↳ 正在获取网络时间。报名计划需在校准完成后启动。 | **一致**【已复现】 |  |
| 270 | spec:332 | 「使用上次校准结果」 | local/ui/state/clock.js:11 ↳ 使用上次校准结果<br>local/ui/state/clock.js:33 ↳ 使用上次校准结果 | **一致**【已复现】 |  |
| 271 | spec:332 | 「时间仍可用，工具会自动重试校准。」 | local/ui/state/clock.js:33 ↳ 时间仍可用，工具会自动重试校准。 | **一致**【已复现】 |  |
| 272 | spec:333 | 「报名计划暂不可启动。检查网络后重试。」 | local/ui/state/clock.js:34 ↳ 报名计划暂不可启动。检查网络后重试。 | **一致**【已复现】 |  |
| 273 | spec:333 | 「时间校准失败」 | local/ui/state/clock.js:34 ↳ 时间校准失败 | **一致**【已复现】 |  |
| 274 | spec:334 | 「使用示例活动和时间，不会提交报名。」 | local/ui/state/clock.js:35 ↳ 使用示例活动和时间，不会提交报名。 | **一致**【已复现】 |  |
| 275 | spec:338 | 「重新校准时间」 | local/ui/views/clock-pop.js:128 ↳ 重新校准时间 | **一致**【已复现】 |  |
| 276 | spec:338 | 「重试校准」 | local/ui/state/clock.js:32 ↳ 重试校准<br>local/ui/state/clock.js:33 ↳ 重试校准 | **一致**【已复现】 |  |
| 277 | spec:339 | 「不会修改电脑时间」 | local/ui/views/clock-pop.js:124 ↳ 不会修改电脑时间 | **一致**【已复现】 |  |
| 278 | spec:340 | 「登录剩余时间仅供参考，以学校校验为准。」 | local/ui/index.html:350 ↳ \<!-- 登录详情卡：只写登录有效与否和上次校验时刻，不显示剩余时间（学校不公布，工具不估算） --><br>local/ui/views/login.js:74 ↳ note = "学校确认登录有效；有效多久学校不公布，工具不估算"; | **代码没有（有意不实现）**【NEEDS-HUMAN】 | 规格 §10 浮层内容含「登录预计剩余时间」与固定说明本句；代码按 §3 红线「登录不估算剩余时间」与决策 014 有意不实现，规格 §10 未同步。对抗复核证实：引用行现盘为 73，内容逐字不变。 |
| 279 | spec:342 | 「最近校准」 | local/ui/views/clock-pop.js:109 ↳ 最近校准<br>local/ui/state/clock.js:166 ↳ 最近校准 | **一致**【已复现】 |  |
| 280 | spec:343 | 「10 分钟前」 | local/ui/state/clock.js:304 ↳ if (ago < 3600) return Math.floor(ago / 60) + " 分钟前"; | **一致**【已复现】 | 对抗复核：原引行 299 为注释；实际渲染在 304（分钟前 拼接归一后命中），内容逐字不变。 |
| 281 | spec:343 | 「刚刚」 | local/ui/state/clock.js:303 ↳ 刚刚<br>local/ui/views/list.js:396 ↳ 刚刚 | **一致**【已复现】 |  |
| 282 | spec:348 | 「待确认」 | local/ui/controllers/tick.js:80 ↳ 待确认<br>local/ui/m/app.js:948 ↳ 待确认 | **一致**【已复现】 |  |
| 283 | spec:356 | 「本机日期为 AI 工具刻意设置」 | 未检出（local/ui 全库无逐字/归一命中） | **规格禁止示例（不写给公众）**【符合】 |  |
| 284 | spec:363 | 「三步完成一次报名」 | local/ui/index.html:190 ↳ 三步完成一次报名<br>local/ui/state/store.js:6 ↳ 三步完成一次报名 | **一致**【已复现】 |  |
| 285 | spec:363 | 「使用帮助」 | local/ui/index.html:143 ↳ 使用帮助<br>local/ui/index.html:151 ↳ 使用帮助 | **一致**【已复现】 |  |
| 286 | spec:364 | “已登录” | local/ui/state/store.js:10 ↳ 已登录<br>local/ui/views/login.js:20 ↳ 已登录 | **一致**【已复现】 |  |
| 287 | spec:364 | 「顶部显示“已登录”就可以继续。只有提示失效时才需要重新登录。」 | local/ui/state/store.js:10 ↳ 顶部显示“已登录”就可以继续。只有提示失效时才需要重新登录。 | **一致**【已复现】 |  |
| 288 | spec:365 | 「在时刻表勾选活动，核对右边的计划，再点「开始报名计划」。勾选不会自动开始。」 | local/ui/state/store.js:11 ↳ 在时刻表勾选活动，核对右边的计划，再点「开始报名计划」。勾选不会自动开始。 | **一致**【已复现】 |  |
| 289 | spec:366 | “待核对” | local/ui/styles.css:917 ↳ 待核对<br>local/ui/controllers/plan-events.js:93 ↳ 待核对 | **一致**【已复现】 |  |
| 290 | spec:366 | 「每场结果单独显示。看到“待核对”时，到学校活动页确认。」 | local/ui/state/store.js:12 ↳ 每场结果单独显示。看到“待核对”时，到学校活动页确认。 | **一致**【已复现】 |  |
| 291 | spec:368 | 「设置 → 条款与隐私」 | local/ui/index.html:145 ↳ 设置 → 条款与隐私<br>local/ui/index.html:151 ↳ 设置 → 条款与隐私 | **一致**【已复现】 |  |
| 292 | spec:370 | 「这里是登录状态和「登录 / 刷新」入口。…只有提示失效时才需要重新登录。」 | local/ui/state/store.js:26-28 ↳ /* … 3：新工作台（决策 009 修订）由六步改为五步，启动时机改为登录成功且列表加载后。 */ const TOUR_VERSION = 3;<br>local/ui/state/store.js:10 ↳ { no: 1, title: "确认登录", text: "顶部显示“已登录”就可以继续。只有提示失效时才需要重新登录。" }, | **不一致（引导已改五步）**【NEEDS-HUMAN】 | 规格 §11 六步引导整块（本条+下 5 条）已被五步引导取代（store.js:30-44，标题/文案全部不同）；规格未回改。对抗复核：引用行现盘为 23-24（TOUR_VERSION=3 在 24 行），内容逐字不变。 |
| 293 | spec:371 | 「「预报名」等待学校开放，「立即报名」在计划启动后尝试提交。选择活动不会自动开始报名。」 | local/ui/state/store.js:34-35 ↳ { target: "list", title: "这是活动时刻表", text: "活动按开放时间排好。「预报名」等开放后自动提交，「立即报名」点开始后马上提交。上面可以搜索和筛选。" }, | **不一致（引导已改五步）**【NEEDS-HUMAN】 | 最接近代码如引。对抗复核：引用行现盘为 31-32（−3），内容逐字不变。 |
| 294 | spec:372 | 「按名称、地点或时间查找活动，也可筛选签到和签退要求。未说明的要求以学校活动页为准。」 | local/ui/state/store.js:34-35 ↳ 同上（引导中无签到/签退筛选句；筛选控件本身在 index.html:40 存在） | **不一致（引导已改五步）**【NEEDS-HUMAN】 | 对抗复核：引用行现盘为 31-32（−3，同条目 293），内容逐字不变。 |
| 295 | spec:373 | 「勾选要报名的活动。举办时间重叠的活动不能同时加入计划。」 | local/ui/state/store.js:36-37 ↳ { target: "row", interactive: true, title: "勾选想报的活动", text: "点这一行试试。勾选只是加入计划，不会开始报名；举办时间重叠的活动不能同时选。" }, | **不一致（引导已改五步）**【NEEDS-HUMAN】 | 对抗复核：引用行现盘为 33-34（−3），内容逐字不变。 |
| 296 | spec:374 | 「设置尝试时长和最多提交次数，再选择「开始报名计划」。达到…任一条件后，工具停止尝试。」 | local/ui/state/store.js:38-39 ↳ { target: "select", title: "核对计划，再点开始", text: "选好的活动都列在这里，可以逐场移除，也能修改尝试时长。开始不了时，按钮下面会写还差什么。" }, | **不一致（引导已改五步）**【NEEDS-HUMAN】 | 对抗复核：引用行现盘为 35-36（−3），内容逐字不变。 |
| 297 | spec:375 | 「可最小化窗口，但不要关闭工具或让电脑睡眠。…显示「待核对」时，到学校活动页确认。」 | local/ui/state/store.js:40-41 ↳ { target: "run", title: "开始以后看这里", text: "这里显示倒计时，下面是每场进度。可以最小化窗口，但不要关闭工具或让电脑睡眠。看到「待核对」时，到学校活动页确认。" }, | **不一致（引导已改五步）**【NEEDS-HUMAN】 | 前半句逐字存在；规格省略处「…显示「待核对」」代码作「看到「待核对」」。对抗复核：引用行现盘为 37-38（−3），内容逐字不变。 |
| 298 | spec:376 | 「上一步」 | local/ui/index.html:343 ↳ 上一步<br>local/ui/app.js:420 ↳ 上一步 | **一致**【已复现】 |  |
| 299 | spec:376 | 「下一步」 | local/ui/index.html:47 ↳ 下一步<br>local/ui/index.html:344 ↳ 下一步 | **一致**【已复现】 |  |
| 300 | spec:376 | 「跳过引导」 | local/ui/index.html:341 ↳ 跳过引导 | **一致**【已复现】 |  |
| 301 | spec:376 | 「重看引导」 | local/ui/index.html:28 ↳ 重看引导<br>local/ui/index.html:203 ↳ 重看引导 | **一致**【已复现】 |  |
| 302 | spec:382 | 「暂时无法检查更新」 | local/ui/views/update.js:34 ↳ 暂时无法检查更新 | **一致**【已复现】 |  |
| 303 | spec:382 | 「检查更新」 | local/ui/index.html:159 ↳ 检查更新<br>local/ui/index.html:311 ↳ 检查更新 | **一致**【已复现】 |  |
| 304 | spec:383 | 「前往下载页」 | local/ui/index.html:159 ↳ 前往下载页<br>local/ui/index.html:312 ↳ 前往下载页 | **一致**【已复现】 |  |
| 305 | spec:384,447 | 「打开数据目录」 | local/ui/index.html:102 ↳ 打开数据目录<br>local/ui/index.html:158 ↳ 打开数据目录 | **一致**【已复现】 |  |
| 306 | spec:384,447 | 「本机数据」 | local/ui/app.js:463 ↳ 本机数据<br>local/ui/index.html:158 ↳ 本机数据 | **一致**【已复现】 |  |
| 307 | spec:384,447 | 「登录信息、设置、运行记录和下载的组件，都只保存在这台电脑。」 | local/ui/index.html:315 ↳ 登录信息、设置、运行记录和下载的组件，都只保存在这台电脑。 | **一致**【已复现】 |  |
| 308 | spec:386 | 「当前为预览版本，最新正式版 X」 | local/ui/views/update.js:24 ↳ preview: "当前是预览版本，最新正式版是 " + (result.latest_version \|\| "") + "，不建议换回旧版本。", | **不一致**【已复现】 | 规格「当前为预览版本，最新正式版 X」；代码「当前是预览版本，最新正式版是 X，不建议换回旧版本。」 |
| 309 | spec:386 | 「请降级」 | 未检出（local/ui 全库无逐字/归一命中） | **规格禁止示例（不写「请降级」）**【符合】 |  |
| 310 | spec:394,417 | 「下载并安装」 | local/ui/index.html:216 ↳ 下载并安装<br>local/ui/index.html:265 ↳ 下载并安装 | **一致**【已复现】 |  |
| 311 | spec:394,417 | 「取消下载」 | local/ui/index.html:216 ↳ 取消下载<br>local/ui/index.html:263 ↳ 取消下载 | **一致**【已复现】 |  |
| 312 | spec:394 | 「启用手机控制」 | local/ui/index.html:216 ↳ 启用手机控制<br>local/ui/views/phone.js:468 ↳ 启用手机控制 | **一致**【已复现】 |  |
| 313 | spec:394 | 「安装/更换组件包」 | local/ui/views/phone.js:469 ↳ 安装/更换组件包 | **一致**【已复现】 |  |
| 314 | spec:394 | 「导入已下载的组件包」 | local/ui/index.html:224 ↳ 导入已下载的组件包<br>local/ui/index.html:271 ↳ 导入已下载的组件包 | **一致**【已复现】 |  |
| 315 | spec:394 | 「手机访问」 | local/ui/index.html:22 ↳ 手机访问<br>local/ui/index.html:215 ↳ 手机访问 | **一致**【已复现】 |  |
| 316 | spec:394,417 | 「校验中…」 | local/ui/index.html:263 ↳ 校验中…<br>local/ui/views/phone.js:463 ↳ 校验中… | **一致**【已复现】 |  |
| 317 | spec:394,419 | 「重新下载」 | local/ui/controllers/refresh.js:296 ↳ 重新下载<br>local/ui/controllers/refresh.js:298 ↳ 重新下载 | **一致**【已复现】 |  |
| 318 | spec:394,419 | 「重新导入组件包」 | local/ui/index.html:265 ↳ 重新导入组件包<br>local/ui/views/phone.js:467 ↳ 重新导入组件包 | **一致**【已复现】 |  |
| 319 | spec:395,419 | 「加载失败」 | local/ui/views/phone.js:483 ↳ 加载失败<br>local/ui/views/settings.js:192 ↳ 加载失败 | **一致**【已复现】 |  |
| 320 | spec:395 | 「已停用」 | local/ui/controllers/terms.js:114 ↳ 已停用<br>local/ui/views/phone.js:484 ↳ 已停用 | **一致**【已复现】 |  |
| 321 | spec:395 | 「手机已连接」 | local/ui/index.html:243 ↳ 手机已连接<br>local/ui/controllers/window.js:51 ↳ 手机已连接 | **一致**【已复现】 |  |
| 322 | spec:395 | 「未开启」 | local/ui/index.html:213 ↳ 未开启<br>local/ui/index.html:216 ↳ 未开启 | **一致**【已复现】 |  |
| 323 | spec:395 | 「等手机连接」 | local/ui/views/phone.js:482 ↳ 等手机连接<br>local/ui/views/status-cards.js:132 ↳ 等手机连接 | **一致**【已复现】 |  |
| 324 | spec:397 | 「从手机查看活动、开始和停止计划。手机只是遥控器，真正报名的还是这台电脑，所以电脑要开着、不能睡眠。」 | local/ui/index.html:217 ↳ 从手机查看活动、开始和停止计划。手机只是遥控器，真正报名的还是这台电脑，所以电脑要开着、不能睡眠。<br>local/ui/views/phone.js:499 ↳ 从手机查看活动、开始和停止计划。手机只是遥控器，真正报名的还是这台电脑，所以电脑要开着、不能睡眠。 | **一致**【已复现】 |  |
| 325 | spec:398 | 「选一条通道再开启。没开启时不监听端口，手机连不上电脑。」 | local/ui/views/phone.js:497 ↳ 选一条通道再开启。没开启时不监听端口，手机连不上电脑。 | **一致**【已复现】 |  |
| 326 | spec:399 | 「正在开启，先不要切换通道。」 | local/ui/views/phone.js:497 ↳ 正在开启，先不要切换通道。 | **一致**【已复现】 |  |
| 327 | spec:400 | 「第一次连接要扫码和配对。扫码只负责打开页面，配对靠这 6 位数。」 | local/ui/views/phone.js:495 ↳ 第一次连接要扫码和配对。扫码只负责打开页面，配对靠这 6 位数。 | **一致**【已复现】 |  |
| 328 | spec:401 | 「手机可以查看活动、开始和停止计划。程序退出后手机就打不开了。」 | local/ui/views/phone.js:494 ↳ 手机可以查看活动、开始和停止计划。程序退出后手机就打不开了。 | **一致**【已复现】 |  |
| 329 | spec:402 | 「可以关掉设置继续用，下载和报名计划互不影响。」 | local/ui/views/phone.js:498 ↳ 可以关掉设置继续用，下载和报名计划互不影响。 | **一致**【已复现】 |  |
| 330 | spec:403,425 | 「一直下载不了的话，可以到发布页手动下载组件包，再导入已下载的组件包。」 | local/ui/index.html:224 ↳ \<p class="ph-note" id="phone-import-line" hidden>一直下载不了的话，可以到发布页手动下载组件包，再\<button class="ph-link" id="btn-phone-import" type="button">导入已下载的组件包\</button>。\</p><br>local/ui/index.html:271 ↳ 同款（ocr-import-line） | **一致（HTML 内联按钮）**【已复现】 | 文本节点连按钮文字即规格整句。 |
| 331 | spec:403,425 | 「可选组件，大小以发布页为准（现在读不到）。下载后自动校验并启用，不会自动升级。」 | local/ui/index.html:222 ↳ 可选组件，大小以发布页为准（现在读不到）。下载后自动校验并启用，不会自动升级。<br>local/ui/index.html:269 ↳ 可选组件，大小以发布页为准（现在读不到）。下载后自动校验并启用，不会自动升级。 | **一致**【已复现】 |  |
| 332 | spec:404,426 | 「下载完成，正在校验组件…」 | local/ui/views/phone.js:536 ↳ 下载完成，正在校验组件…<br>local/ui/views/settings.js:250 ↳ 下载完成，正在校验组件… | **一致**【已复现】 |  |
| 333 | spec:404 | 「下载没有完成：\<原因>，可以重试。」 | local/ui/views/phone.js:102 ↳ 下载没有完成：" + reason + "，可以重试。<br>local/ui/views/phone.js:92 ↳ 下载没有完成：原因，可以重试。 | **一致（模板归一：占位/拼接写法归一后命中）**【已复现】 | 规格占位（N/M/\<…>/HH:MM 等）对应代码变量或字符串拼接。 |
| 334 | spec:404 | 「正在下载手机控制组件」 | local/ui/index.html:227 ↳ 正在下载手机控制组件<br>local/ui/views/phone.js:536 ↳ 正在下载手机控制组件 | **一致**【已复现】 |  |
| 335 | spec:404 | 「网络中断」 | local/ui/views/phone.js:96 ↳ 网络中断 | **一致**【已复现】 |  |
| 336 | spec:404 | 「连不上发布页」 | local/ui/views/phone.js:95 ↳ 连不上发布页 | **一致**【已复现】 |  |
| 337 | spec:405,427 | 「下载已取消，没有装任何东西。」 | local/ui/views/phone.js:514 ↳ 下载已取消，没有装任何东西。<br>local/ui/views/settings.js:264 ↳ 下载已取消，没有装任何东西。 | **一致**【已复现】 |  |
| 338 | spec:406 | 「手机控制组件已安装，选一条通道就能开启。」 | local/ui/views/phone.js:442 ↳ 手机控制组件已安装，选一条通道就能开启。 | **一致**【已复现】 |  |
| 339 | spec:406 | 「手机控制组件已导入并启用，选一条通道就能开启。」 | local/ui/views/phone.js:778 ↳ 手机控制组件已导入并启用，选一条通道就能开启。 | **一致**【已复现】 |  |
| 340 | spec:407 | 「Cloudflare，临时地址」 | local/ui/index.html:237 ↳ Cloudflare，临时地址 | **一致**【已复现】 |  |
| 341 | spec:407 | 「Tailscale，长期地址」 | local/ui/index.html:236 ↳ Tailscale，长期地址 | **一致**【已复现】 |  |
| 342 | spec:407 | 「远程通道」 | local/ui/index.html:235 ↳ 远程通道 | **一致**【已复现】 |  |
| 343 | spec:408 | 「关闭中…」 | local/ui/views/phone.js:664 ↳ 关闭中… | **一致**【已复现】 |  |
| 344 | spec:408 | 「关闭手机访问」 | local/ui/index.html:256 ↳ 关闭手机访问<br>local/ui/views/phone.js:664 ↳ 关闭手机访问 | **一致**【已复现】 |  |
| 345 | spec:408 | 「再配对一台手机」 | local/ui/index.html:256 ↳ 再配对一台手机<br>local/ui/views/phone.js:162 ↳ 再配对一台手机 | **一致**【已复现】 |  |
| 346 | spec:408 | 「启动中…」 | local/ui/views/phone.js:575 ↳ 启动中… | **一致**【已复现】 |  |
| 347 | spec:408 | 「开启手机访问」 | local/ui/index.html:239 ↳ 开启手机访问<br>local/ui/views/phone.js:575 ↳ 开启手机访问 | **一致**【已复现】 |  |
| 348 | spec:408 | 「重新检测」 | local/ui/index.html:239 ↳ 重新检测<br>local/ui/views/phone.js:49 ↳ 重新检测 | **一致**【已复现】 |  |
| 349 | spec:409 | 「先不关闭」 | local/ui/index.html:255 ↳ 先不关闭 | **一致**【已复现】 |  |
| 350 | spec:409 | 「关闭后手机立刻失去权限，下次连接要重新扫码配对。」 | local/ui/index.html:255 ↳ 关闭后手机立刻失去权限，下次连接要重新扫码配对。 | **一致**【已复现】 |  |
| 351 | spec:409 | 「确认关闭」 | local/ui/index.html:255 ↳ 确认关闭 | **一致**【已复现】 |  |
| 352 | spec:410 | 「手机已连接。配对码已换成新的，旧码不能再用。」 | local/ui/index.html:243 ↳ 手机已连接。配对码已换成新的，旧码不能再用。 | **一致**【已复现】 |  |
| 353 | spec:411 | 「\<m:ss> 后失效，一码只能用一次」 | local/ui/views/phone.js:676 ↳ ? "\<b>" + pairLeftText(PhonePanel.codeLeft) + "\</b> 后失效，一码只能用一次"<br>local/ui/views/phone.js:106 ↳ m:ss 后失效，一码只能用一次 | **一致（模板归一：占位/拼接写法归一后命中）**【已复现】 | 对抗复核：证据串 airLeftText 系笔误，代码原文为 pairLeftText（现盘与基线 a85209e 同），已按原码逐字修正。规格占位（N/M/\<…>/HH:MM 等）对应代码变量或字符串拼接。 |
| 354 | spec:411 | 「手机扫码打开页面，再输入这 6 位配对码」 | local/ui/index.html:247 ↳ 手机扫码打开页面，再输入这 6 位配对码 | **一致**【已复现】 |  |
| 355 | spec:411 | 「配对码已过期，正在换新」 | local/ui/views/phone.js:677 ↳ 配对码已过期，正在换新 | **一致**【已复现】 |  |
| 356 | spec:412 | 「地址固定，建议在手机上存成书签，下次直接打开。」 | local/ui/index.html:253 ↳ 地址固定，建议在手机上存成书签，下次直接打开。<br>local/ui/views/phone.js:654 ↳ 地址固定，建议在手机上存成书签，下次直接打开。 | **一致**【已复现】 |  |
| 357 | spec:412 | 「复制」 | local/ui/app.js:458 ↳ 复制<br>local/ui/index.html:102 ↳ 复制 | **一致**【已复现】 |  |
| 358 | spec:412 | 「复制没有成功，请手动选中地址。」 | local/ui/views/phone.js:964 ↳ 复制没有成功，请手动选中地址。 | **一致**【已复现】 |  |
| 359 | spec:412 | 「已复制」 | local/ui/views/log.js:15 ↳ 已复制<br>local/ui/views/phone.js:645 ↳ 已复制 | **一致**【已复现】 |  |
| 360 | spec:412 | 「这是临时地址：关闭访问或重启程序后就会变，手机要重新扫码配对。」 | local/ui/views/phone.js:653 ↳ 这是临时地址：关闭访问或重启程序后就会变，手机要重新扫码配对。 | **一致**【已复现】 |  |
| 361 | spec:413 | 「会装到」 | local/ui/index.html:223 ↳ 会装到<br>local/ui/index.html:270 ↳ 会装到 | **一致**【已复现】 |  |
| 362 | spec:413 | 「打开所在文件夹」 | local/ui/index.html:259 ↳ 打开所在文件夹<br>local/ui/index.html:278 ↳ 打开所在文件夹 | **一致**【已复现】 |  |
| 363 | spec:413 | 「装在」 | local/ui/index.html:259 ↳ 装在<br>local/ui/index.html:278 ↳ 装在 | **一致**【已复现】 |  |
| 364 | spec:414 | 「Cloudflare 隧道断了，旧地址和二维码已失效。重新开启后要重新扫码配对。」 | local/ui/views/phone.js:589 ↳ Cloudflare 隧道断了，旧地址和二维码已失效。重新开启后要重新扫码配对。 | **一致**【已复现】 |  |
| 365 | spec:414 | 「已重新检测：Tailscale 已连接。」 | local/ui/views/phone.js:1047 ↳ 已重新检测：Tailscale 已连接。 | **一致**【已复现】 |  |
| 366 | spec:414 | 「手机访问已关闭，手机需要重新配对才能再进。」 | local/ui/views/phone.js:864 ↳ 手机访问已关闭，手机需要重新配对才能再进。 | **一致**【已复现】 |  |
| 367 | spec:414 | 「正在建立临时隧道，最多等 20 秒。」 | local/ui/views/phone.js:583 ↳ 正在建立临时隧道，最多等 20 秒。 | **一致**【已复现】 |  |
| 368 | spec:414 | 「还差一步：登录 Tailscale 后点“重新检测”，或者改用 Cloudflare。」 | local/ui/views/phone.js:581 ↳ 还差一步：登录 Tailscale 后点“重新检测”，或者改用 Cloudflare。 | **一致**【已复现】 |  |
| 369 | spec:414 | 「还差一步：装好 Tailscale 后点“重新检测”，或者改用 Cloudflare。」 | local/ui/views/phone.js:582 ↳ 还差一步：装好 Tailscale 后点“重新检测”，或者改用 Cloudflare。 | **一致**【已复现】 |  |
| 370 | spec:414,414 | “重新检测” | local/ui/index.html:239 ↳ 重新检测<br>local/ui/views/phone.js:49 ↳ 重新检测 | **一致**【已复现】 |  |
| 371 | spec:415 | 「出门前建议保存账号密码：登录失效时只需在手机上输验证码；再装上验证码识别，就完全不用管。」 | local/ui/index.html:244 ↳ 出门前建议保存账号密码：登录失效时只需在手机上输验证码；再装上验证码识别，就完全不用管。 | **一致**【已复现】 |  |
| 372 | spec:417 | 「启用」 | local/ui/index.html:216 ↳ 启用<br>local/ui/index.html:222 ↳ 启用 | **一致**【已复现】 |  |
| 373 | spec:419 | 「已启用」 | local/ui/index.html:263 ↳ 已启用<br>local/ui/index.html:265 ↳ 已启用 | **一致**【已复现】 |  |
| 374 | spec:419 | 「未启用」 | local/ui/index.html:265 ↳ 未启用<br>local/ui/index.html:288 ↳ 未启用 | **一致**【已复现】 |  |
| 375 | spec:419 | 「验证码识别」 | local/ui/index.html:244 ↳ 验证码识别<br>local/ui/index.html:264 ↳ 验证码识别 | **一致**【已复现】 |  |
| 376 | spec:421 | 「版本 \<版本号>。电脑会自己认验证码，连续认错 3 次再转给手机手动输入。」 | local/ui/views/settings.js:228-229 ↳ ? (version ? "版本 " + version + "。" : "") + "电脑会自己认验证码，连续认错 3 次再转给手机手动输入。" | **一致（拼接）**【已复现】 | 读不到版本号时不写「版本…」句，与规格一致。 |
| 377 | spec:421 | 「版本…」 | local/ui/views/terms.js:233-234 ↳ /* 只读态状态行上屏：副行 #dlg-terms-sub 的「程序要求版本…同意后才能…」…（条款弹窗注释，语境不对题）<br>local/ui/views/settings.js:228 ↳ ? (version ? "版本 " + version + "。" : "") + "电脑会自己认验证码，连续认错 3 次再转给手机手动输入。" | **规格禁止示例（读不到版本号时不写「版本…」这一句）**【符合】 | 对抗复核改判：spec:421 括注为否定式提及；settings.js:228 读不到版本号时该句整句省略=符合；原引 views/terms.js:234 为注释且语境不对题，无用户可见命中。 |
| 378 | spec:422 | 「已装好（版本 \<版本号>），还没启用。启用后，登录失效时电脑会自己认验证码；配合“登录恢复”里的账号密码，就能无人值守自动登录。」 | local/ui/views/settings.js:230-231 ↳ ? "已装好" + (version ? "（版本 " + version + "）" : "") + "，还没启用。启用后，登录失效时电脑会自己认验证码；配合“登录恢复”里的账号密码，就能无人值守自动登录。" | **一致（拼接）**【已复现】 |  |
| 379 | spec:422,423 | “登录恢复” | local/ui/index.html:266 ↳ 登录恢复<br>local/ui/index.html:284 ↳ 登录恢复 | **一致**【已复现】 |  |
| 380 | spec:423 | 「登录失效时，电脑能自己认验证码，配合“登录恢复”里的账号密码就能全自动登录。没装或认不出来时，由你在手机上手动输入。」 | local/ui/index.html:266 ↳ 登录失效时，电脑能自己认验证码，配合“登录恢复”里的账号密码就能全自动登录。没装或认不出来时，由你在手机上手动输入。<br>local/ui/views/settings.js:232 ↳ 登录失效时，电脑能自己认验证码，配合“登录恢复”里的账号密码就能全自动登录。没装或认不出来时，由你在手机上手动输入。 | **一致**【已复现】 |  |
| 381 | spec:424 | 「这一项关系到自动登录，所以装好了也不会自己打开。」 | local/ui/index.html:273 ↳ 这一项关系到自动登录，所以装好了也不会自己打开。 | **一致**【已复现】 |  |
| 382 | spec:426 | 「正在下载验证码识别组件」 | local/ui/index.html:275 ↳ 正在下载验证码识别组件<br>local/ui/views/settings.js:250 ↳ 正在下载验证码识别组件 | **一致**【已复现】 |  |
| 383 | spec:427 | 「取消没有生效，请稍后重试。」 | local/ui/views/phone.js:1009 ↳ 取消没有生效，请稍后重试。<br>local/ui/views/phone.js:1016 ↳ 取消没有生效，请稍后重试。 | **一致**【已复现】 |  |
| 384 | spec:427 | 「打不开所在文件夹。」 | local/ui/views/phone.js:925 ↳ 打不开所在文件夹。<br>local/ui/views/settings.js:310 ↳ 打不开所在文件夹。 | **一致**【已复现】 |  |
| 385 | spec:427 | 「没有启用，请重试。」 | local/ui/views/phone.js:819 ↳ 没有启用，请重试。<br>local/ui/views/phone.js:824 ↳ 没有启用，请重试。 | **一致**【已复现】 |  |
| 386 | spec:427 | 「组件下载没有开始。」 | local/ui/views/phone.js:993 ↳ 组件下载没有开始。<br>local/ui/views/phone.js:996 ↳ 组件下载没有开始。 | **一致**【已复现】 |  |
| 387 | spec:427 | 「验证码识别已启用。」 | local/ui/views/settings.js:295 ↳ 验证码识别已启用。 | **一致**【已复现】 |  |
| 388 | spec:427 | 「验证码识别组件已安装并启用。」 | local/ui/views/settings.js:185 ↳ 验证码识别组件已安装并启用。 | **一致**【已复现】 |  |
| 389 | spec:431 | 「填写账号密码」 | local/ui/index.html:285 ↳ 填写账号密码<br>local/ui/views/phone.js:324 ↳ 填写账号密码 | **一致**【已复现】 |  |
| 390 | spec:431 | 「更换」 | local/ui/index.html:301 ↳ 更换<br>local/ui/views/phone.js:324 ↳ 更换 | **一致**【已复现】 |  |
| 391 | spec:431 | 「登录恢复」 | local/ui/index.html:266 ↳ 登录恢复<br>local/ui/index.html:284 ↳ 登录恢复 | **一致**【已复现】 |  |
| 392 | spec:432 | 「登录失效时用账号密码自动登录。账号密码只用 Windows 当前用户加密保存在本机，手机页看不到。」 | local/ui/index.html:286 ↳ 登录失效时用账号密码自动登录。账号密码只用 Windows 当前用户加密保存在本机，手机页看不到。 | **一致**【已复现】 |  |
| 393 | spec:433,441 | 「只用这一次」 | local/ui/views/phone.js:412 ↳ 只用这一次<br>local/ui/views/relogin.js:51 ↳ 只用这一次 | **一致**【已复现】 |  |
| 394 | spec:433 | 「已保存账号 \<掩码账号>。」 | local/ui/views/phone.js:329 ↳ 已保存账号 " + maskAccount(cred.username) + "。 | **一致（模板归一：占位/拼接写法归一后命中）**【已复现】 | 规格占位（N/M/\<…>/HH:MM 等）对应代码变量或字符串拼接。 |
| 395 | spec:433 | 「这次运行可以用账号 \<提示> 重新登录，关闭工具后自动清除。」 | local/ui/views/phone.js:331 ↳ 这次运行可以用账号 " + String(cred.staged_hint) + " 重新登录，关闭工具后自动清除。 | **一致（模板归一：占位/拼接写法归一后命中）**【已复现】 | 规格占位（N/M/\<…>/HH:MM 等）对应代码变量或字符串拼接。 |
| 396 | spec:435 | 「失效后自动登录：未启用，还没有账号密码。登录失效后要手动重新登录；报名计划开放前 100 秒内失效的场次会直接结束。」 | local/ui/index.html:288 ↳ 失效后自动登录：未启用，还没有账号密码。登录失效后要手动重新登录；报名计划开放前 100 秒内失效的场次会直接结束。<br>local/ui/views/phone.js:341 ↳ 失效后自动登录：未启用，还没有账号密码。登录失效后要手动重新登录；报名计划开放前 100 秒内失效的场次会直接结束。 | **一致**【已复现】 |  |
| 397 | spec:436 | 「失效后自动登录：已启用。登录失效时电脑自己重新登录，报名计划等开放或提交时也一样，不用你动手。」 | local/ui/views/phone.js:343 ↳ 失效后自动登录：已启用。登录失效时电脑自己重新登录，报名计划等开放或提交时也一样，不用你动手。 | **一致**【已复现】 |  |
| 398 | spec:437 | “启用” | local/ui/index.html:216 ↳ 启用<br>local/ui/index.html:222 ↳ 启用 | **一致**【已复现】 |  |
| 399 | spec:437 | 「失效后自动登录：验证码识别本机已装，还没启用（在上面“高级功能”里点“启用”）。现在登录失效时要你输验证码；报名计划开放前 100 秒内失效的场次会直接结束。」 | local/ui/views/phone.js:346 ↳ 失效后自动登录：验证码识别本机已装，还没启用（在上面“高级功能”里点“启用”）。现在登录失效时要你输验证码；报名计划开放前 100 秒内失效的场次会直接结束。 | **一致**【已复现】 |  |
| 400 | spec:437,438 | “高级功能” | local/ui/index.html:27 ↳ 高级功能<br>local/ui/index.html:209 ↳ 高级功能 | **一致**【已复现】 |  |
| 401 | spec:438 | 「失效后自动登录：还缺验证码识别组件（在上面的“高级功能”里一键安装）。现在登录失效时要你输验证码；报名计划开放前 100 秒内失效的场次会直接结束。」 | local/ui/views/phone.js:349 ↳ 失效后自动登录：还缺验证码识别组件（在上面的“高级功能”里一键安装）。现在登录失效时要你输验证码；报名计划开放前 100 秒内失效的场次会直接结束。 | **一致**【已复现】 |  |
| 402 | spec:439 | 「账号：本机加密存储不可用，输入后只在本次运行期间有效。」 | local/ui/index.html:289 ↳ 账号：本机加密存储不可用，输入后只在本次运行期间有效。 | **一致**【已复现】 |  |
| 403 | spec:440 | 「保存的密码学校不认，自动登录已暂停。点“更换”输入新密码。」 | local/ui/index.html:301 ↳ 保存的密码学校不认，自动登录已暂停。点“更换”输入新密码。 | **一致**【已复现】 |  |
| 404 | spec:440 | “更换” | local/ui/index.html:301 ↳ 更换<br>local/ui/views/phone.js:324 ↳ 更换 | **一致**【已复现】 |  |
| 405 | spec:441 | 「保存到本机」 | local/ui/index.html:295 ↳ 保存到本机<br>local/ui/index.html:297 ↳ 保存到本机 | **一致**【已复现】 |  |
| 406 | spec:441,452 | 「取消」 | local/ui/index.html:94 ↳ 取消<br>local/ui/index.html:200 ↳ 取消 | **一致**【已复现】 |  |
| 407 | spec:441 | 「只在这次运行中用，不保存到本机」 | local/ui/index.html:295 ↳ 只在这次运行中用，不保存到本机 | **一致**【已复现】 |  |
| 408 | spec:441 | 「密码」 | local/ui/index.html:160 ↳ 密码<br>local/ui/index.html:161 ↳ 密码 | **一致**【已复现】 |  |
| 409 | spec:441 | “我已阅读并同意《隐私协议》” | local/ui/index.html:296 ↳ 我已阅读并同意《隐私协议》 | **一致**【已复现】 |  |
| 410 | spec:441 | 「登录时，工具会替你勾选学校登录页上的“我已阅读并同意《隐私协议》”。」 | local/ui/index.html:296 ↳ 登录时，工具会替你勾选学校登录页上的“我已阅读并同意《隐私协议》”。 | **一致**【已复现】 |  |
| 411 | spec:441 | 「账号」 | local/ui/index.html:134 ↳ 账号<br>local/ui/index.html:135 ↳ 账号 | **一致**【已复现】 |  |
| 412 | spec:442 | 「先不清除」 | local/ui/index.html:299 ↳ 先不清除 | **一致**【已复现】 |  |
| 413 | spec:442 | 「清除后，电脑不会再自动登录，手机上重新登录也要重新输入账号密码。」 | local/ui/index.html:299 ↳ 清除后，电脑不会再自动登录，手机上重新登录也要重新输入账号密码。 | **一致**【已复现】 |  |
| 414 | spec:442 | 「清除已保存」 | local/ui/index.html:300 ↳ 清除已保存<br>local/ui/views/phone.js:376 ↳ 清除已保存 | **一致**【已复现】 |  |
| 415 | spec:442 | 「确认清除」 | local/ui/index.html:299 ↳ 确认清除 | **一致**【已复现】 |  |
| 416 | spec:443 | 「已准备好，只在这次运行中使用。」 | local/ui/views/phone.js:1080 ↳ 已准备好，只在这次运行中使用。 | **一致**【已复现】 |  |
| 417 | spec:443 | 「已加密保存到本机。」 | local/ui/views/phone.js:1080 ↳ 已加密保存到本机。 | **一致**【已复现】 |  |
| 418 | spec:443 | 「已清除本机保存的账号密码。」 | local/ui/views/phone.js:1138 ↳ 已清除本机保存的账号密码。 | **一致**【已复现】 |  |
| 419 | spec:443 | 「清除没有完成。」 | local/ui/views/phone.js:1138 ↳ 清除没有完成。 | **一致**【已复现】 |  |
| 420 | spec:443 | 「账号信息没有保存。」 | local/ui/views/phone.js:1072 ↳ 账号信息没有保存。<br>local/ui/views/phone.js:1083 ↳ 账号信息没有保存。 | **一致**【已复现】 |  |
| 421 | spec:451 | 「导入手机控制组件」 | local/ui/views/phone.js:702 ↳ 导入手机控制组件 | **一致**【已复现】 |  |
| 422 | spec:451 | 「导入验证码识别组件」 | local/ui/index.html:431 ↳ 导入验证码识别组件<br>local/ui/views/phone.js:702 ↳ 导入验证码识别组件 | **一致**【已复现】 |  |
| 423 | spec:451 | 「选一个已经下好的组件包 ZIP。选完会立刻自检，选错了会当场说清是什么。」 | local/ui/index.html:432 ↳ 选一个已经下好的组件包 ZIP。选完会立刻自检，选错了会当场说清是什么。 | **一致**【已复现】 |  |
| 424 | spec:452 | 「安装中…」 | local/ui/views/phone.js:764 ↳ 安装中… | **一致**【已复现】 |  |
| 425 | spec:452 | 「安装这份」 | local/ui/index.html:455 ↳ 安装这份<br>local/ui/index.html:456 ↳ 安装这份 | **一致**【已复现】 |  |
| 426 | spec:452 | 「还没有选择文件」 | local/ui/index.html:437 ↳ 还没有选择文件<br>local/ui/index.html:445 ↳ 还没有选择文件 | **一致**【已复现】 |  |
| 427 | spec:452 | 「选择文件…」 | local/ui/index.html:438 ↳ 选择文件…<br>local/ui/index.html:446 ↳ 选择文件… | **一致**【已复现】 |  |
| 428 | spec:453 | 「需要 phone_control-版本号.zip，里面已经带好 cloudflared，不用另外安装。」 | local/ui/index.html:441 ↳ 需要 phone_control-版本号.zip，里面已经带好 cloudflared，不用另外安装。 | **一致**【已复现】 |  |
| 429 | spec:453 | 「需要 relogin_ocr-版本号.zip，在发布页和程序一起发布，版本要和程序一致。」 | local/ui/index.html:449 ↳ 需要 relogin_ocr-版本号.zip，在发布页和程序一起发布，版本要和程序一致。 | **一致**【已复现】 |  |
| 430 | spec:454 | 「先选文件并自检通过，再安装。」 | local/ui/views/phone.js:760 ↳ 先选文件并自检通过，再安装。 | **一致**【已复现】 |  |
| 431 | spec:454 | 「已识别为「\<组件名>」组件包，版本 \<版本号>。」 | local/ui/views/phone.js:78 ↳ 已识别为「" + (IMPORT_TITLE[key] \|\| key) + "」组件包，版本 " + version + "。 | **一致（模板归一：占位/拼接写法归一后命中）**【已复现】 | 规格占位（N/M/\<…>/HH:MM 等）对应代码变量或字符串拼接。 |
| 432 | spec:454 | 「自检没有返回结论。」 | local/ui/views/phone.js:75 ↳ 自检没有返回结论。<br>local/ui/views/phone.js:89 ↳ 自检没有返回结论。 | **一致**【已复现】 |  |
| 433 | spec:454 | 「还没有选择文件。」 | local/ui/views/phone.js:737 ↳ 还没有选择文件。 | **一致**【已复现】 |  |
| 434 | spec:454 | 「这个 ZIP 里没有组件清单，不是本程序的组件包。」 | local/ui/views/phone.js:81 ↳ 这个 ZIP 里没有组件清单，不是本程序的组件包。 | **一致**【已复现】 |  |
| 435 | spec:454 | 「这个组件包和现在的 \<版本号> 不配套。到发布页下载 \<版本号> 的组件包。」 | local/ui/views/phone.js:86 ↳ 这个组件包和现在的 " + shown + " 不配套。到发布页下载 " + shown + " 的组件包。 | **一致（模板归一：占位/拼接写法归一后命中）**【已复现】 | 规格占位（N/M/\<…>/HH:MM 等）对应代码变量或字符串拼接。 |
| 436 | spec:454 | 「这是 Tailscale 的安装程序，不是组件包。Tailscale 要用官方安装包装好并登录，不用在这里导入。」 | local/ui/views/phone.js:72 ↳ 这是 Tailscale 的安装程序，不是组件包。Tailscale 要用官方安装包装好并登录，不用在这里导入。 | **一致**【已复现】 |  |
| 437 | spec:454 | 「这里需要组件包 ZIP，不是可执行文件。」 | local/ui/views/phone.js:73 ↳ 这里需要组件包 ZIP，不是可执行文件。 | **一致**【已复现】 |  |
| 438 | spec:459 | 「停止」 | local/ui/index.html:90 ↳ 停止<br>local/ui/index.html:94 ↳ 停止 | **一致**【已复现】 |  |
| 439 | spec:459 | 「取消学校报名」 | 未检出（local/ui 全库无逐字/归一命中） | **规格元描述（红线 2 释义）**【符合】 | 「停止不等于取消学校报名」为规则表述，非界面文案。 |
| 440 | spec:459 | 「开始」 | local/ui/app.js:125 ↳ 开始<br>local/ui/app.js:497 ↳ 开始 | **一致**【已复现】 |  |
| 441 | spec:459 | 「选中」 | local/ui/app.js:458 ↳ 选中<br>local/ui/views/phone.js:964 ↳ 选中 | **一致**【已复现】 |  |
| 442 | spec:462 | 「待校准/待确认」 | local/ui/state/labels.js:82 ↳ if (left === null) return signStartKnown(item) ? "待校准" : "待公布";<br>local/ui/state/clock.js:236 ↳ if (!Number.isFinite(ms)) return { time: "--:--:--", date: "日期待确认" };<br>local/ui/state/conflict.js:41 ↳ if (n === null) return "活动时间待确认"; | **规格元描述（两种显示值，均存在）**【已复现】 | 规格枚举的两个显示值在代码中均有实际使用。 |
| 443 | spec:485 | 「校园活动预报名工具」 | local/ui/index.html:6 ↳ 校园活动预报名工具<br>local/ui/index.html:17 ↳ 校园活动预报名工具 | **一致**【已复现】 |  |
| 444 | spec:490 | 「完整 ZIP」 | 未检出（local/ui 全库无逐字/归一命中） | **分发词表（README/发布文案用词，非 local/ui 界面）**【不适用】 | §15 词表约束分发文案，不在 local/ui 界面文案比对范围。 |
| 445 | spec:497 | 「发给我」 | 未检出（local/ui 全库无逐字/归一命中） | **规格禁止示例（第一人称求助）**【符合】 |  |
| 446 | spec:497 | 「把日志发我」 | 未检出（local/ui 全库无逐字/归一命中） | **规格禁止示例（第一人称求助）**【符合】 |  |
| 447 | spec:500 | 「安装版-1.1.1.exe」 | 未检出（local/ui 全库无逐字/归一命中） | **规格元描述（「不写死版本号」的反例）**【符合】 |  |
| 448 | spec:502 | 「多校支持」 | 未检出（local/ui 全库无逐字/归一命中） | **规格禁止示例（不宣称）**【符合】 |  |
| 449 | spec:502 | 「学校官方」 | 未检出（local/ui 全库无逐字/归一命中） | **规格禁止示例（不宣称）**【符合】 |  |
| 450 | spec:502 | 「数据绝不联网」 | 未检出（local/ui 全库无逐字/归一命中） | **规格禁止示例（不承诺）**【符合】 |  |
| 451 | spec:506 | 「自 vX.Y.Z 起可下载」 | 未检出（local/ui 全库无逐字/归一命中） | **规格禁止示例（不把候选写成已发布）**【符合】 |  |
| 452 | spec:523 | 「完整条款」 | local/ui/index.html:127 ↳ 完整条款<br>local/ui/index.html:140 ↳ 完整条款 | **一致**【已复现】 |  |
| 453 | spec:523 | 「条款要点」 | local/ui/index.html:126 ↳ 条款要点<br>local/ui/index.html:151 ↳ 条款要点 | **一致**【已复现】 |  |
| 454 | spec:524,543 | 「正在保存…」 | local/ui/controllers/terms.js:193 ↳ 正在保存…<br>local/ui/views/terms.js:52 ↳ 正在保存… | **一致**【已复现】 |  |
| 455 | spec:529 | 「Esc 暂不使用」 | local/ui/index.html:181 ↳ Esc 暂不使用<br>local/ui/views/terms.js:60 ↳ Esc 暂不使用 | **一致**【已复现】 |  |
| 456 | spec:530 | 「同意时间未记录」 | local/ui/views/terms.js:226 ↳ 同意时间未记录 | **一致**【已复现】 |  |
| 457 | spec:535 | 「还没有同意使用条款。」 | local/ui/views/plan-panel.js:1355 ↳ 还没有同意使用条款。 | **一致**【已复现】 |  |
| 458 | spec:536 | 「条款状态没能确认。」 | local/ui/views/plan-panel.js:1350 ↳ 条款状态没能确认。 | **一致**【已复现】 |  |
| 459 | spec:537 | 「没有记录同意」 | 未检出（local/ui 全库无逐字/归一命中） | **规格禁止示例（坏回执不说「没有记录同意」）**【符合】 |  |
| 460 | spec:541 | 「重新打开同一份副本」 | 未检出（local/ui 全库无逐字/归一命中） | **规格禁止示例（版本不匹配只指向前）**【符合】 |  |
| 461 | spec:542 | 「请重新打开条款再确认一次」 | 未检出（local/ui 全库无逐字/归一命中） | **已废止旧句（规格声明废止）**【符合】 |  |
| 462 | spec:543 | 「保存结果未确认」 | local/ui/controllers/terms.js:274 ↳ 保存结果未确认<br>local/ui/controllers/terms.js:188 ↳ 保存结果未确认 | **一致**【已复现】 |  |
| 463 | spec:538 | 『重新确认状态』 | local/ui/index.html:117 ↳ \<button class="btn btn-line" id="btn-terms-recheck" type="button" hidden>重新确认状态\</button><br>local/ui/views/terms.js:32 ↳ recheck.textContent = "重新确认状态";<br>local/ui/controllers/terms.js:226 ↳ (version \|\| "缺失") + "）；请点「重新确认状态」核对本机记录。"<br>local/ui/controllers/terms.js:275 ↳ "门禁保持关闭。点「重新确认状态」核对本机记录。"<br>local/ui/views/terms.js:319 ↳ button.textContent = busy ? "正在核对…" : "重新确认状态"; | **一致**【已复现】 | 对抗复核补漏（2026-11-08）：原 462 条提取漏收本条（报告方法自述含『』），补入后全表 463 条。 |

## NEEDS-HUMAN：9 条归并 4 个议题（需人定改规格还是改代码）

素材 9 条 NEEDS-HUMAN（spec:195、spec:262、spec:340、spec:370-375 六条）归并为 4 个议题。以下规格、代码原文均逐字取自上表对应条目。4 个议题经对抗复核独立证实（见同目录 `ADVERSARIAL-L5.md`），维持待决。

### 议题一：时间线占位词三方不一致（spec:195，条目 170）

- 规格（逐字）：「待启动 / 待打开 / 待发生」
- 代码三处：
  - local/ui/views/plan-panel.js:773 ↳ { name: "本次启动", time: runStarted ? routeTime(runStarted) : "待启动", done: runStarted !== null },
  - local/ui/views/plan-panel.js:774 ↳ … : "待准备", done: ready !== null },
  - local/ui/views/plan-panel.js:758 ↳ * 显示「待启动/待打开/待开始」，不得拿计划时刻或当前时间编造
- 素材备注（逐字）：时间线未发生占位：代码实际用「待启动 / 待准备 / 待定」(773-778)，注释写「待启动/待打开/待开始」，规格写「待启动 / 待打开 / 待发生」——三方不一致。
- 待决：三个词表（规格 / 代码实际取值 / 代码注释）以哪一方为准。

### 议题二：spec:262 与 b-amendment-007 冲突（条目 233）

- 规格（逐字）：「打开学校活动页核对」
- 代码两处：
  - local/ui/views/plan-panel.js:661 ↳ text: "工具不会自动重发，到学校活动页核对。", frame: "warn", led: null };
  - local/ui/views/plan-panel.js:1147-1148 ↳ * 不做「打开活动页」（后端没有按活动打开学校页面的接口，b-amendment-007）
- 素材备注（逐字）：规格 §8 红线固定下一步为「打开学校活动页核对」；代码按 b-amendment-007 有意只写「到学校活动页核对」。规格与代码决策冲突。
- 待决：改规格 §8 的固定下一步措辞，或推翻 b-amendment-007。

### 议题三：spec:340 规格自相矛盾（条目 278）

- 规格（逐字）：「登录剩余时间仅供参考，以学校校验为准。」
- 代码两处：
  - local/ui/index.html:350 ↳ \<!-- 登录详情卡：只写登录有效与否和上次校验时刻，不显示剩余时间（学校不公布，工具不估算） -->
  - local/ui/views/login.js:74 ↳ note = "学校确认登录有效；有效多久学校不公布，工具不估算";
- 素材备注（逐字）：规格 §10 浮层内容含「登录预计剩余时间」与固定说明本句；代码按 §3 红线「登录不估算剩余时间」与决策 014 有意不实现，规格 §10 未同步。
- 待决：删去规格 §10 的「登录预计剩余时间」与固定说明句（对齐 §3 红线与决策 014），或恢复实现。

### 议题四：spec:370-375 §11 六步引导过时（代码已五步），6 条（条目 292-297）

- 代码侧总述（素材原文）：local/ui/state/store.js:26-28 ↳ /* … 3：新工作台（决策 009 修订）由六步改为五步，启动时机改为登录成功且列表加载后。 */ const TOUR_VERSION = 3;
- 素材备注（逐字，条目 292）：规格 §11 六步引导整块（本条+下 5 条）已被五步引导取代（store.js:30-44，标题/文案全部不同）；规格未回改。
- 六条逐条对照：

1. spec:370 规格（逐字）「这里是登录状态和「登录 / 刷新」入口。…只有提示失效时才需要重新登录。」
   代码侧：
   - local/ui/state/store.js:26-28 ↳ /* … 3：新工作台（决策 009 修订）由六步改为五步，启动时机改为登录成功且列表加载后。 */ const TOUR_VERSION = 3;
   - local/ui/state/store.js:10 ↳ { no: 1, title: "确认登录", text: "顶部显示“已登录”就可以继续。只有提示失效时才需要重新登录。" },
   备注（逐字）：规格 §11 六步引导整块（本条+下 5 条）已被五步引导取代（store.js:30-44，标题/文案全部不同）；规格未回改。

2. spec:371 规格（逐字）「「预报名」等待学校开放，「立即报名」在计划启动后尝试提交。选择活动不会自动开始报名。」
   代码侧：
   - local/ui/state/store.js:34-35 ↳ { target: "list", title: "这是活动时刻表", text: "活动按开放时间排好。「预报名」等开放后自动提交，「立即报名」点开始后马上提交。上面可以搜索和筛选。" },
   备注（逐字）：最接近代码如引。

3. spec:372 规格（逐字）「按名称、地点或时间查找活动，也可筛选签到和签退要求。未说明的要求以学校活动页为准。」
   代码侧：
   - local/ui/state/store.js:34-35 ↳ 同上（引导中无签到/签退筛选句；筛选控件本身在 index.html:40 存在）

4. spec:373 规格（逐字）「勾选要报名的活动。举办时间重叠的活动不能同时加入计划。」
   代码侧：
   - local/ui/state/store.js:36-37 ↳ { target: "row", interactive: true, title: "勾选想报的活动", text: "点这一行试试。勾选只是加入计划，不会开始报名；举办时间重叠的活动不能同时选。" },

5. spec:374 规格（逐字）「设置尝试时长和最多提交次数，再选择「开始报名计划」。达到…任一条件后，工具停止尝试。」
   代码侧：
   - local/ui/state/store.js:38-39 ↳ { target: "select", title: "核对计划，再点开始", text: "选好的活动都列在这里，可以逐场移除，也能修改尝试时长。开始不了时，按钮下面会写还差什么。" },

6. spec:375 规格（逐字）「可最小化窗口，但不要关闭工具或让电脑睡眠。…显示「待核对」时，到学校活动页确认。」
   代码侧：
   - local/ui/state/store.js:40-41 ↳ { target: "run", title: "开始以后看这里", text: "这里显示倒计时，下面是每场进度。可以最小化窗口，但不要关闭工具或让电脑睡眠。看到「待核对」时，到学校活动页确认。" },
   备注（逐字）：前半句逐字存在；规格省略处「…显示「待核对」」代码作「看到「待核对」」。

- 待决：按五步引导（store.js:30-44）回改规格 §11，或在规格标注 §11 已废止。

## 修订记录（对抗审阅 2026-11-08）

对抗审阅两路（实质反证 + 机械核验；身份安排、判定全文见同目录 `ADVERSARIAL-L5.md`）之后修订本报告。所有行号与证据修正落笔前均以 `sed -n` / `grep` 实测磁盘原文（含 `git show a85209e` 基线回退）。三档结论：462 条中站得住 444、部分站不住 15（条目 5、8、53、54、86、88、89、98、161、164、195、216、234、280、353）、推翻 3（条目 33、175、377）；红牌 0；补漏 1 条（条目 463）。整体结论不变：文案真源与实现一致性成立，22 条不一致与 4 条代码没有全部站得住。

1. **推翻重判 3 条**：条目 33——spec:73「正在处理」为否定式提及（「忙时不拿「正在处理」替换登录结论」），唯一出现 login.js:19 是重申禁令的注释，全库无用户可见命中，「一致」→「规格禁止示例·符合」；条目 175——spec:197「要求 + 时间段」为格式元描述，唯一出现 filters.js:43 是注释，「一致」→「规格元描述」（同条目 11/262 口径）；条目 377——spec:421 括注「读不到版本号时不写「版本…」」为否定式，settings.js:228 条件省略=符合，原引 views/terms.js:234 是条款弹窗注释「程序要求版本…」（实际在 233-234 行）文不对题，「一致」→「规格禁止示例·符合」并撤原证据。
2. **归类调整 1 条**：条目 8 从「规格禁止示例」单列为「规格示例格式」——spec:17 把「约到 xx 过期」列为「说估算就写约」的格式示例而非禁语；备注补 state/login.js:62-63 未接线的 expiryText()（「约到 」拼接）死代码提示。
3. **部分站不住 15 条证据修正**（结论方向均维持）：条目 53/54 行号改现盘 list.js:325-327/343（基线 a85209e 为 275-277/293，原引 339-340/347 两处状态均不含该代码）；条目 86 → plan-panel.js:125/1323（原引 122 为注释）；条目 88 → :130-135（原引 129 为注释）；条目 89 → time.js:94/95/106（原引 time.js:102、plan-panel.js:137 均为注释）；条目 161/234 → :1092（原引 1085 为注释）；条目 164 → :925/932、条目 195 → :932（原引 921 为注释）；条目 280 → clock.js:304（原引 299 为注释）；条目 98/216/353 证据串逐字修正（98 首段实为单引号 JS 串；216 补回丢失的字符串定界引号；353 pairLeftText 原报告误写 airLeftText）；条目 5 备注补「引句为免责句子串，非标签用法」（真实标签 labels.js:48、plan.js:471、plan-panel.js:650）。
4. **行号漂移补注 7 处**（内容逐字核到，不重排名）：条目 24/278 login.js:74→现盘 73；条目 292-297 store.js 引用行整体 −3（26-28→23-24、34-35→31-32、36-37→33-34、38-39→35-36、40-41→37-38，TOUR_VERSION=3 现盘 24 行、五步主线 31-40 行），各条备注已补现盘行号。
5. **补漏 1 条**：新增条目 463——spec:538『重新确认状态』（index.html:117、views/terms.js:32/319、controllers/terms.js:226/275，一致），原 462 条提取漏收。
6. **统计重算**：修订前 一致 402 / 不一致 22 / 代码没有 4 / 禁止示例+已废止 28 / 元描述 5 / 词表 1 = 462；修订后 一致 399 / 不一致 22 / 代码没有 4 / 禁止示例·已废止 29 / 规格示例格式 1 / 元描述 6 / 词表 1 = 462，另补漏 1 条（条目 463，一致），全表 463（一致含补漏 400）。NEEDS-HUMAN 4 议题经对抗复核独立证实，维持待决。
