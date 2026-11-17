# 拆 Api 第一步：更新

把「更新」的状态与用例从 `local/app.py` 的 `Api` 搬到 `local/application/update_service.py` 的
`UpdateService`，Api 只留转发。本目录是本轮的证据。

## 搬了什么

| 项 | 搬家前 | 搬家后 |
|---|---|---|
| 状态字段 | `Api._updating`、`_update_request_id`、`_update_result`、`_update_installer`、`_update_installer_path`、`_update_staging_path`、`_update_cancelled` 七个，受 `Api._lock` 保护 | 同名字段在 `UpdateService` 上，受它自己的 `threading.Lock()` 保护 |
| 用例 | `Api.check_update` / `_do_check_update` / `update_download` / `_do_update_download` / `update_cancel` / `update_launch` / `_publish_update` 的方法体 | `UpdateService.start_check` / `start_download` / `download_job` / `cancel` / `launch` / `_launch_switch` / `publish`，加上模块级 `run_check` / `run_download` / `run_version_download` 三个用例函数 |
| Api 侧 | 195 行方法体 + 7 个字段 | `self._updates = UpdateService(emit=..., is_closing=...)` 一处构造，加 7 个短方法（关闭端口、两个线程目标、四个公开入口，共约 63 行）：参数检查已删（格式只在服务里查），端口全部在调用时装配 |
| bootstrap | `with self._lock:` 里逐字段拼 `update_check` 四个键 | `payload["update_check"] = self._updates.snapshot()`（调用时不持 Api 锁，两把锁不嵌套） |
| 测试 | 三个测试文件直接读写 `api._updating` 一类字段 | 改成读写 `api._updates.<同名字段>`；直接调 `_do_check_update` / `_do_update_download` 的用例照旧调 Api 的这两个方法（它们还在，作为线程目标）。逐处对照见 `changed-tests.md` |
| 新增测试 | — | `local/tests/test_update_service.py`：不经 Api，用内存替身端口直测单飞、关闭中拒绝、取消、snapshot 四键、publish 的 `ready_to_restart` 补路径、launch 三条路径 |

`Api` 上的 `_do_check_update` / `_do_update_download` 保留（线程目标就是它们），方法体只剩一次
「取端口 → 调服务」。

## 为什么行为不变

- **状态与锁**：搬家前七个字段由 `Api._lock` 保护；搬家后由服务自己的锁保护。服务的每个入口都是
  「先在本锁内改状态，出锁再做事」：`publish` 写状态后出锁才 `emit`，`start_check` / `start_download`
  出锁才清暂存、起线程，`launch` 出锁才拉安装器。Api 的转发方法进服务之前不持 `_lock`
  （`_update_is_closing` 现在只读一个布尔值、不拿 `Api._lock`，所以服务锁里不会嵌套 Api 锁），两把锁不嵌套、拆开后没有新的锁序，也没有把
  同一个临界区切成两段。
- **事件**：`publish` 仍先落状态再发 `update`；关闭中不发事件但状态留档 —— 与搬家前一致
  （`test_closing_drops_result_event`、`test_closing_drops_event_but_keeps_result` 守着）。
- **请求号**：格式只在服务里检查（`_refuse` 管检查与下载，`launch` 自己一处）。Api 转发前原先的
  检查已删；服务的两处返回值与删掉的那段逐键相同，所以界面看到的结论不变。
- **bootstrap**：四个键（`checking` / `request_id` / `result` / `installer_path`）在服务锁内拼，
  与原来在 Api 锁内拼的是同一份字段。
- **端口在调用时取**：`fetch`、`thread_factory`、`updater.*`、`version_switch_available`、
  `update_version_paths`、`update_launcher_command`、`subprocess.Popen`、`defer_close_action` 全部
  由 Api 的转发方法在调用时读取并传给服务，服务构造时只收 `emit` 与 `is_closing`。测试在构造
  Api 之后打的补丁因此仍然生效（证据见下面「注入点核对」）。
