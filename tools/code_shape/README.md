# 代码形状守卫

分层与大小两类守卫，供 `local/tests/` 里的契约测试和命令行共用。所有量法都照
`design/evidence/2026-11-12/refactor-audit/README.md` 的 C1③、C1④、C2，脚本从审计目录搬来时
只做函数拆分，不改量法（等价性证明见搬入当批的结果目录）。

## 两条分层规则

1. **后端**（`local/domain`、`local/application`、`local/infrastructure`）
   - `domain` 只许 import 标准库与 `domain`；`application` 只许 import 标准库、`domain`、`application`；
     这两层 import 第三方包也算越界。
   - `infrastructure` 是接第三方包的适配器层：除标准库、`domain`、`infrastructure` 外，允许 import 第三方包。
   - 三个内层包都不许 import `local/` 根目录下的顶层模块（`runtime_paths`、`app` 之类）；标准库以 `sys.stdlib_module_names` 判定。
   - `import a, b` 的每个 alias 都判；`from 包 import 名`、`from local import 名`、`import local.名` 都先解析成完整模块名再判；
     相对 import 按 level 解析到实际的包（level 1 是同包，不算越界）；函数体里的延迟 import 也算。
   - 存量例外写在 `local/tests/test_layer_boundaries.py` 的 `LEGACY_DIRECTION_VIOLATIONS`，
     键是「文件、完整模块名」，按模块锁、不按包锁；每条带理由与去向。
2. **前端**（`local/ui`，按 `index.html` 的加载顺序；`led.js` 会被加载，和 `app.js` 同算根层；不含手机页 `m/`；过渡期模块与普通脚本并存，清单口径与模块专守见下面「模块图守卫」一节）
   - `state/` 不引用 `views/`、`controllers/`、`app.js` 定义的顶层名字；
   - `views/` 不引用 `controllers/`、`app.js` 定义的顶层名字；
   - 「引用」按名字匹配：属性访问、对象字面量的键、注释与字符串里的不算，本文件有同名局部声明的不算。
   - 存量例外记在 `ui_layer_allow.json`，分 `state` 与 `views` 两组，键与名字都排序。
   - 白名单按「文件 × 名字」计，只约束名字集合，不约束同一名字在同一文件里的引用次数（次数会随改写抖动）。

**消掉白名单里的一项**：把定义搬到正确的层，或让下层只交出状态、由视图订阅重画。
不许把上层函数当参数或回调塞进下层——那样名字不在调用点，守卫看不见，但依赖是真实的。

两组名单都**只减不增**：代码里多出名单外的一项就红；名单里的项在代码里没有了也红，提示把它删掉。

## 模块图守卫（ESM 过渡期）

界面正在从「按顺序加载的普通脚本」迁到 ES Modules（目标目录见
`design/proposals/engineering-refactor.md` 的「前端目标目录」一节）。过渡期普通脚本先跑、
模块后跑，这里的清单口径是：`index.html` 的普通脚本按加载序在前，模块入口 `main.js` 的
整张引用图随后、被引用的在前；模块只允许「import { 名字 } from 相对路径;」的单行具名
导入与 export 声明 / export { 列表 }，别的写法直接报错。`ui_refs.mjs` 按这个清单清点
跨层引用（认层：普通脚本按目录，模块按文件名规则——`state-`/`view-`/`actions-` 开头
分属状态/视图/编排，`shared/` 下是公共层，入口 `main.js` 与过渡名单 `legacy-globals.js`
不限——并进现有四档词表）；`local/tests/fixtures/ui_harness.py` 是同一口径的另两份
实现（Python 拼接一份、node 沙箱一份），两边各有测试守着。

`ui_modules.mjs` 只读地输出模块报告：模块清单与各自的层、每个模块引入了哪些名字、
顶层循环引用、「用了别的模块定义的名字却没有 import」、违反层规则的引用、「模块直接
用到的普通脚本全局名字」（入口 `main.js` 不进这份清单——它是过渡期的桥，对普通脚本
全局名字的引用就是迁移机制本身，全部迁完时随它一起消失）、`legacy-globals.js` 挂回
window 的名字、挂出去却没有任何普通脚本在用的名字（有就必须删）。

`unattached_module_names` 量的是「搬进模块却没挂回」：普通脚本引用了一个名字，这个名字
的顶层定义只在模块里（没有任何普通脚本定义同名），而它不在 `legacy-globals.js` 挂回
window 的名单里。每项给出 file、name、line、defined_in。拼接式测试发现不了这类缺陷——
拼接以后模块里的名字恰好进了全局作用域，调用照常返回；真加载下模块名不进全局，普通
脚本一调用就是 ReferenceError，要等用户在真窗口点到那里才坏。

