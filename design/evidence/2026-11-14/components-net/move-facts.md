# 搬家事实：views/phone.js 与 views/settings.js 的四张表

- **基线提交**：`dda275e`。执行日期：2026-11-14（表一、表一·面板成员、反向表、表三由脚本
  本轮修订后重出）。
- **用途**：下一批把「组件与手机访问」拆成模块要用的事实。只清点，不改任何文件。
- 各表的量法与复跑命令写在表上方；表一、表一·面板成员、反向表、表三由
  `scripts/move_facts.py` 出（只读，结果打印到标准输出）；表二、表四由人工逐个方法、
  逐个阶段读代码填，每格带函数名，便于抽查。
- **本轮修订说明**：表一的量法原来把「前面带点」的引用全部排除，于是经
  `window.PhonePanel` 的引用一条没算（app.js、views/plan-panel.js、views/status-cards.js
  各有，views/settings.js 有十几处）——这组引用正是搬成模块时最要紧的，本轮把它们与
  `typeof PhonePanel` 这类裸名判断一起算进来；表一·面板成员与反向表是本轮新增，
  分别回答「别的脚本用了这两个面板的哪些成员」与「这两个文件自己用到了哪些定义在
  别的脚本里的名字」。

---

## 表一 名字引用

**量法**：抹掉字符串与注释后按词匹配；裸名字与 typeof 判断（`typeof PhonePanel`）算
引用；经显式挂载点的访问（`window.PhonePanel`、`globalThis.PhonePanel`）也算引用——
搬成模块后这些引用要靠挂载点接上；其余前面带点（属性访问）不算；本文件有同名声明的
名字在该文件里不算；import 具名引用算引用；「加载期」= 引用出现在任何函数体之外的
顶层。两个目标文件互为「别的脚本」。
**复跑命令**：`python -B design/evidence/2026-11-14/components-net/scripts/move_facts.py`

### views/phone.js 的顶层名字

| 名字 | 被谁引用 | 结论 |
|---|---|---|
| phonePhase | 无 | 只在本文件内用 |
| phoneLinkedNow | 无 | 只在本文件内用 |
| channelCards | 无 | 只在本文件内用 |
| IMPORT_TITLE | 无 | 只在本文件内用 |
| importCheckText | 无 | 只在本文件内用 |
| PHONE_DOWNLOAD_REASON | 无 | 只在本文件内用 |
| downloadFailText | views/settings.js 2 处（paintOcrDownload 的红条拼法，函数内） | 有跨文件引用 |
| pairLeftText | 无 | 只在本文件内用 |
| maskAccount | views/plan-panel.js 2 处（核对计划面板的账号打码，函数内） | 有跨文件引用 |
| agoText | 无 | 只在本文件内用 |
| phoneShow / phoneText | 无 | 只在本文件内用 |
| PhonePanel | app.js 3 处（check 事件处理器经 `window.PhonePanel` 触发 refresh，函数内）、views/help.js 2 处（帮助弹窗打开时经 `typeof PhonePanel !== "undefined"` 触发 refresh，函数内）、views/plan-panel.js 3 处（计划面板读 state、调 refresh，函数内）、views/settings.js 20 处（读 state、busy、installing、feature，调 refresh/downloadComponent/cancelComponent/openComponents，函数内）、views/status-cards.js 2 处（顶栏手机标识读 state，函数内） | 有跨文件引用 |

### views/settings.js 的顶层名字

| 名字 | 被谁引用 | 结论 |
|---|---|---|
| settingsOpen | app.js 2 处 | 跨文件 |
| openSettings | app.js 2 处；views/phone.js 2 处（goSaveCredentials）；views/status-cards.js 2 处 | 跨文件 |
| openSettingsSection | app.js 2 处 | 跨文件 |
| closeSettings | app.js 1 处 | 跨文件 |
| paintSettings / paintClosePref / saveClosePref / termsWithdrawAskOpen / formatAcceptedAt / paintTermsRow / withdrawTerms | 无 | 只在本文件内用 |
| ocrFeature | 无 | 只在本文件内用 |
| OcrPanel | views/phone.js 9 处（downloadComponent/cancelComponent/installComponent 写 note、error） | 跨文件 |
| ocrPhase / ocrShow / ocrText / ocrLoadLocation | 无 | 只在本文件内用 |
| paintOcrDownload | views/phone.js 2 处（paint 里 `typeof paintOcrDownload === "function"` 后调用） | 跨文件 |
| enableOcr / openOcrDir | 无 | 只在本文件内用 |
| wireSettings | app.js 1 处，**加载期**（app.js 顶层直接调用） | 跨文件，唯一加载期引用 |

