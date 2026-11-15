# 设置抽屉的后端补字段：组件等锁时长、读错退回与手机连接状态

- **基线提交**：`3bda03f`（分支 refactor/step1；开工时工作区里另有一处本会话之外的
  AGENTS.md 改动，未触碰）。执行日期：2026-11-15。这批只动后端：规则进 domain，
  组件的新字段在 infrastructure 产生，手机的在 application 产生，`local/app.py`
  只加一行展开；前端一个字没改，这些字段是留给下一批（状态机）用的。
- **加了哪些字段**：
  - 组件状态行（`advanced_features_state` 的每个组件、冻结态）：等组件事务锁时给
    `lock_wait_s`（这一轮连续等锁的秒数，第一次等锁那一拍记起点并报 0，之后逐拍累计；
    读成功或读错即清零重算）与 `check_timed_out`（连续等满 30 秒为真）；读状态出错时给
    `read_error=true`。三个字段只在发生时出现。
  - 手机访问状态（`phone_access_state` 顶层）：`link`（off / waiting / connected /
    disconnected / unknown 五种）与 `last_contact_ago_s`（最近一次来访距今的秒数，
    还没有来访时为 null）。现有字段（`paired_count`、`live_session` 等）一个没动。
- **规则放在哪**：
  - `local/domain/component_rules.py`（新文件）：`COMPONENT_CHECK_TIMEOUT_S = 30` 与
    纯函数 `check_timed_out(wait_s)`（大于等于 30 为真，非数字按假）。
  - `local/domain/phone_rules.py`：`PHONE_IDLE_DISCONNECT_S = 120` 与纯函数
    `phone_link_state(running, has_contacted, last_contact_ago_s, clock_ok=True)`——
    没在跑为 off；时钟不可用为 unknown；本次开启后还没有过来访为 waiting；最近一次
    来访距今小于 120 秒为 connected，达到即为 disconnected。配对过但会话已过期时
    来访时间拿不到，按 disconnected（不是「还没来」，也不是时钟坏了）。
- **为什么用单调时钟**：等锁时长是「已经连续等了多久」，不是业务时刻；单调时钟不受
  改系统时间影响，不会让等待计时跳变。手机来访时间记的是「最近一次来访」这个瞬时值，
  与会话寿命分开算。
- **为什么读错时退回上一次成功的结果**：读组件状态出错（PackageError、OSError、
  ValueError，例如目录换位中断后的恢复路径）不代表组件装坏了，只代表「这一次读不到」；
  冒异常会让整份状态快照失败、界面照旧画。有缓存就退回缓存副本并标 `read_error`，
  一次都没成功过就返回与「等锁且没缓存」同形的包（status 是 checking、available 为假）
  再加 `read_error`——现在的前端会显示「检查中」，不会误画成「没装」。
- **大小约束怎么守住的**：
  - `local/app.py` 仍是 4873 行（大小名单记录值顶格）：只在 `phone_access_state` 的
    返回字典里加一行 `**service.link_status()` 展开，同时把 `live_session` 上面那段
    三行注释压成两行，一加一减正好抵消。
  - `Api.advanced_features_state`（80 行，在函数名单里）没变长：组件的新字段全部在
    `infrastructure/advanced_features.py` 的 `feature_state` / `_frozen_package` 一层
    产生，Api 原样透出。
  - `PhoneAccessService` 没有新开实例属性：来访时间记在会话字典里（`seen_at` 键，
    配对、设备信任恢复、校验通过三处写），文件 486 行（上限 500）。
- **测试怎么写的**：先写用例、在没改的代码上跑红（组件 8 条、规则 11 条、手机 8 条、
  Api 1 条、规则纯函数 4 条，红色输出与本批结果目录的 tests-first-*.txt 对得上），
  再改实现让它们绿。替身补齐：`test_application_services.py` 的 `FakePhoneService`
  加了一个 `link_status()` 方法（按替身自己的 running 返回 off 或 waiting），没有改
  任何现有断言。
- **变异结论表**（执行器 `scripts/mutate_fields.py`，在 mkdtemp 副本里逐条做、各跑
  自己那个测试文件；定位按「文件、函数、那一行的文字」，仓库本体不动）：

| 编号 | 变异 | 变红的用例 | 首条失败断言 |
|---|---|---|---|
| m01 | 组件超时阈值 30 改 31 | test_boundary_is_thirty_seconds_inclusive、test_threshold_is_thirty_seconds | AssertionError: False is not true |
| m02 | check_timed_out 的大于等于改成大于 | test_boundary_is_thirty_seconds_inclusive | AssertionError: False is not true |
| m03 | 读成功后不清等锁起点 | test_successful_read_resets_the_wait_clock | AssertionError: 35 != 0 |
| m04 | 有缓存的等锁分支不带新字段 | test_cached_busy_row_also_carries_the_wait_fields、test_successful_read_resets_the_wait_clock（成功一拍写了缓存，下一拍等锁走的就是缓存分支） | KeyError: 'lock_wait_s' |
| m05 | 去掉读状态的读错捕获 | test_read_error_with_cache_returns_cache_and_read_error、test_read_error_without_cache_reports_checking_and_read_error、test_read_error_clears_and_success_drops_read_error | OSError: disk gone |
| m06 | 读错且没缓存时不带 read_error | test_read_error_without_cache_reports_checking_and_read_error | KeyError: 'read_error' |
| m07 | authenticate 校验通过不写 seen_at | test_a_later_visit_returns_to_connected_with_zero_ago | AssertionError: 'disconnected' != 'connected' |
| m08 | 设备信任恢复建会话不写 seen_at | test_device_restore_counts_as_a_visit | AssertionError: 'disconnected' != 'connected' |
| m09 | 断开阈值 120 的大于等于改成大于 | test_two_idle_minutes_disconnect | AssertionError: 'connected' != 'disconnected' |
| m10 | 时钟坏时不返回 unknown（谎报 off） | test_clock_failure_reads_unknown_instead_of_raising | AssertionError: {'link': 'off', …} != {'link': 'unknown', …} |
| m11 | app.py 去掉那一行展开 | test_phone_access_state_carries_the_link_fields_from_the_service | KeyError: 'link' |

  十一条全部红在预期用例上（执行器退出 0）。每条变异各自的完整输出见执行当次运行，
  表里的用例名与断言原文即其结论。
- **复跑命令**（仓库根；变异只在临时目录的仓库副本里做，仓库本体不动）：

  ```bash
  # 规则、组件、手机与 Api 四组新用例
  python -B -m unittest discover -s local/tests -p test_component_rules.py
  python -B -m unittest discover -s local/tests -p test_phone_rules.py -k PhoneLinkState
  python -B -m unittest discover -s local/tests -p test_advanced_features.py -k FeatureStateWaitFields
  python -B -m unittest discover -s local/tests -p test_phone_service.py -k PhoneLink
  python -B -m unittest discover -s local/tests -p test_application_services.py -k link_fields
  # 十一条变异（全部红在预期用例上退出 0）
  python -B design/evidence/2026-11-15/backend-fields/scripts/mutate_fields.py
  # 大小与分层
  python -B -X utf8 tools/code_shape/check.py
  python -B -m unittest discover -s local/tests -p test_code_shape.py
  python -B -m unittest discover -s local/tests -p test_layer_boundaries.py
  ```
