# -*- coding: utf-8 -*-
"""清点 phone_service 的反射调用与组件服务的越层 import（ast 只读）。

产出 reflection.md 三张表：
1. 手机动作 → 实际反射调用的 Api 方法 → 将来归哪个服务（归属是手工判断，单列一栏）；
2. advanced_component_service 对 infrastructure.component_packages 的每个用法与消法；
3. test_layer_boundaries 的存量越层例外。

口径：不 import、不运行任何产品代码，只读源码；行号以 --head 指定的基线为准。
@author Author
"""
from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lock_graph as lg  # noqa: E402  同目录的证据脚本，不是产品代码

# 手工判断：每个被反射调用的 Api 方法将来归哪个服务。
# 依据 = 按方法名的功能归类（lock_graph 的规则与例外）+ fields.md 里该功能带的字段；
# 只有 save_prefs 是例外：偏好是 app 的公共设施，不随任何一个功能服务走。
OWNER = {
    "list_activities": "活动列表服务",
    "check": "登录恢复服务",
    "start_plan": "计划服务",
    "start_request_state": "计划服务",
    "cancel_start_request": "计划服务",
    "stop_plan": "计划服务",
    "cancel_task": "计划服务",
    "save_prefs": "偏好端口（留 Api，不归功能服务）",
    "show_window": "窗口与托盘服务",
    "phone_relogin_begin": "登录恢复服务",
    "phone_relogin_submit": "登录恢复服务",
    "phone_relogin_cancel": "登录恢复服务",
}

# 构造默认端口：__init__ 里「参数为空就退回 _packages.X」的九个端口。
# 键是 _packages 的属性名，值是（参数名, 这个端口干什么）。
PORTS = {
    "version": ("version", "当前版本号（找发布资产用）"),
    "inspect_archive": ("inspect", "单体包体检：清单、签名、feature"),
    "install": ("install", "单体包安装（事务、回滚在 infrastructure）"),
    "inspect_artifact": ("inspect_artifact", "拆分资产体检"),
    "find_cached_artifact": ("find_cached_artifact", "查缓存命中"),
    "cache_artifact": ("cache_artifact", "把资产放进缓存"),
    "commit_artifact_group": ("commit_artifact_group", "整组原子切换"),
    "feature_status": ("status", "组件当前状态"),
    "remove": ("remover", "卸载组件"),
}

CMD = "python -B design/evidence/<日期>/api-coordination/scripts/reflect.py --head <哈希>"


def _table(add, head, rows) -> None:
    add("| " + " | ".join(head) + " |")
    add("|" + "---|" * len(head))
    for row in rows:
        add("| " + " | ".join(row) + " |")


def _parse(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=path.as_posix())


def action_params(root: Path) -> dict[str, set[str]]:
    """domain/phone_rules.py 的动作白名单（动作 → 允许的参数键）。"""
    tree = _parse(root / "local/domain/phone_rules.py")
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == "ACTION_PARAMS" for t in node.targets):
            out = {}
            for key, value in zip(node.value.keys, node.value.values):
                params = set()
                for elt in getattr(value, "elts", []):
                    if isinstance(elt, ast.Constant):
                        params.add(str(elt.value))
                out[str(key.value)] = params
            return out
    raise SystemExit("ACTION_PARAMS not found")


def dispatch_rewrites(root: Path) -> list[tuple[int, str]]:
    """dispatch 里两处服务端改写：换方法名 / 补参数。"""
    tree = _parse(root / "local/application/phone_service.py")
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "dispatch":
            for sub in ast.walk(node):
                if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute) \
                        and sub.func.attr == "_call" and sub.args \
                        and isinstance(sub.args[0], ast.Constant):
                    out.append((sub.lineno, "改调 `%s`" % sub.args[0].value))
                if isinstance(sub, ast.keyword) and sub.arg == "source":
                    out.append((sub.lineno, "补参数 `source=\"%s\"`"
                                % getattr(sub.value, "value", ast.unparse(sub.value))))
            return sorted(out)
    raise SystemExit("dispatch not found")