```bash
node tools/code_shape/ui_modules.mjs                                      # 只读报告
node tools/code_shape/ui_modules.mjs --expect > tools/code_shape/ui_modules_expect.json
```

期望值由 `--expect` 生成，不手写；`local/tests/test_ui_modules.py` 比对：五类问题
（顶层循环、缺 import、普通脚本引用了没挂回的模块名字、违反层规则、挂出去没人用）
必须为空，「模块用到的普通脚本全局
名字」与「挂回名单」两份清单与实际逐项相等，多一项少一项都红。「模块用到的普通脚本
全局名字」就是过渡期的迁移清单：迁完一块少几个名字，全部迁完时应当为空。

## 四条大小规则

| 对象 | 上限 | 进名单的阈值 |
|---|---|---|
| 产品文件 | 500 行 | >800 行进名单甲，501–800 行进名单乙 |
| 产品函数 | 60 行 | >100 行进名单甲，61–100 行进名单乙 |
| `test_` 函数 | 60 行 | 超过即进测试函数名单 |
| 类里多处赋值的实例属性 | 5 个 | 超过即进类名单 |

- 量法：物理行；Python 函数从 `def` 行到最后一行，不含装饰器；嵌套函数单独算一条，也计入外层；JS 表达式体的箭头函数不计。
- 只算同时在不少于 3 个方法里赋值的 `self.x`（`=`、`+=`、带注解赋值；容器内修改不算），这样的属性超过 5 个才判类超限。
- 产品代码指 `local/`、`server/`、`tools/` 下受版本管理的 `.py`、`.js`、`.mjs`，去掉测试。
- 名单甲与类名单每项带一句理由（去处或排期），名单乙与测试函数名单不带理由。
- 键是「路径::限定名」，不含行号；同一文件里限定名重复时按出现顺序加 `#2`、`#3`。
- 名单里的项不得超过记录值，变短放行。
- 新写的工具与测试自己也要守这四条上限：本目录的代码文件（`.py`/`.js`/`.mjs`）没有超过 500 行的，函数也没有超过 60 行的；`baseline.json` 这类数据文件不在此列。

## 三份名单与三个命令

`baseline.json` 存四份名单（文件甲乙、函数甲乙、测试函数、类）。它只由命令行显式维护，测试从不改写它。

```bash
python -B -X utf8 tools/code_shape/check.py            # 只读比对，有违规非零退出
python -B -X utf8 tools/code_shape/check.py --json     # 机器可读结果，给测试用
python -B -X utf8 tools/code_shape/check.py --tighten  # 收紧记录值、删掉已不超限的项
python -B -X utf8 tools/code_shape/check.py --init     # 只在 baseline.json 不存在时可用
```

`--tighten` 拒绝任何变长或新增；记录值变小后写回，已不超限的项直接从名单删掉。
从甲档缩到乙档（文件 850→700、函数 150→90）只是换档，不算新增，照样允许。
没有 node、或 `jsfuncs.mjs` 执行失败时，`--tighten` 与 `--init` 直接非零退出并说明原因，
不写 `baseline.json`（否则会把 JS 名单整段删掉或生成空名单）；只读比对与 `--json` 照旧跳过 JS 并说明。

## 文件

- `jslex.mjs`：JS 词法（token 化），搬自审计目录，拆成不超过 60 行的若干函数。
- `jsscan.mjs`：从 token 找函数声明与函数体范围，同样拆开。
- `jsfuncs.mjs`：输出函数表 JSON（文件、限定名、起始行、行数），供 `check.py` 与等价性核对使用。
- `ui_refs.mjs`：只读清点前端跨层引用，输出 JSON；页面脚本清单（普通脚本加模块图）与 import 解析也从这里导出，`ui_modules.mjs` 复用。
- `ui_modules.mjs`：模块图守卫，只读报告与期望值生成。
- `ui_modules_expect.json`：`ui_modules.mjs --expect` 生成的期望值，不手写。
- `ui_layer_allow.json`：前端分层的存量白名单。
- `check.py`：大小守卫命令行。
- `baseline.json`：大小名单。

## 已知限制

名单的键靠出现顺序：JS 匿名函数的键是「文件内第几个匿名函数」，Python 里同名函数的键按出现顺序加 `#2`、`#3`。
在它们前面插入同类函数会让后面的键错位：守卫会把错位后的大函数报成新超限，`--tighten` 也会拒绝。
遇到时停下来问用户，经用户同意后只改 `baseline.json` 里的键名，不改记录值。

没有 node 时，JS 函数行数与前端分层两类检查跳过并在输出里说明；Python 部分照常查。