- **对照**：15 个场景、1292 项逐项相同，见 `trace-head-vs-worktree.txt`。

## 补丁落点守卫（P1）

`local/tests/test_api_patch_targets.py` 用 `ast` 静态扫描 `local/tests/**.py` 与 `local/app.py`，
不 import 产品代码。口径：测试里打到 app 模块上的名字必须在 app 里真实存在 —— 认四种写法
`patch.object(<app 别名>, "名字")`、`patch("app.名字")`（含追到模块级字面量列表/循环变量的动态
目标）、`setattr(<app 别名>, "名字", v)`、对 `Api()` 实例变量的属性赋值；被写的名字必须在
`class Api` 里被 `self.X` 读到、或者本身是 Api 的方法。

开工 HEAD 上的输出（`guard-head.txt`）里，冻结存量三条，都不是真缺陷 —— 产品侧分别是
`getattr(self, …)` 与 `self.__dict__.setdefault(…)` 读的，ast 看不见，所以留作存量：

| 测试 | 名字 | 说明 |
|---|---|---|
| `test_application_services.py` | `_endpoint` | `_connect_tailscale` 里走 `getattr` |
| `test_application_services.py` | `_close_approved` | 同上 |
| `test_release_audit.py` | `_canceled_start_ids` | `__dict__.setdefault` 读 |

搬家完成后守卫一度报出 37 条落空（测试还在写 `api._updating` 一类字段），把三个测试文件改到
`api._updates` 上之后归零；冻结清单只增不减的是 0 条。

## 注入点核对（P4）

`scripts/patch_points.py` 列出更新相关测试打的每一个补丁在新代码里的调用点（文件、函数、行号），
再对每个补丁做两条变异，两条都必须让打这个补丁的用例变红。完整输出见 `patch-points.txt`。

| 补丁 | 调用点 |
|---|---|
| `app.check_latest_release` | `local/app.py:2071` `Api._do_check_update` → `fetch=` |
| `app.threading.Thread` | `2065` `Api.check_update` / `2079` `Api.update_download` → `thread_factory=` |
| `app.updater.cleanup_staging` | `2066` `Api.check_update` → `cleanup_staging=` |
| `app.version_switch_available` | `2085` `Api._do_update_download` / `2106` `Api.update_launch` |
| `app.update_version_paths` | `2067` `Api.check_update` / `2086` `Api._do_update_download` / `2107` `Api.update_launch` |
| `app.updater.stage_update` / `download_payload` / `download_installer` / `cleanup_download` | `2086–2090` `Api._do_update_download` → `download_job` 的关键字端口 |
| `app.updater.launch_installer` | `2116` `Api.update_launch` → `LaunchPorts.launch_installer` |
| `app.subprocess.Popen` | `2109` `Api.update_launch` → `LaunchPorts.spawn` |
| `app.defer_close_action` | `2114` `Api.update_launch` → `LaunchPorts.defer_close` |

两条变异只差「替身绑在哪一刻」：

- **A 调用点**：把转发方法传给服务的那个端口换成抛错替身。变红说明补丁确实要经过这个调用点。
- **B 构造时**：同一个抛错替身改成在 Api 构造时绑死（`self._mut_x = _mutant_port(...)`），转发
  方法读 `self._mut_x`。变红说明若端口提前绑死，用例在构造之后打的补丁就再也顶不上去。

用同一个抛错替身而不是「构造时绑真端口」，是为了不真联网、不起进程、不碰磁盘；要证明的事一样成立：
基线（什么都不改时这 12 个用例全绿）说明补丁被认、端口读的是调用时的名字；A 全红说明补丁经过
调用点；B 全红说明端口不能提前绑。三条合起来就是「端口必须在调用时取」。

结果：**12 个补丁 × 2 条变异 = 24 条，全部让对应用例变红**；跑完 `app.py` 的 SHA-256 与改前一致
（变异在副本上做，工作区不留改动）。

