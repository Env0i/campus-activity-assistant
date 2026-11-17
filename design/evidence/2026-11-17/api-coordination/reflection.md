# 反射调用与越层依赖

- 生成脚本：`scripts/reflect.py`（ast 只读源码，不 import 产品代码）
- 命令：`python -B design/evidence/<日期>/api-coordination/scripts/reflect.py --head 788b25c`
- 基线：`788b25c`；「将来归谁」一栏是手工判断（依据写在脚本 OWNER 的注释），其余列都由 ast 读出

## 一、phone_service 按名字反射调用的 Api 方法

- 注入点：`local/app.py:899` 构造 `PhoneAccessService(api=self, ...)` —— 整个 Api 传进去；`local/application/phone_service.py:463` `getattr(self._api, name, None)` 按名字取方法。
- 动作白名单在 `local/domain/phone_rules.py:155`（`ACTION_PARAMS`，12 个动作）；`dispatch`（phone_service.py:447）先 `normalize_action` 校验参数，再 `_call` 反射。
- `_call` 把参数原样展开成 kwargs：Api 方法的签名就是远程可调用面的一部分，改参数名不会在导入期暴露，只会在手机端变成 `internal`。

| 动作 | 参数白名单 | 实际调的 Api 方法 | 定义行 | 功能 | 将来归谁（手工） |
|---|---|---|---|---|---|
| cancel_start_request | request_id | cancel_start_request | `local/app.py:2750` | 计划 | 计划服务 |
| cancel_task | plan_id、task_id | cancel_task | `local/app.py:3093` | 计划 | 计划服务 |
| check | request_id | check | `local/app.py:2111` | 登录恢复 | 登录恢复服务 |
| list_activities | request_id | list_activities | `local/app.py:2142` | 活动列表 | 活动列表服务 |
| phone_relogin_begin | password、save、username | phone_relogin_begin | `local/app.py:4070` | 登录恢复 | 登录恢复服务 |
| phone_relogin_cancel | flow_id | phone_relogin_cancel | `local/app.py:4107` | 登录恢复 | 登录恢复服务 |
| phone_relogin_submit | challenge_id、code、flow_id | phone_relogin_submit | `local/app.py:4103` | 登录恢复 | 登录恢复服务 |
| save_retry_policy | retry_policy | save_prefs | `local/app.py:4235` | 其他 | 偏好端口（留 Api，不归功能服务） |
| show_window | — | show_window | `local/app.py:3286` | 窗口与托盘 | 窗口与托盘服务 |
| start_plan | headed、items、request_id、retry_policy | start_plan | `local/app.py:2782` | 计划 | 计划服务 |
| start_request_state | request_id | start_request_state | `local/app.py:2713` | 计划 | 计划服务 |
| stop_plan | plan_id | stop_plan | `local/app.py:3101` | 计划 | 计划服务 |

动作名与 Api 方法名不是一一对应，`dispatch` 里有两处服务端改写（`local/application/phone_service.py:455`、`local/application/phone_service.py:459`）：

| 行 | 改写 |
|---|---|
| `455` | 改调 `save_prefs` |
| `459` | 补参数 `source="phone"` |

- 守卫现状：`local/tests/test_phone_service.py` 用假 api 派发校验白名单与参数（459–533 一带），但没有测试盯着「白名单动作 ↔ 真实 Api 方法签名」的对应——把 `start_plan` 的参数改名，测试照样绿，手机端静默变 `internal`。设计稿要补这条守卫。

## 二、advanced_component_service 对 infrastructure 的用法

- 越层点只有一处：`local/application/advanced_component_service.py:29` `from infrastructure import component_packages as _packages`（application 层按 `_ALLOWED_KINDS` 不许 import infrastructure）。
- 用法分三类：构造函数的默认端口（参数为空就退回 `_packages.X`）、静态表 `ARTIFACTS`（拆分资产清单）、常量 `CLOUDFLARED_VERSION`（内置 cloudflared 版本）。

