# -*- coding: utf-8 -*-
"""phone_rules 验证码图片投影回归：合法有界整段保留，非法/超限不放行。

纯函数测试：不起 socket、不读墙钟、不碰真实凭据与学校接口。

@author Author
"""
from __future__ import annotations

import base64
import sys
import unittest
from pathlib import Path

LOCAL = Path(__file__).resolve().parents[1]
if str(LOCAL) not in sys.path:
    sys.path.insert(0, str(LOCAL))

import login_relay  # noqa: E402
from domain.phone_rules import (  # noqa: E402
    MAX_IMAGE_BYTES, TEXT_LIMIT, project_event, project_state, project_text,
    strip_sensitive,
)

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def png_uri(blob: bytes) -> str:
    return "data:image/png;base64," + base64.b64encode(blob).decode("ascii")


# 真 PNG 魔数 + 400 字节填充：base64 后远超 TEXT_LIMIT，能暴露截断缺口
LONG_PNG = png_uri(PNG_MAGIC + b"\x00" * 400)


class ImageProjectionTests(unittest.TestCase):
    """验证码图投影：合法且有界的 data:image/png;base64, 整段保留。"""

    def test_valid_bounded_png_is_preserved_whole(self):
        self.assertGreater(len(LONG_PNG), TEXT_LIMIT)
        self.assertEqual(project_text(LONG_PNG), LONG_PNG)
        self.assertEqual(strip_sensitive({"image": LONG_PNG}), {"image": LONG_PNG})
        self.assertEqual(project_state({"image": LONG_PNG})["image"], LONG_PNG)
        payload = project_event("phone_relogin", {"image": LONG_PNG})["payload"]
        self.assertEqual(payload["image"], LONG_PNG)

    def test_plain_text_still_clipped_at_text_limit(self):
        self.assertEqual(project_text("x" * (TEXT_LIMIT + 80)),
                         "x" * TEXT_LIMIT + "…")
        self.assertEqual(strip_sensitive({"note": "y" * 500})["note"],
                         "y" * TEXT_LIMIT + "…")

    def test_sensitive_keys_still_stripped_beside_image(self):
        out = strip_sensitive({"image": LONG_PNG, "token": "t",
                              "password": "p", "path": "C:/x"})
        self.assertEqual(out, {"image": LONG_PNG})

    def test_illegal_base64_png_is_not_passed(self):
        for bad in ("data:image/png;base64,zzz",
                    "data:image/png;base64,!!!!",
                    "data:image/png;base64,AAAA=A",
                    "data:image/png;base64,A"):
            with self.subTest(image=bad):
                self.assertEqual(project_text(bad), "")
                self.assertEqual(strip_sensitive({"image": bad}), {"image": ""})

    def test_over_limit_png_is_not_passed(self):
        raw = "A" * (MAX_IMAGE_BYTES + 4)
        self.assertEqual(project_text("data:image/png;base64," + raw), "")

    def test_boundary_length_is_kept(self):
        # 真 PNG 魔数 + 填充使 base64 段恰好达到上限：边界值必须整段放行
        blob = PNG_MAGIC + b"\x00" * (3 * (MAX_IMAGE_BYTES // 4) - len(PNG_MAGIC))
        image = png_uri(blob)
        self.assertEqual(len(image.split(",", 1)[1]), MAX_IMAGE_BYTES)
        self.assertEqual(project_text(image), image)

    def test_empty_or_non_png_content_is_not_passed(self):
        """解码后空内容/非 PNG 一律不放行：与 worker 的魔数门禁同一张。"""
        self.assertEqual(project_text("data:image/png;base64,"), "")
        self.assertEqual(strip_sensitive({"image": "data:image/png;base64,"}),
                         {"image": ""})
        for blob in (b"",                          # 解码后空内容
                     b"\xff\xd8\xff\xe0" + b"\x00" * 32,   # JPEG 魔数
                     b"x" * 64,                            # 纯文本
                     b"\x89PNG-not-really"):               # 近似魔数
            with self.subTest(blob=blob):
                image = png_uri(blob)
                self.assertEqual(project_text(image), "")
                self.assertEqual(strip_sensitive({"image": image}), {"image": ""})

    def test_image_limit_matches_worker(self):
        self.assertEqual(MAX_IMAGE_BYTES, 128 * 1024)
        self.assertEqual(MAX_IMAGE_BYTES, login_relay.MAX_IMAGE_BYTES)
        self.assertEqual(PNG_MAGIC, login_relay.PNG_MAGIC)

    def test_non_image_strings_follow_text_limit(self):
        jpeg = "data:image/jpeg;base64," + "A" * 500
        self.assertEqual(project_text(jpeg), jpeg[:TEXT_LIMIT] + "…")
        self.assertEqual(project_text(123), 123)
        self.assertIsNone(project_text(None))

    def test_projection_reaches_nested_state_and_events(self):
        raw = {"login_relay": {"image": LONG_PNG, "password": "p"},
               "items": [LONG_PNG, "z" * 500]}
        projected = project_state(raw)
        self.assertEqual(projected["login_relay"]["image"], LONG_PNG)
        self.assertNotIn("password", projected["login_relay"])
        self.assertEqual(projected["items"][0], LONG_PNG)
        self.assertEqual(projected["items"][1], "z" * TEXT_LIMIT + "…")
        payload = project_event("phone_relogin",
                                {"image": LONG_PNG, "safe_error": ""})["payload"]
        self.assertEqual(payload["image"], LONG_PNG)


if __name__ == "__main__":
    unittest.main()