## 表一·面板成员

**量法**：在别的脚本里找「`(window.)面板名.成员`」的引用；每个引用归属到它所在的最内层
有名字的函数体（plain function、对象方法简写、对象成员箭头函数、const 赋值的箭头函数
都算；控制语句的括号头不算），不在任何函数体里记「顶层」。本文件用自己面板的成员不在
此表——那是表二的事。
**复跑命令**：同表一。

### PhonePanel（定义于 views/phone.js）的成员被谁用

| 成员 | 被谁用（几处、函数） | 搬家含义 |
|---|---|---|
| refresh | app.js 2 处（check 事件处理器）；views/help.js 1 处（showHelp）；views/settings.js 4 处（enableOcr 2 处、openSettings 2 处） | 跨文件调用最多的方法 |
| state | views/plan-panel.js 2 处（autoLoginCredential）；views/status-cards.js 1 处（phoneSnapshot） | 顶栏与计划面板直接读快照 |
| busy | views/settings.js 1 处（paintOcrDownload） | 三类动作共用的忙碌位被另一文件读（见表二 busy 行） |
| installing | views/settings.js 2 处（paintOcrDownload） | 安装标志被另一文件的绘制读 |
| feature | views/settings.js 2 处（ocrFeature） | 组件快照的统一取用口 |
| downloadComponent / cancelComponent / openComponents | views/settings.js 各 1 处（wireSettings 绑定按钮） | settings.js 的事件绑定直接挂这三个方法 |
| 其余成员（pending、notes、stopAsk、addPair、location 等） | 无别的脚本引用 | 只在本文件内用 |

### OcrPanel（定义于 views/settings.js）的成员被谁用

| 成员 | 被谁用（几处、函数） | 搬家含义 |
|---|---|---|
| note / error | views/phone.js 各 3 处（installComponent、downloadComponent、cancelComponent 写入） | phone.js 的下载、取消、导入三路写验证码识别的反馈位（见表二 note/error 行） |
| busy / location / lastDownload | 无别的脚本引用 | 只在本文件内用 |

## 反向表

**量法**：把其余界面脚本（led.js 与手机页 m/ 不算）的顶层声明名取并集，逐个在这两个
文件里按词找引用（挂载点访问也算，前面带点不算）；本文件自己声明过的名字不算。
每个名字列出引用几处、在哪些函数里用（最内层函数）、有没有加载期就用的。
**复跑命令**：同表一。

### views/phone.js 用到的外部名字

| 名字 | 几处 | 定义于 | 在哪些函数用 |
|---|---|---|---|
| $ | 89 处 | state/store.js | importCheckText、phoneShow、phoneText、startPolling、paint、paintRelogin、paintCredForm、paintPhoneAccess、paintCountdown 等 |
| api | 15 处 | controllers/bridge.js | refresh、loadLocation、pickComponent、inspectComponent、installComponent、enableFeature、toggleStart、toggleStop 等 |
| OcrPanel | 9 处 | views/settings.js | installComponent、downloadComponent、cancelComponent |
| openSettings | 2 处 | views/settings.js | goSaveCredentials |
| paintOcrDownload | 2 处 | views/settings.js | paint |
| paintStatusCards | 2 处 | views/status-cards.js | paint |

### views/settings.js 用到的外部名字

| 名字 | 几处 | 定义于 | 在哪些函数用 |
|---|---|---|---|
| $ | 40 处 | state/store.js | openSettings、openSettingsSection、closeSettings、paintClosePref、paintTermsRow、withdrawTerms、ocrShow、ocrText、paintOcrDownload、enableOcr、openOcrDir、wireSettings 等 |
| PhonePanel | 20 处 | views/phone.js | openSettings、ocrFeature、paintOcrDownload、enableOcr、wireSettings |
| S | 14 处 | state/store.js | settingsOpen、openSettings、closeSettings、paintClosePref、saveClosePref、paintTermsRow、ocrFeature、wireSettings |
| api | 4 处 | controllers/bridge.js | withdrawTerms、ocrLoadLocation、enableOcr、openOcrDir |
| ingestTerms / termsAccepted / helpStatus / downloadFailText / closeStatusCards | 各 2 处 | controllers/terms.js、features/terms/state.js、views/help.js、views/phone.js、views/status-cards.js | withdrawTerms、paintTermsRow、paintOcrDownload、openSettings |
| savePrefs / msg / render / addLog / paintBanners | 各 1 处 | controllers/prefs.js、state/store.js、views/list.js、views/login.js、views/plan-panel.js | saveClosePref、withdrawTerms |