| 行 | 写法 | 类别 | 消法 |
|---|---|---|---|
| `78` | `_packages.version` | 构造默认端口（`version` 为空时退回；当前版本号（找发布资产用）） | app.py 构造时显式传 `version`（与 download/install 同路），删默认值 |
| `81` | `_packages.inspect_archive` | 构造默认端口（`inspect` 为空时退回；单体包体检：清单、签名、feature） | app.py 构造时显式传 `inspect`（与 download/install 同路），删默认值 |
| `82` | `_packages.install` | 构造默认端口（`install` 为空时退回；单体包安装（事务、回滚在 infrastructure）） | app.py 构造时显式传 `install`（与 download/install 同路），删默认值 |
| `83` | `_packages.inspect_artifact` | 构造默认端口（`inspect_artifact` 为空时退回；拆分资产体检） | app.py 构造时显式传 `inspect_artifact`（与 download/install 同路），删默认值 |
| `84` | `_packages.find_cached_artifact` | 构造默认端口（`find_cached_artifact` 为空时退回；查缓存命中） | app.py 构造时显式传 `find_cached_artifact`（与 download/install 同路），删默认值 |
| `85` | `_packages.cache_artifact` | 构造默认端口（`cache_artifact` 为空时退回；把资产放进缓存） | app.py 构造时显式传 `cache_artifact`（与 download/install 同路），删默认值 |
| `86` | `_packages.commit_artifact_group` | 构造默认端口（`commit_artifact_group` 为空时退回；整组原子切换） | app.py 构造时显式传 `commit_artifact_group`（与 download/install 同路），删默认值 |
| `87` | `_packages.feature_status` | 构造默认端口（`status` 为空时退回；组件当前状态） | app.py 构造时显式传 `status`（与 download/install 同路），删默认值 |
| `88` | `_packages.remove` | 构造默认端口（`remover` 为空时退回；卸载组件） | app.py 构造时显式传 `remover`（与 download/install 同路），删默认值 |
| `347` | `_packages.ARTIFACTS` | 静态表：`_run_split_assets` 里 1 处用 | 加构造参数把表传进来 |
| `474` | `_packages.CLOUDFLARED_VERSION` | 常量：组件包内置 cloudflared 版本 | 加构造参数把版本号传进来 |

- 核过的事实：`local/app.py:909-931` 构造两个服务时已显式传 `download`、`asset_resolver`、`install`、`inspect_artifact`、`commit_artifact_group`，没传的正是六个默认端口（version、inspect、find_cached_artifact、cache_artifact、status、remover）；服务内部 8 处调用端口都带 `root=self._root`，所以消掉这条越层不需要改行为。

## 三、test_layer_boundaries 的存量越层例外

- 规则：按模块锁（键是「文件、完整模块名」），同包再加一个模块照样报；每条都要写去处，消掉时从字典里删。

| 文件 | import 的模块 | 登记的去处 |
|---|---|---|
| application/advanced_component_service.py | infrastructure.component_packages | 步骤 2 拆组件服务时消：组件包扫描归 infrastructure，服务经端口拿清单 |
| infrastructure/component_packages.py | runtime_paths | 步骤 2 拆组件服务时消：数据目录改由调用方传进来，不直接取顶层模块 |

- 第二条例外对应 `local/infrastructure/component_packages.py:101`：`_root(root)` 的 `root is None` 分支里延迟 `from runtime_paths import DATA_DIR`。服务侧 8 处都传了 root，这条在「调用方一律传 root」后可消；`_root(None)` 还有没有别的可达调用方，本次没核全，消例外的计划里要按同一口径再核一遍。

## 与 2026-11-12 审计的对照

- X3（phone_service 按名字反射调用 Api 的公开方法）：仍在，注入点与白名单同审计描述；本次补上了「12 个动作、两处改写、无签名守卫」的具体面。
- L1（application/advanced_component_service.py 直接 import infrastructure）：仍在，全仓只此一处（application 与 domain 下 grep 不到第二个）；本次把它拆成 11 个用法点，每个都给了消法。

