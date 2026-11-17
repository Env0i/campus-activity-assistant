# 拆 Api 前的协调清点：README

## 口径

- **只读**：三个脚本全部 ast 解析源码，不 import、不运行 `local/app.py` 与 `local/application`
  下的任何模块；手工表（busy.md、closing.md）逐函数读源码整理，判断依据写在文内。
- **基线**：开工 HEAD `788b25c`（分支 `refactor/step1`）。2026-11-12 审计的行号基于
  `7e2d31c`，本批一律重量，不照抄旧行号。
- **环境**：控制台不是 UTF-8 时跑脚本前设 `PYTHONIOENCODING=utf-8`；Python 带 `-B`。
- **范围**：`local/app.py` 与 `local/application` 下 9 个模块（update_service、
  advanced_component_service、phone_service、login_relay_service、auto_relogin、
  plan_service 等）加 `local/domain/phone_rules.py` 与 `local/tests/*.py`（只读触点）。

## 产出与条目数

| 文件 | 生成方式 | 条目数 |
|---|---|---|
| `locks.md` | `lock_graph.py` 生成 | 12 把锁；`Api._lock` 96 处 `with` / 64 个方法；先后表 14 条边（无 A→B 与 B→A 并存）；RLock 重入 3 处；认不出的 `with` 0 处 |
| `fields.md` | `field_map.py` 生成 | Api 实例属性 59 个（3 把锁另见 locks.md）：单功能 2 个、跨功能 23 个；另有只读引用与动态访问两节 |
| `busy.md` | 手工（依据文内） | 判断 G1–G14；「谁挡谁」矩阵 14 行 × 9 列；读出来的事 7 条 |
| `closing.md` | 手工（依据文内） | `_closing` 2 处赋值、28 处读（9 个功能）；锁外读 4 处；shutdown 7 步先后表 |
| `demo.md` | `field_map.py` 生成 | DEMO 读点 22 个函数、31 处；测试打补丁 27 处；伪模块注入 2 处 |
| `reflection.md` | `reflect.py` 生成 | 12 个动作 → 12 个 Api 方法（含 2 处 dispatch 改写）；组件服务越层用法 11 个点；test_layer_boundaries 存量例外 2 条 |
| `tests.md` | `field_map.py` 生成 | 测试触点 1259 处 / 21 个文件；按 9 个功能 + 跨功能分档给出改造预算 |
| `design.md` | 手工（设计稿，proposed） | 七个问题各一节 + 决定↔事实对照表 + 待拍板 3 条 |

脚本行数（上限 500）：`lock_graph.py` 500、`field_map.py` 416、`reflect.py` 254。

## 复跑命令

```bash
PYTHONIOENCODING=utf-8 python -B design/evidence/2026-11-17/api-coordination/scripts/lock_graph.py \
  --head 788b25c --out-dir design/evidence/2026-11-17/api-coordination
PYTHONIOENCODING=utf-8 python -B design/evidence/2026-11-17/api-coordination/scripts/field_map.py \
  --head 788b25c --out-dir design/evidence/2026-11-17/api-coordination
PYTHONIOENCODING=utf-8 python -B design/evidence/2026-11-17/api-coordination/scripts/reflect.py \
  --head 788b25c --out-dir design/evidence/2026-11-17/api-coordination
```

三条都在仓库根跑，覆盖写回同名文件；在干净工作区（HEAD 仍是 `788b25c`）重跑得到同样的表。

## 与 2026-11-12 审计的对照（审计基线 `7e2d31c`）

| 审计数字 | 本次 | 变没变、为什么 |
|---|---|---|
| `Api._lock` 被 67 个方法读 | 64 个方法 | 变小。同口径（按 `with self._lock` 逐函数数）基线 66 个方法 / 98 处，少的 5 个方法 7 处是拆更新块走的：`check_update`（2）、`_publish_update`（1）、`update_download`（2）、`update_cancel`（1）、`update_launch`（1）。审计的 67 与本表 64 还有 1 的口径差（本表把别名锁、`run_plan_task(lock=...)` 的参数锁也计入：64 = 61 + 别名/参数路径）。 |
| `with self._lock` 98 次 | 96 处 | 同上：grep 口径 98 → 91，全口径（含别名与参数锁）91 → 96。 |
| `_credential_lock` 12 个方法 | 12 个方法、12 处 | 不变。 |
| `_phone_access_lock` 9 个方法 | 9 个方法、9 处 | 不变（其中 5 处是与 `_credential_lock` 的联合 `with`）。 |
| 23 个标志在三个以上方法里赋值 | 跨功能字段 23 个 | 数字相同、口径不同：审计按「≥3 个方法里赋值」，本表按「≥2 个功能读写」（fields.md 两张表）。两个 23 是巧合，集合未必重合；本表口径更适合「字段跟服务走」的决策。 |
| DEMO 被 22 个函数读 | 22 个函数、31 处 | 不变。 |
| 测试给 DEMO 打补丁 24 次 | 27 处 | 多 3：口径差 2（`for patch in (mock.patch.object(...),)` 的元组写法，审计只数了直接出现的行）+ 基线后新增 1（`test_relogin_busy_order.py`，`b4afa7b` 引入）。按本脚本口径基线是 26。详见 demo.md 对照节。 |
| `_closing` 2 处赋值 30 处读 | 2 处赋值、28 处读 | 变小。少的 3 处读随更新块搬进 `UpdateService`，新增 1 个唯一对外入口 `Api._update_is_closing`；逐条写法对照见 closing.md 第五节。 |

**工具本身的口径修正（要交代）**：`field_map.py` 首版对测试触点只认出 1018 处——它漏认了
`mock.patch.object(...)` 的 `mock.` 前缀与 `self.app`/`self.local_app` 基座两种写法
（打在 app 模块上的补丁几乎全是这两种形态）。修正后 1259 处；DEMO 补丁从 0 处修正为 27 处。
audit 数字对照以修正后的口径为准。

## 手工表的自证

- `busy.md` 的 G1–G14 每行都写「位置（函数名 + 行号区间）、读了什么、持锁、谁在调」；
  矩阵每个非空格子都能回溯到某个 G 编号，`—` 表示读过源码确认不挡。
- `closing.md` 的数字与 `fields.md` 的 `_closing` 一节互核过（读写次数、锁外 4 处一致）；
  同名坑（`main()` 里 4699 行的局部函数 `_closing()`）已排除。
- `design.md` 是判断稿，每条决定括注依据表与条目；它不改代码，落地前每块另立计划。
