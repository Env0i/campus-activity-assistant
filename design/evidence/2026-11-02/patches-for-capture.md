# 为取证临时打过的补丁（2026-11-02）

本目录的截图与观测，有的是在**临时改过的副本**上拍的。这里把每一处改动原始记录清楚，
方便以后判断「截图里的行为和仓库里的代码是否一致」。

这些改动**都没有提交**，也不在共享仓库里；它们只在跑截图的那份工作副本
`<repo>` 中存在过。

## 1. 界面列表在「真有活动」时崩溃（真 bug，改的是生产代码）

### 现象

用真实登录态起图形界面，条款已同意、登录有效，但活动列表一直停在骨架屏，
运行记录给出：

```
[X] 列表请求异常 TypeError: seconds_until() missing 1 required positional argument: 'epoch_of'
```

表现为「列表 0 场、选不中任何活动、开始计划直接提示『还没选活动』」，一次报名请求都不会发出。
列表为空时走不到这段代码，所以早上「学校当前没有返回活动」那批截图没有暴露它。

### 根因

- `local/app.py:575` 定义了二参数包装 `def _seconds_until(ts, now)`，内部再拼上 `school_epoch` 调 `_time_text.seconds_until(ts, now, epoch_of)`。
- `local/app.py:3067`（文件末尾的「兼容包装」区）又写了一行 `_seconds_until = _time_text.seconds_until`，
  在模块导入末尾把上面的包装**覆盖**成三参数原函数。
- `local/app.py:1785` 仍按两参数调用：`it["seconds_to_open"] = _seconds_until(it.get("sign_start"), now)`，
  于是列表里每一场算「距开放秒数」都抛 TypeError。

### 本次改动（仅工作副本）

```diff
--- a/local/app.py
+++ b/local/app.py
@@
-_seconds_until = _time_text.seconds_until
 _task_deadline = _time_text.task_deadline
```

即删掉末尾那行别名，保留 575 行的二参数包装。其余兼容别名（`_task_deadline` / `_kill_tree` /
`_SpawnFailure` / `_ProcessTree`）未动。

### 验证

```bash
cd local
python -c "import time, app; n=time.time(); print(app._seconds_until('2026-11-04 14:00:00', n))"
# 162970（未来时间返回正秒数）、过去时间返回负数、None 返回 None
```

只验证了函数本身可调用；界面在真实活动下的完整流程尚未验证（写这份记录时登录态已失效）。

### 这不是「设计如此」

`app.py:3063` 的注释说明这些旧名字是「保留供测试与内部调用按原名注入、patch」，
`local/tests/test_runtime_bundle.py:252` 用 `mock.patch.object(self.app, "_seconds_until", ...)` 打桩。
删掉别名后该属性依然存在（来自 575 行），打桩不受影响；但**这个判断没有跑测试验证**。

## 2. 演示截图的运行态放慢（只在演示进程内存里，不改文件）

`ui-01..05-*` 是 `--demo` 假数据拍的。演示 runner 每场只睡 0.2 秒，「准备提交」几乎抓不到，
所以在驱动进程里：

- 把 `app.time` 换成 `_Slow(real, 15)`，让 runner 的 `time.sleep` 慢 15 倍，抓完立刻还原；
- 把 `demo-workshop`、`demo-career` 的 `sign_start` 挪到「现在减 60 秒」，让它们当场进入开放态。

两处都只改内存对象，磁盘上的仓库文件没动过。

## 3. 拍法

- 截图用 `PrintWindow(hwnd, hdc, PW_RENDERFULLCONTENT)` 只取窗口像素，再用
  `DWMWA_EXTENDED_FRAME_BOUNDS` 裁掉不可见的缩放边——桌面上其他窗口不会被拍进来。
- 驱动脚本在 `%TEMP%/gui-shots-20261102/`（临时目录，按仓库规范不入库、也不在文档里写死路径）。