**反向表要点**：两个文件都没有加载期就用的外部名字——外部引用全部在函数体内（包括
经 `window.PhonePanel` 的访问）；大头是取元素的 `$` 与发桥接请求的 `api`，搬成模块后
这两类要走模块的公共层，不能再依赖全局裸名；`OcrPanel`、`openSettings`、
`paintOcrDownload`、`paintStatusCards`、`downloadFailText` 是两个目标文件与其他视图之间
的真实耦合，与表一互相印证。

**搬家要点**（表一 + 成员 + 反向）：加载期引用只有一处（app.js 顶层调 `wireSettings()`）；
`downloadFailText`、`OcrPanel`、`paintOcrDownload`、`openSettings`、`maskAccount` 是两个
目标文件与其他脚本之间的真实耦合，拆模块时要么一起搬、要么经显式挂载点；
`PhonePanel` 已有 `window.PhonePanel = PhonePanel` 挂载（文件尾），而且别的脚本对它的
引用几乎全部走这个挂载点（app.js 3 处、plan-panel.js 3 处、settings.js 20 处、
status-cards.js 2 处，help.js 用 typeof 裸名判断），搬成模块后这组引用必须继续经挂载点
或改成模块导入；`OcrPanel` 没有挂载、靠加载顺序共享全局。

---

## 表二 成员归属

**量法**：逐个方法、逐个字段读 `local/ui/views/phone.js`（基线 dda275e，行号见括号）与
`local/ui/views/settings.js`，归入五类：组件安装路径、手机访问、保存的账号与登录恢复、
导入弹窗、公共；写每个方法读写了哪些字段、调用了哪些别的方法；被两类以上共用（或被
另一文件写入）的字段单独列出。
**复跑方式**：人工对照两个文件重填；方法行号随文件头注释。

### PhonePanel 的字段（phone.js 155–196）

