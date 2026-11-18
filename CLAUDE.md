# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

@AGENTS.md

项目规则、授权边界、命令、测试注意事项和架构都写在 `AGENTS.md` 里（上面已经导入），所有 agent 共用。本文件只补 Claude 专用的几条。

- **原型预览**：在内置浏览器里调 `preview_start`，用 `.claude/launch.json` 的 `prototype` 配置，等价于 `py -3.12 -m http.server 8790 --bind 127.0.0.1 --directory design/prototype/workbench-2026-11`。断行要以 Edge 的结果为准，原因见 AGENTS.md。
- **提交尾注**：`Agent:` 和 `Co-Authored-By:` 两行连着写，**中间不留空行**（空行会让 `Agent:` 掉出 trailer 区，`%(trailers)` 取不到）。长度上限和正文写法见 AGENTS.md「提交规范」。
- **`.claude/` 净化**：`.claude/` 下的计划、结果和交接记录对共享工作区可见。每轮收工前都提醒运行 scrub-share（命令见 AGENTS.md「收工」）。
- **测试与重构铁律（最高优先级）**：
  - `local/tests/` 测试文件总数硬上限为 **39 个**，严禁新建 `test_*.py`（包括禁止新建 `test_prerefactor_*`、`test_*_wiring.py`、`test_*_patch_targets.py`、`test_ui_exit_paths_*` 等过渡或接线守卫）。
  - 拆分 `local/app.py` (`Api`) 时只改业务委派与已有测试，只守 `domain/` 纯函数与最外层 UI 契约，不守中间层私有状态与 monkeypatch 落点。
