#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""前端分层的契约：state/ 不引用 views/、controllers/ 与 app.js 的名字；views/ 不引用后两者的名字。

量法与审计参照表一致（按名字匹配、排除属性访问 / 对象字面量的键 / 注释与字符串 / 本文件同名局部声明），
由 tools/code_shape/ui_refs.mjs 清点；存量例外记在 tools/code_shape/ui_layer_allow.json，只减不增。
白名单按「文件 × 名字」计，不约束同一名字在同一文件里的引用次数。
没有 node 时两条清点用例跳过并说明，其余用例照常跑。
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

TESTS = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS))

from fixtures.ui_harness import LOCAL  # noqa: E402

ROOT = LOCAL.parent
UI_REFS = ROOT / "tools/code_shape/ui_refs.mjs"
ALLOW = ROOT / "tools/code_shape/ui_layer_allow.json"

# 批 3 已把 8 个纯判断函数搬回 state 层：它们不许以「上层名字」的身份回到白名单里。
MOVED_TO_STATE = ("verifiedSigned", "hmsDay", "submittingDetail", "effectiveRetryDeadline",
                  "selectionSignature", "numOrNull", "termsLocked", "clockPopOpenNow")


def _load_allow():
    return json.loads(ALLOW.read_text(encoding="utf-8"))


def _run_refs():
    """跑一次 ui_refs.mjs，返回 {层: {(文件, 名字)}}。"""
    out = subprocess.run(
        ["node", str(UI_REFS)], cwd=str(ROOT),
        capture_output=True, text=True, encoding="utf-8", check=True)
    data = json.loads(out.stdout)
    result = {}
    for group in ("state", "views"):
        result[group] = {(r["file"], r["name"]) for r in data[group]}
    return result


@unittest.skipUnless(shutil.which("node"), "本机没有 node，前端跨层清点跳过")
class UiLayerRefsTests(unittest.TestCase):
    def _compare(self, group):
        allow = {(file, name) for file, names in _load_allow()[group].items() for name in names}
        actual = _run_refs()[group]
        extra = sorted(actual - allow)
        missing = sorted(allow - actual)
        self.assertEqual([], extra,
                         "%s/ 出现新的跨层引用（文件, 名字），要么把定义搬到正确的层，"
                         "要么加进 ui_layer_allow.json：%r" % (group, extra))
        self.assertEqual([], missing,
                         "ui_layer_allow.json 里的这些 %s/ 项在代码里已经没有了，"
                         "请删掉：%r" % (group, missing))

    def test_state_does_not_reference_upper_layers(self):
        self._compare("state")

    def test_views_do_not_reference_controllers_or_app(self):
        self._compare("views")


class UiLayerAllowListTests(unittest.TestCase):
    """不依赖 node：白名单本身的结构与内容。"""

    def test_moved_names_do_not_come_back_as_upper_layer_definitions(self):
        state_names = {name for names in _load_allow()["state"].values() for name in names}
        back = sorted(set(MOVED_TO_STATE) & state_names)
        self.assertEqual([], back,
                         "这些名字已经在 state 层定义，不该再作为上层名字出现在白名单：%r" % (back,))

    def test_allow_list_is_sorted_and_non_empty(self):
        allow = _load_allow()
        for group in ("state", "views"):
            self.assertTrue(allow[group], "%s 组白名单不能为空（否则守卫形同虚设）" % (group,))
            files = list(allow[group])
            self.assertEqual(sorted(files), files, "%s 组的文件要排序" % (group,))
            for file, names in allow[group].items():
                self.assertEqual(sorted(names), names, "%s 的 %s 要排序" % (group, file))


if __name__ == "__main__":
    unittest.main()