| 字段 | 归类 | 写入 | 读取 | 共用？ |
|---|---|---|---|---|
| `state`（155–160） | 公共 | refresh（合并快照） | paint、paintPhoneAccess、paintRelogin、paintCredForm、feature、downloadActive、needsPolling、selectedChannel、copyAddress、openComponentDir | 手机访问+组件+登录恢复三层共用；plan-panel.js 与 status-cards.js 也经挂载点读（见面板成员表） |
| `busy`（161） | **共用** | enableFeature:847、toggleStart:866、toggleStop:890、downloadComponent:1013、saveCredentials:1099 置真；各 finally（856/883/906/1022/1111）置假 | paint:302、paintRelogin:322、paintCredForm:419/431、paintPhoneAccess:438、startPolling:246 | 手机访问开合、组件下载、登录恢复保存三类动作共用；settings.js paintOcrDownload:204 也读（经 window.PhonePanel） |
| `pending`（164） | 手机访问 | toggleStart:867（"starting"）、toggleStop:891（"stopping"）；finally 882/905 清 | paintPhoneAccess:439 | 否；toggleStart:864 与 toggleStop:889 的重入守卫也读 |
| `pollTimer`/`pollTicks`（165–166） | 手机访问（轮询） | startPolling/stopPolling | startPolling:242/246–251 | 轮询条件 needsPolling 读组件下载态 → 与组件共用触发条件 |
| `tickTimer`（167） | 手机访问 | startTick/stopTick | startTick:264 | 否 |
| `lastCode`（168） | 手机访问 | paintPhoneAccess:648/650 | paintPhoneAccess:641 | 否 |
| `channel`（170） | 手机访问 | changeChannel:1065 | selectedChannel:293 | 否 |
| `notes`（172） | **共用**（手机访问的反馈位，组件下载也写） | enableFeature:848/858–859（feature、off）、downloadComponent:1014/1031（missing）、cancelComponent:1055–1056（loading）、toggleStart:868–869/874/876（off、offErr、pair）、toggleStop:892/897–900（onErr、off、offErr）、copyAddress:999（onErr）、recheckTailscale:1082（off）、paintPhoneAccess:463（off，安装完成句）、goSaveCredentials/cancelStop 等 paint 前清空 | paintPhoneAccess（notes.feature/missing/loading/off/offErr/pair/onErr 六处取用）、paintRelogin 不读 notes | 写入方法跨三类 → 拆模块时这七个键要按块拆 |
| `stopAsk`（174） | 手机访问 | askStop:913、cancelStop:917、confirmStop:922、paintPhoneAccess:467/687 | paintPhoneAccess:687–688 | 否 |
| `addPair`/`addPairAt`（175–176） | 手机访问 | addPairing:930–931、paintPhoneAccess:627/468 | paintPhoneAccess:627–628 | 否 |
| `copied`/`copyTimer`（177–178） | 手机访问 | copyAddress:1000–1004 | paintPhoneAccess:674 | 否 |
| `location`（180） | 组件安装路径 | loadLocation:220–224 | paintPhoneAccess:544–551 | 否（显示在手机访问卡片的「装在/会装到」行） |
| `lastDownload`（181） | 组件安装路径 | paintPhoneAccess:465 | paintPhoneAccess:461–462 | 否 |
| `codeLeft`/`codeSync`（183–184） | 手机访问 | paintPhoneAccess:634–637 | paintCountdown:704、paintPhoneAccess:634 | 否 |
| `picked`/`verified`（186–187） | 导入弹窗 | openComponents:716–717、inspectComponent:761–762/772、installComponent:803–804 | paintComponents:737–738、inspectComponent:761、installComponent:787 | 否 |
| `clearConfirm`（189） | 保存的账号与登录恢复 | askClearCredentials:1150、cancelClearCredentials:1155、confirmClearCredentials:1161 写 | paintRelogin:330/395/398 | 否（paintRelogin 与三个清除动作读写；paintPhoneAccess 不碰这个字段） |
| `credForm`/`credNote`/`credNoteTone`（191–193） | 保存的账号与登录恢复 | openCredForm:1126–1127、cancelCredForm:1139、goSaveCredentials:940–944、saveCredentials:1114–1119、clearCredentials:1173–1174、askClearCredentials:1151 | paintRelogin:329/404–406、paintCredForm 不读、goSaveCredentials:939 | 否 |
| `importKey`（194） | 导入弹窗 | openComponents:715、paintComponents:729（规整） | paintComponents:729、installComponent:786（经 key） | 否 |
| `installing`（196） | **共用**（导入弹窗置位、两段绘制读） | installComponent:793（true）、820（false） | paintPhoneAccess:445、settings.js paintOcrDownload:200–201 | 导入弹窗 → 组件安装路径的绘制；两组件各占一个键（phone_control/relogin_ocr） |

### PhonePanel 的方法（phone.js 198–1242）

