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
    redact_log_text, strip_sensitive,
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


class LogRedactionTests(unittest.TestCase):
    """运行记录经隧道转发前隐去网址与本机路径；只作用在 log 事件的文字上。"""

    URL = "（网址已隐藏）"
    PATH = "（路径已隐藏）"

    def test_url_replaced_and_sentence_kept(self):
        out = redact_log_text("请求 https://school.example.com/a/b?x=1，失败了")
        self.assertEqual(out, "请求 %s，失败了" % self.URL)
        self.assertEqual(redact_log_text("见(http://10.0.0.1:8080/p)."),
                         "见(%s)." % self.URL)

    def test_url_glued_to_chinese_stops_at_non_ascii(self):
        self.assertEqual(redact_log_text("地址https://a.cn/x下一句"),
                         "地址%s下一句" % self.URL)

    def test_drive_paths_backslash_and_slash(self):
        self.assertEqual(redact_log_text("读取 C:\\Users\\某人\\data\\a.json 失败"),
                         "读取 %s 失败" % self.PATH)
        self.assertEqual(redact_log_text("写入D:/work/out.log。好"),
                         "写入%s。好" % self.PATH)
        self.assertEqual(redact_log_text('"C:\\a\\b" 和 \'d:/q\''),
                         '"%s" 和 \'%s\'' % (self.PATH, self.PATH))

    def test_unc_path(self):
        self.assertEqual(redact_log_text("打不开 \\\\srv\\share\\dir\\f.txt，重试"),
                         "打不开 %s，重试" % self.PATH)

    def test_spaced_drive_path_is_fully_masked(self):
        self.assertEqual(
            redact_log_text("C:\\Program Files\\x\\cloudflared.exe 已启动"),
            "%s 已启动" % self.PATH)
        self.assertEqual(
            redact_log_text("装到 D:/My Tools/a b/c.exe，再试"),
            "装到 %s，再试" % self.PATH)

    def test_spaced_unc_path_is_fully_masked(self):
        self.assertEqual(
            redact_log_text("\\\\srv\\my share\\dir\\f.txt 不可达"),
            "%s 不可达" % self.PATH)

    def test_plain_words_after_path_are_not_swallowed(self):
        self.assertEqual(redact_log_text("C:\\a\\b 已启动 成功 了"),
                         "%s 已启动 成功 了" % self.PATH)
        self.assertEqual(redact_log_text("读 C:\\Program Files\\x 失败 请重试"),
                         "读 %s 失败 请重试" % self.PATH)

    def test_log_payload_stays_a_string_after_redaction(self):
        event = project_event("log", "C:\\Program Files\\x\\a.exe 已启动")
        self.assertIsInstance(event["payload"], str)
        self.assertEqual(event["payload"], "%s 已启动" % self.PATH)

    def test_trailing_ascii_punct_kept(self):
        self.assertEqual(redact_log_text("see C:\\a\\b."), "see %s." % self.PATH)

    def test_plain_text_and_non_strings_untouched(self):
        for text in ("普通一句话 12:30 a/b word:x", "[预报名] 活动A：开始"):
            self.assertEqual(redact_log_text(text), text)
        self.assertIsNone(redact_log_text(None))
        self.assertEqual(redact_log_text(5), 5)

    def test_log_event_string_and_dict_payload(self):
        event = project_event("log", "访问 https://x.example.cn/p 于 C:\\a\\b")
        self.assertEqual(event["payload"], "访问 %s 于 %s" % (self.URL, self.PATH))
        event = project_event("log", {"text": "D:/x/y", "detail": "http://h/p", "n": "C:/keep"})
        self.assertEqual(event["payload"]["text"], self.PATH)
        self.assertEqual(event["payload"]["detail"], self.URL)
        self.assertEqual(event["payload"]["n"], "C:/keep")

    def test_redacts_before_clipping(self):
        event = project_event("log", "x" * 190 + " https://secret.example.com/aaaa/bbbb")
        self.assertNotIn("secret", event["payload"])
        self.assertNotIn("https", event["payload"])

    def test_non_log_events_and_state_untouched(self):
        payload = {"name": "活动 https://a.b/c", "place": "C:\\厅", "href": "https://a.b/c"}
        event = project_event("activities", payload)
        self.assertEqual(event["payload"], payload)
        self.assertEqual(project_state({"link": "https://a.b/c"})["link"], "https://a.b/c")

    def test_captcha_image_in_log_payload_not_touched(self):
        event = project_event("log", {"text": LONG_PNG})
        self.assertEqual(event["payload"]["text"], LONG_PNG)
        event = project_event("phone_relogin", {"image": LONG_PNG})
        self.assertEqual(event["payload"]["image"], LONG_PNG)


if __name__ == "__main__":
    unittest.main()
