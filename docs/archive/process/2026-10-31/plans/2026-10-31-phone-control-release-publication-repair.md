# Phone Control Release Publication Repair Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复手机控制组件 ZIP 已生成并校验、却没有进入最终 GitHub Release 上传清单的问题，确保用户的一键安装能真正拿到 `phone_control` 组件。

**Architecture:** 保留现有 `verify_release_assets()`、组件包 manifest 校验和 `update_check.resolve_phone_control_asset()` 不变。只把已核验的 `component` 资产纳入发布阶段的指纹复核和 `publish()` 上传列表，并用发布生命周期测试锁住这两个契约。

**Tech Stack:** Python 3.10+、`unittest`、现有 `tools/release.py` GitHub CLI 发布封装。

## Global Constraints

- 不改变手机控制、Tailscale、Cloudflare、组件下载或学校接口行为。
- 不新增依赖，不修改 `local/update_check.py` 的下载协议。
- 不在自动执行中创建 tag、上传 Release 或覆盖已有 Release；真实发布必须停在用户确认门禁。
- 保留当前工作区的其他 WIP，不清理、不回滚、不执行 `git add -A`。
- 本返修只允许修改本计划列出的文件；不提交 Git。
- 组件资产的最终文件名必须继续由 `component_asset_name(version)` 产生：
  `campus-activity-watch-phone-control-v<version>-win-x64.zip`。

---

### Task 1: 把组件资产纳入发布指纹和上传清单

**Files:**
- Modify: `tools/release.py:774-819`
- Test: `local/tests/test_lifecycle_release.py`（`ConfirmedSourceRecheckTests`）

**Interfaces:**
- `asset_digest(assets: dict) -> dict` 必须返回 `zip`、`exe`、`installer`、`component`、`manifest` 五个资产的 SHA-256。
- `do_publish()` 调用 `publish()` 时，上传列表必须包含 `assets["component"]`，并且组件 ZIP 仍在 `manifest` 之后或之前保持稳定顺序。
- `verify_release_assets()` 继续负责组件存在、大小、哈希和组件内部 manifest 校验；本任务不重复实现这些校验。

- [ ] **Step 1: 写能暴露遗漏的回归测试**

在 `ConfirmedSourceRecheckTests` 中增加以下两个测试。第一个锁住指纹集合，第二个捕获真正传给发布器的文件列表：

```python
def test_asset_digest_includes_phone_component(self):
    import tempfile
    with tempfile.TemporaryDirectory() as name:
        stage, exe, zip_path, manifest = self._candidate(name)
        installer = stage / self.rel.installer_asset_name(self.VERSION)
        component = stage / self.rel.component_asset_name(self.VERSION)
        assets = {
            "zip": zip_path,
            "exe": exe,
            "installer": installer,
            "component": component,
            "manifest": manifest,
        }
        digest = self.rel.asset_digest(assets)
        self.assertEqual(
            set(digest), {"zip", "exe", "installer", "component", "manifest"}
        )
        self.assertEqual(digest["component"], self.rel.sha256_of(component))

def test_publish_uploads_phone_component_asset(self):
    import tempfile
    with tempfile.TemporaryDirectory() as name:
        captured = []
        stage, _exe, _zip_path, _manifest = self._candidate(name)
        patches = [
            mock.patch.object(self.rel, "DIST", Path(name)),
            mock.patch.object(self.rel, "git_state", lambda: self._state()),
            mock.patch.object(self.rel, "source_commit", lambda: "f" * 40),
            mock.patch.object(self.rel, "confirm_publish", lambda *args: None),
            mock.patch.object(self.rel, "ensure_tag", lambda *args, **kwargs: None),
            mock.patch.object(
                self.rel,
                "publish",
                lambda tag, assets, clobber=False: captured.extend(assets),
            ),
        ]
        for patch in patches:
            patch.start()
        try:
            self.rel.do_publish(self.rel.tag_of(self.VERSION), True, self.VERSION)
        finally:
            mock.patch.stopall()

        names = [Path(path).name for path in captured]
        self.assertIn(self.rel.component_asset_name(self.VERSION), names)
        self.assertEqual(len(names), 5)
```

- [ ] **Step 2: 运行定向测试确认当前代码先失败**

运行：

```text
python -X utf8 -m unittest local.tests.test_lifecycle_release.ConfirmedSourceRecheckTests
```

预期：新增的指纹测试因 `asset_digest()` 只返回四项而失败，上传测试因 `publish()` 参数列表缺少组件 ZIP 而失败；不得通过删除断言或把组件改成可选来绕过失败。

- [ ] **Step 3: 做最小实现**

在 `tools/release.py` 中完成两处同步修改，并更新函数说明：

```python
def asset_digest(assets: dict) -> dict:
    """候选资产指纹：主程序、安装器、手机组件和 manifest 全部纳入复核。"""
    return {
        key: sha256_of(assets[key])
        for key in ("zip", "exe", "installer", "component", "manifest")
    }
```

