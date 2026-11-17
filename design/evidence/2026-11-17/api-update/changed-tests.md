# 测试跟着搬：读写七个更新字段的逐处对照

只改一类东西：原来写在 `api` 上、现在写在 `api._updates`（`UpdateService` 实例）上的字段。
字段名、输入值、断言值一律不变。三个文件之外一个字没改；断言、skip、测试路径都没动。

`api._emit` 不在此列：它是 Api 的方法，搬到服务后由服务在调用时读 `self._emit`，
测试里 `self.api._emit = Mock()` 照旧生效（补丁落点守卫也在盯这一点）。

## local/tests/test_update_check.py

| 原行 | 原写法 | 新写法 |
|---|---|---|
| 521 | `self.api._updating = True` | `self.api._updates._updating = True` |
| 522 | `self.api._update_request_id = "request"` | `self.api._updates._update_request_id = "request"` |
| 526 | `assertFalse(self.api._updating)` | `assertFalse(self.api._updates._updating)` |
| 527 | `self.api._update_result["request_id"]` | `self.api._updates._update_result["request_id"]` |
| 528 | `_emit.assert_called_once_with("update", self.api._update_result)` | 同上字段改读 `self.api._updates._update_result` |
| 531 | `self.api._updating = True` | `self.api._updates._updating = True` |
| 532 | `self.api._update_request_id = "request"` | `self.api._updates._update_request_id = "request"` |
| 533 | `self.api._update_installer_path = .../stale.exe` | `self.api._updates._update_installer_path = .../stale.exe` |
| 539 | `assertEqual(self.api._update_installer["name"], INSTALLER)` | 读 `self.api._updates._update_installer` |
| 540 | `assertEqual(self.api._update_installer_path, "")` | 读 `self.api._updates._update_installer_path` |
| 544 | `self.api._update_staging_path = stale` | `self.api._updates._update_staging_path = stale` |
| 551 | `assertEqual(self.api._update_staging_path, "")` | 读 `self.api._updates._update_staging_path` |
| 556 | `self.api._updating = True` | `self.api._updates._updating = True` |
| 559 | `assertFalse(self.api._updating)` | 读 `self.api._updates._updating` |
| 560 | `self.api._update_result["state"]` | 读 `self.api._updates._update_result` |
| 567 | `assertFalse(self.api._updating)` | 读 `self.api._updates._updating` |
| 585 | `assertFalse(self.api._updating)` | 读 `self.api._updates._updating` |
| 588 | `self.api._update_installer = None` | `self.api._updates._update_installer = None` |
| 596 | `self.api._update_installer = installer` | `self.api._updates._update_installer = installer` |
| 603 | `self.api._updating = False` | `self.api._updates._updating = False` |
| 608 | `assertFalse(self.api._updating)` | 读 `self.api._updates._updating` |
| 613 | `self.api._update_installer = installer` | `self.api._updates._update_installer = installer` |
| 614 | `self.api._update_request_id = "dl-1"` | `self.api._updates._update_request_id = "dl-1"` |
| 615 | `self.api._update_result = {...}` | `self.api._updates._update_result = {...}` |
| 625 | `assertFalse(self.api._updating)` | 读 `self.api._updates._updating` |
| 626 | `self.api._update_result["state"]` | 读 `self.api._updates._update_result` |
| 627 | `self.api._update_installer_path.endswith(INSTALLER)` | 读 `self.api._updates._update_installer_path` |
| 642 / 643 | `self.api._update_installer = installer` / `_update_result = {...}` | 同一处改到 `self.api._updates` |
| 653 | `self.api._update_result["state"]` | 读 `self.api._updates._update_result` |
| 666 / 667 | `_update_installer` / `_update_result` 赋值 | 同一处改到 `self.api._updates` |
| 679 / 680 | `_update_result` / `_update_installer_path` 读取 | 同一处改到 `self.api._updates` |
| 686 | `self.api._update_installer = installer` | `self.api._updates._update_installer = installer` |
| 690–693 | `_updating` / `_update_result` / `_update_installer_path` 读取 | 同一处改到 `self.api._updates` |
| 698 | `self.api._update_installer = installer` | `self.api._updates._update_installer = installer` |
| 702 / 703 | `_update_result` 读取 | 读 `self.api._updates._update_result` |
| 706 / 708 | `assertFalse/True(self.api._update_cancelled)` | 读 `self.api._updates._update_cancelled` |
| 718–720 | `_update_installer`、`_update_installer_path`、`_update_result` 赋值 | 同一处改到 `self.api._updates` |
| 723 | `return_value={"ok": True, "path": self.api._update_installer_path}` | `self.api._updates._update_installer_path` |
| 731 | `self.api._update_installer_path = ...` | `self.api._updates._update_installer_path = ...` |
| 736 / 737 | `_update_result` 读取 | 读 `self.api._updates._update_result` |

调用 `self.api._do_check_update(...)`、`self.api._do_update_download(...)` 的用例**一个字不改**：
这两个方法留在 Api 上作一行转发（线程目标就是它们），端口在那一层取。见结果文件的 amendment。

## local/tests/test_application_services.py

`FakeState`（第 33–47 行）是 UpdateState 协议的替身，不是 Api，字段一字不改；
只按新协议补一个 `is_closing()`（原来 `state._closing` 由用例函数直接读，现在改调端口）。

| 原行 | 原写法 | 新写法 |
|---|---|---|
| 2580 | `api._update_result = {...}` | `api._updates._update_result = {...}` |
| 2582 | `api._update_staging_path = "D:/versions/.staging-rid-update"` | `api._updates._update_staging_path = ...` |
| 2732 | `api._update_installer = installer` | `api._updates._update_installer = installer` |
| 2733 | `api._update_result = {...}` | `api._updates._update_result = {...}` |
| 2754 | `assertEqual(api._update_result["state"], "ready_to_install")` | 读 `api._updates._update_result` |
| 2952 | `self.api._update_staging_path = staging` | `self.api._updates._update_staging_path = staging` |
| 2953 | `self.api._update_result = {...}` | `self.api._updates._update_result = {...}` |
| 2960 | `assertEqual(self.api._update_staging_path, staging)` | 读 `self.api._updates._update_staging_path` |
| 2963 | `assertFalse(self.api._updating)` | 读 `self.api._updates._updating` |

第 39–43、62–86、2854 行的 `state._*` 都属于 `FakeState`，不动。

## local/tests/test_runtime_bundle.py

| 原行 | 原写法 | 新写法 |
|---|---|---|
| 1856 | `api._update_result = {...}` | `api._updates._update_result = {...}` |
| 1858 | `api._update_staging_path = ...` | `api._updates._update_staging_path = ...` |
| 1891 / 1892 | 同上两行 | 同一处改到 `api._updates` |
| 1898 | `assertEqual(api._update_result["state"], "ready_to_restart")` | 读 `api._updates._update_result` |
| 1905 / 1906 | 同上两行 | 同一处改到 `api._updates` |
| 1920 / 1922 | 同上两行 | 同一处改到 `api._updates` |

## 值不变的核对

- 所有赋值右边的字典/字符串（`{"state": "ready_to_restart", ...}`、`"D:/versions/.staging-rid-update"`、
  `str(Path(tempfile.gettempdir()) / ...)`）逐字保留。
- 所有断言的期望值逐字保留，只把左边的读取路径改到服务上。
- 改完以后 `test_api_patch_targets` 必须重新变绿（没有写到 Api 上却没人读的字段）。