| 方法 | 归类（行号） | 读写 | 调用 |
|---|---|---|---|
| `refresh`（198） | 公共 | state 合并；location | api("phone_access_state")、loadLocation、paint、paintComponents、needsPolling、startPolling/stopPolling、startTick/stopTick |
| `loadLocation`（216） | 组件安装路径 | location | api("advanced_component_location") |
| `downloadActive`（227） | 组件安装路径 | state.advanced（只读） | — |
| `needsPolling`（235） | 组件安装路径+手机访问 | state（只读） | downloadActive |
| `startPolling`（241） | 手机访问（触发条件含组件） | pollTimer、pollTicks、busy:246 读 | needsPolling、stopPolling:245、refresh:251 |
| `stopPolling`（255） | 手机访问 | pollTimer | — |
| `startTick`（262）/`stopTick`（272） | 手机访问 | tickTimer、codeLeft:265、paintCountdown:267 | — |
| `feature`（279） | 公共 | state.advanced（只读） | — |
| `selectedChannel`（286） | 手机访问 | state、channel（只读） | — |
| `paint`（298） | 公共（总重画） | busy:302 读、phoneRemove:310 | paintStatusCards、paintPhoneAccess:309、paintRelogin:311、paintOcrDownload:313 |
| `paintRelogin`（321） | 保存的账号与登录恢复 | busy:322 读、credForm、clearConfirm、credNote/credNoteTone:404–406 | paintCredForm:393、phoneShow/phoneText、maskAccount:342 |
| `paintCredForm`（412） | 保存的账号与登录恢复 | busy:419/431 读、state（只读） | — |
| `paintPhoneAccess`（437） | 手机访问（含组件安装行的绘制：missing/downloading/verifying/checking/outdated/broken 块与标题行按钮） | busy:438、pending:439、installing:445 读；notes 读写；lastDownload:461–465；codeSync/codeLeft:634–637；lastCode:641–650；stopAsk:467/687；addPair:627–628；copied:674；location:544 | phonePhase:443、phoneLinkedNow:448、channelCards:579、selectedChannel:578、downloadFailText:537/617、paintCountdown:638、phoneShow/phoneText |
| `paintCountdown`（701） | 手机访问 | codeLeft:704 | pairLeftText:705 |
| `openComponents`（711） | 导入弹窗 | importKey:715、picked/verified:716–717 | paintComponents:723、showComponentNote:721、dlg.showModal:724 |
| `paintComponents`（728） | 导入弹窗 | importKey、picked、verified:737–738 | phoneShow:734 |
| `pickComponent`（743） | 导入弹窗 | — | api("pick_advanced_component")、inspectComponent:753、showComponentNote:748 |
| `inspectComponent`（758） | 导入弹窗 | picked:761、verified:762/772 | api("inspect_advanced_component"):770、importCheckText:771、showComponentNote:771、paintComponents:773 |
| `showComponentNote`（776） | 导入弹窗 | DOM note | — |
| `installComponent`（785） | 导入弹窗（安装动作 → 组件安装路径） | verified:787、installing:793/820、picked/verified:803–804、notes.off/notes.missing:810–811、OcrPanel.note/error:813–814 | api("install_advanced_feature"):798、showComponentNote:801/807、closeComponents:816、refresh:817、paint:794/824、paintComponents:822 |
| `closeComponents`（828） | 导入弹窗 | dlg | — |
| `featureAction`（836） | 手机访问（分派：启用或导入） | dataset.action:838 | enableFeature:839、openComponents:842 |
| `enableFeature`（845） | 手机访问（启用位） | busy:846/856、notes.feature:848/859、notes.off:858 | api("enable_advanced_feature"):852、paint:849、refresh:860 |
| `toggleStart`（863） | 手机访问 | busy:864/866/883、pending:864/867/882、notes.off/offErr:868–874、notes.pair:876、addPair:877 | api("start_phone_access"):872、paint:870、selectedChannel:865、refresh:884 |
| `toggleStop`（888） | 手机访问 | busy:889/890/906、pending:889/891/905、notes.onErr/off/offErr:892/897–900 | api("stop_phone_access"):895、paint:893、refresh:907 |
| `askStop`（912）/`cancelStop`（917）/`confirmStop`（922） | 手机访问 | stopAsk | paint、toggleStop:925 |
| `addPairing`（929） | 手机访问 | addPair、addPairAt、notes.pair:932 | paint:933 |
| `goSaveCredentials`（937） | 保存的账号与登录恢复 | credForm、credNote:940、openSettings 联动 | openSettings:938、paint:947、user.focus |
| `openComponentDir`（952） | 组件安装路径 | location:961–962、notes.onErr/offErr/feature:963–965 | api("open_advanced_component_dir"):955、phonePhase:961、paint:966 |
| `copyByTextarea`（970）/`copyAddress`（985） | 手机访问 | copied、copyTimer、notes.onErr:999、state.address:986 | navigator.clipboard、paint:1005 |
| `downloadComponent`（1010） | 组件安装路径（两组件共用一条事务） | busy:1012/1013/1022、notes.missing:1014/1031、OcrPanel.note/error:1027–1028 | api("download_advanced_feature"):1018、paint:1015、refresh:1033、startPolling:1035 |
| `cancelComponent`（1038） | 组件安装路径 | notes.loading:1055、OcrPanel.note/error:1049–1051 | api("cancel_advanced_feature_download"):1042、refresh:1058 |
| `changeChannel`（1062） | 手机访问 | channel:1065、notes.off/offErr:1066–1067 | api("set_phone_access_preferences"):1070、paint:1068、refresh:1074 |
| `recheckTailscale`（1078） | 手机访问 | notes.off:1082 | refresh:1079、paint:1083 |
| `saveCredentials`（1089） | 保存的账号与登录恢复 | busy:1099/1111、credForm:1114、credNote/credNoteTone:1115/1118–1119 | api("prepare_phone_relogin")/api("save_relogin_credentials"):1103–1104、refresh:1121 |
| `openCredForm`（1125）/`cancelCredForm`（1139） | 保存的账号与登录恢复 | credForm、credNote、输入框 | paint、focus |
| `askClearCredentials`（1149）/`cancelClearCredentials`（1155）/`confirmClearCredentials`（1160） | 保存的账号与登录恢复 | clearConfirm:1150/1155/1161、credNote:1151 | paint、clearCredentials:1163 |
| `clearCredentials`（1166） | 保存的账号与登录恢复 | credNote/credNoteTone:1173–1174 | api("clear_relogin_credentials"):1169、refresh:1175 |
| `wire`（1178） | 公共（绑定 + 末尾 refresh:1241） | — | downloadComponent:1190、cancelComponent:1192、featureAction:1194、openComponents:1197/1392…、pickComponent、installComponent、closeComponents、changeChannel:1211、toggleStart/askStop/cancelStop/confirmStop:1213–1216、addPairing、goSaveCredentials、openComponentDir、recheckTailscale、copyAddress、openCredForm、cancelCredForm、paintCredForm:1231/1234、saveCredentials、askClearCredentials、cancelClearCredentials、confirmClearCredentials、refresh:1241 |