def api_def_lines(root: Path) -> dict[str, int]:
    tree = _parse(root / "local/app.py")
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == "Api":
            return {n.name: n.lineno for n in node.body if isinstance(n, ast.FunctionDef)}
    raise SystemExit("Api not found")


def package_usages(root: Path) -> tuple[int, dict[str, list[int]]]:
    """组件服务里 `_packages.X` 的用法：返回 import 行号与按属性分组的用法行。"""
    tree = _parse(root / "local/application/advanced_component_service.py")
    import_line = None
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "infrastructure" and any(
                a.name == "component_packages" for a in node.names):
            import_line = node.lineno
    usages: dict[str, list[int]] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) \
                and node.value.id == "_packages":
            usages.setdefault(node.attr, []).append(node.lineno)
    return import_line, usages


def layer_exceptions(root: Path) -> list[tuple[str, str, str]]:
    """test_layer_boundaries 的存量越层例外（键是文件、模块名）。"""
    tree = _parse(root / "local/tests/test_layer_boundaries.py")
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == "LEGACY_DIRECTION_VIOLATIONS"
                for t in node.targets):
            rows = []
            for key, value in zip(node.value.keys, node.value.values):
                src, mod = (str(k.value) for k in key.elts)
                rows.append((src, mod, str(value.value)))
            return rows
    raise SystemExit("LEGACY_DIRECTION_VIOLATIONS not found")


