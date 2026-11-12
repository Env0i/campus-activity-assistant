"""下载失败原因映射的一致性守卫。

local/app.py 的 _DOWNLOAD_FAIL_REASONS（写日志用）与 local/ui/views/phone.js 的
PHONE_DOWNLOAD_REASON（手机页高级功能区用）注释说同源，两边只要有一边多了或少了
error_code，用户在日志和界面里就会看到不同的原因说法，甚至一边回落后端原话。
这里只读源码、用正则抽键，不 import app（它会拉起一堆运行时依赖）。
"""
import re
import unittest
from pathlib import Path

LOCAL = Path(__file__).resolve().parents[1]


def _keys(source: str, anchor: str, quoted: bool) -> set:
    """取 anchor 之后第一个 {...} 块里的键。"""
    start = source.index(anchor)
    block = source[source.index("{", start):]
    block = block[:block.index("}")]
    pattern = r'"(\w+)"\s*:' if quoted else r'^\s*(\w+)\s*:'
    return set(re.findall(pattern, block, re.M))


class DownloadReasonMapTests(unittest.TestCase):
    def test_python_and_js_reason_maps_share_keys(self):
        py = (LOCAL / "app.py").read_text(encoding="utf-8")
        js = (LOCAL / "ui" / "views" / "phone.js").read_text(encoding="utf-8")
        py_keys = _keys(py, "_DOWNLOAD_FAIL_REASONS = {", True)
        js_keys = _keys(js, "const PHONE_DOWNLOAD_REASON = {", False)
        self.assertTrue(py_keys, "没抽到 app.py 的键，正则需要跟着源码改")
        self.assertEqual(py_keys, js_keys)

    def test_not_published_reason_is_in_both_maps(self):
        """I3：发布页上没有组件资产时，日志与手机页都要有「未发布」原因，不能回落到网络类文案。"""
        py = (LOCAL / "app.py").read_text(encoding="utf-8")
        js = (LOCAL / "ui" / "views" / "phone.js").read_text(encoding="utf-8")
        self.assertIn("not_published", _keys(py, "_DOWNLOAD_FAIL_REASONS = {", True))
        self.assertIn("not_published", _keys(js, "const PHONE_DOWNLOAD_REASON = {", False))


if __name__ == "__main__":
    unittest.main()