## 不变区对照（P6）

`scripts/update_trace.py` 用同一组替身端口（检查、下载、落盘、启动、版本路径、线程、推迟关窗）
依次驱动 15 个场景：检查更新（有新版、已是最新、抛错、请求号不合法、关闭中、在途时再点）、下载
（成功、取消、下载失败、版本目录包、版本目录包失败回退安装器）、启动（安装器、版本目录切换、
没有已校验产物）。每步记 Api 方法的返回值、推出去的事件（名与载荷）、bootstrap 的 `update_check`。

开工 HEAD（`local/` 与 `VERSION` 经 `git archive` 取出）对当前工作区：

```
比了 1292 项，相同 1292 项，不同 0 项
```

## 测试

- `test_api_patch_targets`：4 项，全过（守卫在 HEAD 上与改完后都过）
- `test_update_service`：14 项，全过
- `test_update_check`：68 项，全过
- `test_application_services`：162 项，全过
- `test_runtime_bundle`：85 项，全过
- 分层与代码形状：`test_layer_boundaries` 19 项、`test_code_shape` 15 项，全过；
  `tools/code_shape/check.py` 通过（`local/application/update_service.py` 恰好 500 行，上限 500）
- 名单只改小、只删项：`local/app.py` 4873 → 4740、`Api.__init__` 167 → 164、`class Api` 属性
  23 → 20（去掉 `_updating` / `_update_request_id` / `_update_cancelled`）、`Api.update_launch`
  73 → 21 行故删项
- 本机版全量：3055 项、364.6 秒，1 失败 5 跳过。唯一那条失败是
  `test_phone_http.RejectionTests.test_cookies_after_stop_are_rejected`（拿到 502，期望 0/401/403），
  在开工 HEAD 副本上单独跑同样失败，属环境（出口代理）而不是本轮改动引入，见
  `local-full-preexisting.txt` —— 没有新增失败。

**mypy 没装**：本机没有 `mypy`，静态类型检查这一项没跑，`from __future__ import annotations` 与
注解只作为阅读信息，不当作已校验的类型契约。

## 预计与实际时长

| 段 | 预计 | 实际 |
|---|---|---|
| 补丁落点守卫与清点 | 约 1 小时 | 约 12 分钟 |
| 搬家（UpdateService）与改测试 | 约 1.5 小时 | 约 20 分钟（含最后压到 500 行的几轮） |
| 注入点变异与不变区对照 | 约 0.5 小时 | 约 8 分钟 |
| 本机版全量 | 约 10 分钟 | 约 6 分钟 |
| **合计** | **约 3 小时 10 分** | **约 41 分钟**（15:00 开工，15:41 收工） |

## 复跑命令

都在仓库根执行，`python` 用装了 `pywebview` 的解释器（本机是 3.12）。

```
python -B -m unittest discover -s local/tests -p test_api_patch_targets.py
python -B -m unittest discover -s local/tests -p test_update_service.py
python -B -m unittest discover -s local/tests -p test_update_check.py
python -B -m unittest discover -s local/tests -p test_application_services.py
python -B -m unittest discover -s local/tests -p test_runtime_bundle.py
python -B -m unittest discover -s local/tests -p test_layer_boundaries.py
python -B -m unittest discover -s local/tests -p test_code_shape.py
python -B tools/code_shape/check.py
python -B design/evidence/2026-11-17/api-update/scripts/patch_points.py --list
python -B design/evidence/2026-11-17/api-update/scripts/patch_points.py --out patch-points.txt
python -B design/evidence/2026-11-17/api-update/scripts/update_trace.py --repo . --out work.json
python -B design/evidence/2026-11-17/api-update/scripts/update_trace.py --compare head.json work.json
```

对照组（HEAD）这样取：

```
git archive HEAD local VERSION | tar -x -C <空目录>
python -B design/evidence/2026-11-17/api-update/scripts/update_trace.py --repo <空目录> --out head.json
```