def build(root: Path, head: str) -> list[str]:
    L: list[str] = []
    add = L.append
    actions = action_params(root)
    rewrites = dispatch_rewrites(root)
    defs = api_def_lines(root)
    import_line, usages = package_usages(root)
    exceptions = layer_exceptions(root)

    add("# 反射调用与越层依赖")
    add("")
    add("- 生成脚本：`scripts/reflect.py`（ast 只读源码，不 import 产品代码）")
    add("- 命令：`%s`" % CMD.replace("<哈希>", head))
    add("- 基线：`%s`；「将来归谁」一栏是手工判断（依据写在脚本 OWNER 的注释），其余列都由 ast 读出"
        % head)
    add("")
    add("## 一、phone_service 按名字反射调用的 Api 方法")
    add("")
    add("- 注入点：`local/app.py:899` 构造 `PhoneAccessService(api=self, ...)` —— 整个 Api 传进去；"
        "`local/application/phone_service.py:463` `getattr(self._api, name, None)` 按名字取方法。")
    add("- 动作白名单在 `local/domain/phone_rules.py:155`（`ACTION_PARAMS`，12 个动作）；"
        "`dispatch`（phone_service.py:447）先 `normalize_action` 校验参数，再 `_call` 反射。")
    add("- `_call` 把参数原样展开成 kwargs：Api 方法的签名就是远程可调用面的一部分，"
        "改参数名不会在导入期暴露，只会在手机端变成 `internal`。")
    add("")
    _table(add, ("动作", "参数白名单", "实际调的 Api 方法", "定义行", "功能", "将来归谁（手工）"),
           [[a, "、".join(sorted(actions[a])) or "—",
             m, "`local/app.py:%d`" % defs[m],
             lg.classify("Api." + m)[0], OWNER[m]]
            for a, m in sorted((a, "save_prefs" if a == "save_retry_policy" else a)
                               for a in actions)])
    add("")
    add("动作名与 Api 方法名不是一一对应，`dispatch` 里有两处服务端改写（%s）："
        % "、".join("`local/application/phone_service.py:%d`" % n for n, _ in rewrites))
    add("")
    _table(add, ("行", "改写"), [["`%d`" % n, t] for n, t in rewrites])
    add("")
    add("- 守卫现状：`local/tests/test_phone_service.py` 用假 api 派发校验白名单与参数"
        "（459–533 一带），但没有测试盯着「白名单动作 ↔ 真实 Api 方法签名」的对应——"
        "把 `start_plan` 的参数改名，测试照样绿，手机端静默变 `internal`。设计稿要补这条守卫。")
    add("")
    add("## 二、advanced_component_service 对 infrastructure 的用法")
    add("")
    add("- 越层点只有一处：`local/application/advanced_component_service.py:%d` "
        "`from infrastructure import component_packages as _packages`（application 层按 "
        "`_ALLOWED_KINDS` 不许 import infrastructure）。" % import_line)
    add("- 用法分三类：构造函数的默认端口（参数为空就退回 `_packages.X`）、"
        "静态表 `ARTIFACTS`（拆分资产清单）、常量 `CLOUDFLARED_VERSION`（内置 cloudflared 版本）。")
    add("")
    _table(add, ("行", "写法", "类别", "消法"),
           [["`%d`" % lines[0],
             "`_packages.%s`" % attr,
             ("构造默认端口（`%s` 为空时退回；%s）" % (PORTS[attr][0], PORTS[attr][1]))
             if attr in PORTS else
             ("静态表：`_run_split_assets` 里 %d 处用" % len(lines)
              if attr == "ARTIFACTS" else "常量：组件包内置 cloudflared 版本"),
             ("app.py 构造时显式传 `%s`（与 download/install 同路），删默认值"
              % PORTS[attr][0]) if attr in PORTS else
             ("加构造参数把表传进来" if attr == "ARTIFACTS"
              else "加构造参数把版本号传进来")]
            for attr, lines in sorted(usages.items(), key=lambda kv: kv[1][0])])
    add("")
    add("- 核过的事实：`local/app.py:909-931` 构造两个服务时已显式传 `download`、`asset_resolver`、"
        "`install`、`inspect_artifact`、`commit_artifact_group`，没传的正是六个默认端口"
        "（version、inspect、find_cached_artifact、cache_artifact、status、remover）；"
        "服务内部 8 处调用端口都带 `root=self._root`，所以消掉这条越层不需要改行为。")
    add("")
    add("## 三、test_layer_boundaries 的存量越层例外")
    add("")
    add("- 规则：按模块锁（键是「文件、完整模块名」），同包再加一个模块照样报；"
        "每条都要写去处，消掉时从字典里删。")
    add("")
    _table(add, ("文件", "import 的模块", "登记的去处"), exceptions)
    add("")
    add("- 第二条例外对应 `local/infrastructure/component_packages.py:101`：`_root(root)` 的 "
        "`root is None` 分支里延迟 `from runtime_paths import DATA_DIR`。服务侧 8 处都传了 "
        "root，这条在「调用方一律传 root」后可消；`_root(None)` 还有没有别的可达调用方，"
        "本次没核全，消例外的计划里要按同一口径再核一遍。")
    add("")
    add("## 与 2026-11-12 审计的对照")
    add("")
    add("- X3（phone_service 按名字反射调用 Api 的公开方法）：仍在，注入点与白名单同审计"
        "描述；本次补上了「12 个动作、两处改写、无签名守卫」的具体面。")
    add("- L1（application/advanced_component_service.py 直接 import infrastructure）：仍在，"
        "全仓只此一处（application 与 domain 下 grep 不到第二个）；本次把它拆成 11 个用法点，"
        "每个都给了消法。")
    add("")
    return L


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="反射调用与越层依赖清点（ast 只读）")
    ap.add_argument("--repo", default=None)
    ap.add_argument("--out-dir", default=None)
    ap.add_argument("--head", default="（未记录）")
    args = ap.parse_args(argv)
    root = Path(args.repo).resolve() if args.repo else Path(__file__).resolve().parents[5]
    if not (root / "local/app.py").exists():
        print("找不到 local/app.py；用 --repo 指定仓库根。")
        return 2
    text = build(root, args.head)
    if not args.out_dir:
        print("\n".join(text))
        return 0
    out = Path(args.out_dir)
    (out / "reflection.md").write_text("\n".join(text) + "\n",
                                       encoding="utf-8", newline="\n")
    print("已写 %s（%d 行）" % (out / "reflection.md", len(text)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