### OcrPanel 与 settings.js 的函数（settings.js 142–345）

| 成员 | 归类（行号） | 读写 | 调用 |
|---|---|---|---|
| `OcrPanel.busy`（143） | 验证码识别（组件） | enableOcr:316/326 置位清位；paintOcrDownload:204 读 | — |
| `OcrPanel.note`/`error`（144–145） | **共用**（本文件动作 + phone.js 的下载/取消/导入三路写入） | enableOcr:317–318/328–329、openOcrDir:343、paintOcrDownload:210/212/268；phone.js downloadComponent:1027–1028、cancelComponent:1049–1051、installComponent:813–814 | — |
| `OcrPanel.location`（146） | 组件安装路径 | ocrLoadLocation:184–185 | paintSettings:55 |
| `OcrPanel.lastDownload`（147） | 组件安装路径 | paintOcrDownload:209/212 | — |
| `ocrPhase`（152） | 验证码识别（认阶段） | 只读入参 | — |
| `ocrLoadLocation`（180） | 组件安装路径 | location | api("advanced_component_location") |
| `paintOcrDownload`（193） | 验证码识别（含安装路径绘制） | busy:204 读（OcrPanel.busy + PhonePanel.busy）、installing:200–201 读、lastDownload:209/212、note/error:210/268 | ocrPhase:197、downloadFailText:266、ocrShow/ocrText |
| `enableOcr`（314） | 验证码识别（启用位） | busy:315–316/326、error/note:317–318/328–329 | api("enable_advanced_feature"):322、paintOcrDownload:319/331、PhonePanel.refresh:330 |
| `openOcrDir`（335） | 组件安装路径 | error:343 | api("open_advanced_component_dir"):338、paintOcrDownload:344 |
| `wireSettings`（347） | 公共（绑定） | — | closeSettings:349、openSettingsSection:354、saveClosePref:358、paintTermsRow:367/374、withdrawTerms:377、PhonePanel.downloadComponent:380、PhonePanel.cancelComponent:384、enableOcr:387、PhonePanel.openComponents:392、openOcrDir:396 |

### 两个文件之外的共用点

- `PhonePanel.busy`：settings.js paintOcrDownload 也读（经 `window.PhonePanel`）——三类动作共用一个忙碌位，拆模块时这是最大的共用字段。
- `PhonePanel.installing`：导入弹窗置位、phone.js 与 settings.js 两段绘制都读。
- `OcrPanel.note`/`error`：phone.js 有三处写入（下载、取消、导入）。
- `PhonePanel.openComponents`：settings.js 一处调用（`openComponents("relogin_ocr")`）。
- `downloadFailText`：settings.js paintOcrDownload 拼红条时调用 phone.js 的函数。

**已知事实（记录，不在本计划修）**：saveCredentials 入口不查 busy 就直接置位
（phone.js:1099）。用户能到它的唯一入口是保存按钮的点击（wire 里的 save 监听，
phone.js:1235），而保存按钮忙时已被 paintCredForm 禁用（`save.disabled =
!!PhonePanel.busy || …`，phone.js:431），账号表单也不包 form、回车不会触发提交——
入口没有守卫，但界面上到不了。

---

## 表三 按路径加载的测试

**量法**：逐个测试文件找两种方式——读源码（read / read_text / `_read` 指到这两个文件），
`run_phone_js(..., files=[...])` 的 files 参数（ast 解析；片段还原后列出片段里用到的
这两个文件的顶层名字）。行号按当前文件。
**复跑命令**：`python -B design/evidence/2026-11-14/components-net/scripts/move_facts.py`