把 `do_publish()` 的最终上传调用改为：

```python
publish(
    tag,
    [
        assets["zip"],
        assets["exe"],
        assets["installer"],
        assets["component"],
        assets["manifest"],
    ],
    clobber,
)
```

同时把 `do_publish()` 的资产说明从“四项”改成“主程序、安装器、手机组件、manifest 五项”，避免代码和门禁文案再次分叉。不要修改 `verify_release_assets()` 的组件校验逻辑，也不要让 `--without-component` 绕过发布门禁。

- [ ] **Step 4: 运行发布生命周期测试确认修复**

运行：

```text
python -X utf8 -m unittest local.tests.test_lifecycle_release
```

预期：该模块 exit 0；新增测试确认组件 ZIP 出现在上传参数和资产指纹中，既有 tag、来源、资产替换门禁继续通过。

---

### Task 2: 把“真实 Release 组件资产”加入验收门禁

**Files:**
- Modify: `design/evidence/2026-10-31/phone-access-channel-redesign-acceptance.md`

**Interfaces:**
- 记录必须把“本地 prepare 已生成”与“GitHub Release 已上传且应用能解析”分开。
- 在真实发布完成前，手机真机验收仍保持 `pending_user_review`；不能用 1447 个本地测试替代 Release 资产验收。

- [ ] **Step 1: 增加发布资产验收小节**

在现有真机步骤前增加“组件 Release 资产”小节，逐项保留未执行状态，至少包括：

1. `tools/release.py --prepare` 产物目录同时存在主程序资产、`manifest.json` 和 `campus-activity-watch-phone-control-v<version>-win-x64.zip`。
2. `manifest.json` 的 `files` 中有该组件资产，且记录的字节数和 SHA-256 与 ZIP 一致。
3. 用户确认并完成正式发布后，GitHub Release 的资产列表确实包含该组件 ZIP；不能只看发布器的“校验通过”输出。
4. 应用主动读取该 Release 时，`select_release_assets()` 选中组件，`resolve_phone_control_asset()` 返回 `state=available`；缺失组件时仍返回 `no_component`。
5. 真实设备点击“下载并安装组件包”后进入校验并安装，不能落到“这个版本没有发布手机控制组件”。

- [ ] **Step 2: 更新缺陷记录和停点**

在证据文档中记录本返修前的根因：`verify_release_assets()` 已核验组件，但 `asset_digest()` 和 `publish()` 的最终资产列表漏传 `component`，所以发布前门禁不能证明组件已上传。记录返修后必须重新执行 Task 1 测试，并由用户在真实 Release 上确认资产存在；在此之前不把 Cloudflare 或手机安装流程标记为已验收。

---

### Task 3: 回归验证并停在真实发布/真机用户门禁

**Files:**
- No additional source files.

- [ ] **Step 1: 运行本轮定向与静态检查**

在获得本轮测试授权后运行：

```text
python -X utf8 -m unittest local.tests.test_lifecycle_release
python -X utf8 -m compileall -q tools local
git -c core.whitespace=cr-at-eol diff --check
```

预期：全部 exit 0，且本轮两个改动文件通过严格 UTF-8 解码与乱码黑名单检查。

- [ ] **Step 2: 做只读发布前核对**

确认 `tools/release.py --check` 的输出同时列出四类发布资产（主程序 ZIP、独立 EXE、安装器、手机控制组件）以及 manifest；确认 `publish()` 参数列表由回归测试锁住。不要在本任务中调用 `--publish`、创建 tag、上传 GitHub 或覆盖已有 Release。

- [ ] **Step 3: 停在用户外部副作用门禁**

把以下动作交给用户显式确认后再做：

1. 在干净且已提交的目标来源上执行 `tools/release.py --prepare`，确认组件 ZIP 已进入候选目录。
2. 用户确认后执行 `tools/release.py --publish`，完成真实 GitHub Release 上传。
3. 用 GitHub Release 资产列表和应用端组件下载流程核对资产真实存在，再继续 Tailscale/Cloudflare 真机验收。

计划执行结果必须把“代码修复通过”“真实 Release 已发布”“手机真机验收”三种状态分开记录。

## Self-Review

- 根因覆盖：最终上传列表缺少 `component`，以及资产指纹遗漏 `component`，均有测试和代码修改点。
- 未扩大范围：不改组件构建、下载、通道生命周期、UI 或学校接口。
- 不把本地假资产测试当作 GitHub Release 端到端证据。
- 不自动执行外部发布，不自动提交 Git。
- `amendment-009`（既有计划范围漏列 `local/tests/test_advanced_features.py`）作为上一轮计划的历史偏差单独记录；本返修不通过改历史计划来掩盖它。

## Execution Notes

执行前确认工作区仍包含其他 agent 的 WIP；只修改本计划列出的文件。执行完成后停在用户发布与真机验收门禁，不把 `acceptance_status` 误报为通过。
