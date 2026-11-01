"""QA 桥与 QA 静态服务的反向契约测试。

这些文件不在产品运行路径上，页面拆分、接口改名时不会有人报错。2026-10-30
的教训：local/ui 拆成 32 个脚本后，qa 工具的静态白名单只服务 4 个，全场景
退化成 `S is not defined`；而截图断言只看文件体积，于是失败现场照样判绿。
local/tests 对工具与桥的引用当时是 0 处，所以没人发现。这里把「桥跟得上
生产接口」「静态服务认得出所有资源」写成断言，让腐烂立刻变红。

@author Author
"""
import importlib.util
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BRIDGE = ROOT / "local" / "tests" / "fixtures" / "runtime_bridge.js"
TOOL = ROOT / "tools" / "qa_runtime_reliability.py"
UI = ROOT / "local" / "ui"
APP = ROOT / "local" / "app.py"

# 桥故意不实现的方法：每条都写清现在为什么不需要，功能纳入 QA 时必须删掉。
# 断言是双向的——多出来的条目也会失败，防止这份豁免单变成新的腐烂温床。
ALLOWED_MISSING = {
    "update_cancel": "检查更新（B11）尚无 QA 场景",
    "update_download": "检查更新（B11）尚无 QA 场景",
    "update_launch": "检查更新（B11）尚无 QA 场景",
    "phone_access_state": "手机访问（B13）不在 v1.1.1 发布包内",
    "start_phone_access": "手机访问（B13）不在 v1.1.1 发布包内",
    "stop_phone_access": "手机访问（B13）不在 v1.1.1 发布包内",
    "install_advanced_feature": "高级功能安装（B12）不在 v1.1.1 发布包内",
    "prepare_phone_relogin": "手机重登（B14）不在 v1.1.1 发布包内",
    "save_relogin_credentials": "手机重登（B14）不在 v1.1.1 发布包内",
    "clear_relogin_credentials": "手机重登（B14）不在 v1.1.1 发布包内",
}


def _ui_api_names() -> set:
    """页面实际调用的 Api 方法名（只认字面量调用，变量名不算）。"""
    names = set()
    for path in UI.rglob("*.js"):
        text = path.read_text(encoding="utf-8")
        names.update(re.findall(r"\bapi\(\s*[\"']([a-z_]+)[\"']", text))
    return names


def _bridge_methods() -> set:
    text = BRIDGE.read_text(encoding="utf-8")
    start = text.index("const methods = {")
    end = text.index("\n  };", start)
    return set(re.findall(r"^    ([a-zA-Z_]\w*):", text[start:end], re.M))


def _tool_module():
    """按路径载入 qa 工具：tools/ 不是包，导入只为读常量，不跑场景。"""
    spec = importlib.util.spec_from_file_location("qa_runtime_reliability", TOOL)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class QaBridgeContractTest(unittest.TestCase):
    def test_bridge_covers_every_ui_api_call(self):
        missing = _ui_api_names() - _bridge_methods()
        self.assertEqual(sorted(missing - set(ALLOWED_MISSING)), [],
                         "QA 桥缺方法：这些 api(...) 调用在浏览器里会抛 no_such_method")
        # 反向守卫只认「桥有没有实现这个方法」，不认页面是否调用它：
        # codex 的 WIP 页面会调用尚未进桥的方法，干净 HEAD 则根本不调用，
        # 两者都合法；用 missing 做守卫会把测试绑死在某一版 UI 上。
        stale = sorted(name for name in ALLOWED_MISSING if name in _bridge_methods())
        self.assertEqual(stale, [],
                         "ALLOWED_MISSING 里这些方法桥已经实现，豁免条目该删了：%s" % stale)

    def test_static_server_serves_every_ui_asset(self):
        module = _tool_module()
        html = (UI / "index.html").read_text(encoding="utf-8")
        refs = re.findall(r"(?:src|href)=\"([^\"]+)\"", html)
        local = [r for r in refs
                 if not r.startswith(("http:", "https:", "data:", "#", "javascript:"))]
        self.assertGreater(len(local), 10, "index.html 的静态引用少于预期，正则可能失效")
        for ref in local:
            suffix = Path(ref).suffix.lower()
            self.assertIn(suffix, module.CTYPES, "qa 静态服务不认这个后缀：%s" % ref)

    def test_terms_version_matches_product(self):
        module = _tool_module()
        app = APP.read_text(encoding="utf-8")
        found = re.search(r'^TERMS_VERSION\s*=\s*"([^"]+)"', app, re.M)
        self.assertIsNotNone(found, "local/app.py 里找不到 TERMS_VERSION")
        self.assertEqual(module.TERMS_VERSION, found.group(1),
                         "qa 工具与 local/app.py 的条款版本必须同值")

    def test_no_static_whitelist_regression(self):
        """白名单式列举静态资源是这次事故的根因，不许回来。

        只查代码形态（定义与成员判断），不查注释里的历史说明。
        """
        source = TOOL.read_text(encoding="utf-8")
        self.assertNotIn("SCREENSHOT_FILES =", source)
        self.assertNotIn("in SCREENSHOT_FILES", source)


if __name__ == "__main__":
    unittest.main()