### 读源码的测试（改这两个文件的文字会碰到的断言）

| 测试文件 | 行号 | 方式 | 用到的名字 |
|---|---|---|---|
| test_phone_ui.py | 1568、1909 | `read_text` phone.js | 下载按钮/标题行相关文字断言 |
| test_reason_maps.py | 27、36 | `read_text` phone.js | PHONE_DOWNLOAD_REASON（下载原因文案与 app.py 对照） |
| test_ui_contract_components.py | 21、77、118、141 | `read` / `read_text` phone.js、settings.js | 组件包文案、installEl.disabled、openComponents 调用计数、cloudflared_missing 标记 |
| test_ui_contract_settings.py | 970 | `self._read("ui","views","phone.js")` | cloudflared_missing / componentMissing / 安装入口标记 |

### files 参数加载的测试（改这两个文件的行为会碰到的用例）

全部在 `test_phone_ui.py`（39 处调用）：行 568、586、601、618、660、695、716、748、766、802、836、864、892、922、964、992、1014、1030、1074、1114、1140、1159、1183、1201、1211、1246、1285、1309、1337 及其余（完整清单见 move_facts.py 输出）。

- 绝大多数片段只用到 `PhonePanel`（重入画、触发动作）；个别片段用到 `downloadFailText`（行 1211 一带的下载失败文案）。
- `views/settings.js` 出现在 files 里时片段通常仍只直接用 `PhonePanel`（间接经 `paintOcrDownload`/`OcrPanel` 生效）。

**搬家要点**：这 39 处 `run_phone_js(..., files=[...])` 按文件路径加载，下一批搬成模块后
`files` 参数要跟着改成模块入口或改走整页清单——这正是新用例不走按路径加载的原因。

---

## 表四 两段绘制的逐阶段对照

**量法**：逐阶段读 `paintPhoneAccess`（phone.js 437–698）与 `paintOcrDownload`
（settings.js 193–311），列出每个阶段各自画了哪些元素、写了哪些字；同一阶段两边做法
不同的地方在右列写明。认阶段的判定分别由 `phonePhase`（14–25）与 `ocrPhase`（152–162）
给出。写「可见」「显示」「收起」的格同时核对了元素自己的 hidden 与它所在块的显示条件。
**复跑方式**：人工对照两个函数重填；元素 id 在 index.html。

| 阶段 | phone.js 侧（paintPhoneAccess） | settings.js 侧（paintOcrDownload） | 同阶段不一致点 |
|---|---|---|---|
| missing 没装 | `#phone-missing` 块显示（`phase === "missing" && !installing`）；标题行 `#btn-phone-component-install`「下载并安装」（failed 后「重新下载」，disabled=busy\|\|installing）；红条 `#phone-component-error`=notes.missing\|\|downloadFailText（条件含 !installing）；cancelled 句在 `#phone-component-state`（条件含 !missingErr）；导入行（failed）；「会装到」`#phone-loc-before`；无 chip；lead 是通用介绍 | `#ocr-missing` 块显示（`phase === "missing" && !installing`）；`#btn-ocr-download`「下载并安装/重新下载」（disabled=busy\|\|installing）；红条 `#ocr-download-error`=OcrPanel.error\|\|failText（installing 时整条清空）；cancelled 句在 `#ocr-note`（条件：无 error 且无 failText）；导入行（failed）；「会装到」；无 chip；lead 说自动登录价值 | ① cancelled 句落点不同：phone 专用元素 #phone-component-state、ocr 用通用 #ocr-note；② 红条来源不同：phone 优先 notes.missing、ocr 优先 OcrPanel.error；③ 红条元素名不同 |
| downloading 下载中 | `#phone-loading` 显示；`#phone-prog-text`「正在下载手机控制组件」；`#phone-prog-num`「x / y MB」；aria-valuenow；fill 宽度；`#btn-phone-component-cancel`「取消下载」（disabled=busy）；install hidden；lead「可以关掉设置继续用…」；「装在」行（#phone-loc-after）收起 | `#ocr-loading` 显示；`#ocr-prog-text`「正在下载验证码识别组件」；`#ocr-prog-num` 同款；cancel「取消下载」（disabled=busy）；download hidden；lead 说自动登录；「装在」行收起 | lead 文案主题不同（预期：两个功能各自的说明）；其余同构 |
| verifying 校验中 | 进度字「下载完成，正在校验组件…」；pct=100；cancel 变「校验中…」且禁用 | 同款（文字、pct、cancel 字面与禁用都一致） | 无 |
| checking 检查中 | `#phone-loading` 显示；进度字「正在检查组件…」；install/cancel hidden；missing hidden；**「开启手机访问」按钮看不到**——它在 `#phone-off` 块里，这一块只在阶段为 off 时显示（#phone-access-detail 也只在 off/on 显示）；start.disabled 里计入 loading 是防御写法，检查中这块本来就收着；无 chip | `#ocr-loading` 显示；进度字「正在检查组件…」；download/enable/reimport/cancel 全 hidden；missing hidden；无 chip | 无——两边进度块都显示、主按钮都收在各自块里（此前此处写「phone 检查中保留可见的禁用主按钮、ocr 直接收起启用」，与代码不符，已删） |
| outdated 需要更新 | install「更新组件」（disabled=busy\|\|installing）；chip「需要更新」（warn）；红条（failed 时）；导入行（failed 时）；lead「主程序已升级…」 | download「更新组件」（disabled=busy\|\|installing）；chip「需要更新」（warn）；红条；导入行；lead 同主题 | 基本对应；红条来源差异同 missing 行①② |
| broken 加载失败 | `#btn-phone-feature-install`「重新导入组件包」（dataset.action="import"）；chip「加载失败」（warn）；说明在 `#phone-feature-error`=notes.feature（由动作写入） | `#btn-ocr-feature-install`「重新导入组件包」；chip「加载失败」（warn）；说明在 `#ocr-download-error`=OcrPanel.error | 说明字的来源不同：phone 走 notes.feature、ocr 走 OcrPanel.error；按钮字面一致 |
| off（phone 已装未开启 / ocr 已装未启用） | `#phone-off` 块（两张通道卡+「开启手机访问」+提示）；chip「未开启」（中性）；lead「选一条通道再开启…」，starting 时「正在开启，先不要切换通道。」 | `#btn-ocr-enable`「启用」；`#ocr-title-chip` 显示＋lead「已装好（版本 x），还没启用。…」 | ① 提示形态不同：phone 用 chip「未开启」、ocr 用 #ocr-title-chip＋lead 文案；② 主按钮字面「开启手机访问」vs「启用」；③ phone 的 off 块还承担通道选择与开启动作，ocr 的 off 只剩启用一步 |
| on（phone 已开启 / ocr 已启用） | `#phone-on` 块（地址、二维码、配对码、复制）；chip linked?「手机已连接」（ok）:「等手机连接」（warn）；`#btn-phone-stop`「关闭手机访问」（stopping 时「关闭中…」，disabled=busy\|\|pending） | chip「已启用」（ok）；lead「版本 x。电脑会自己认验证码…」；enable/download hidden | phone 的 on chip 按连接状态分两档；ocr 固定「已启用」（预期：功能不同） |
| disabled（phone 独有） | `#btn-phone-feature-install`「启用手机控制」（dataset.action="enable"，点击走 enableFeature）；chip「已停用」 | ocrPhase 无此阶段（available 时直接 off） | phone 有「组件在本机但启用位没开」的独立档，ocr 把这种情况并进 off |
| installing（导入安装中，两边都按标志盖住旧态） | installing.phone_control=true：进度字「正在安装组件…」（盖过 checking/verifying/下载字）；#phone-missing hidden；红条不再画（missingErr 带 !installing）；install disabled | installing.relogin_ocr=true：进度字「正在安装组件…」；#ocr-missing hidden；红条显式清空（installing ? "" : …）；download disabled | 进度字与禁用逻辑同构；红条处理 phone 是条件里排除、ocr 是显式清空——写法不同、效果一致（failText 的另一个消费点被取消句的 cancelled 条件兜住，见 uses 表的等价判定） |

**搬家要点**：两段绘制逐阶段同构的部分（进度区三件套、标题行主按钮的三种字面、chip 的
outdated/broken 档）可以抽成一台状态机的两个实例；差异集中在①红条与说明字的来源字段
（notes.missing/notes.feature vs OcrPanel.error）、②cancelled 句的落点、③off 档的提示
形态——搬的时候要显式决定每处用哪一侧的做法，不能两边各留一半。此前要点里写的
「checking 时主按钮的可见性策略」一项删掉：检查中两边的按钮都看不见，不存在要裁决的
不一致。
