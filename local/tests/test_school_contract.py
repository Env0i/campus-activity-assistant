"""读共享契约样例（contracts/school-api/）的测试（S4 测试部分）。

样例只放接口形状，本机版与服务器版的测试读同一份。这里验证本机版的消费代码
（列表映射、签到时间解析、getJoinInfo 判已报名、回包分类）与样例一致：
学校改接口时先更新样例，再让这些测试告诉你哪段本机代码要跟着改。
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from unittest import mock

LOCAL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LOCAL))
import grab  # noqa: E402
from domain.signup_reply import classify_signup_reply  # noqa: E402

# 仓库相对路径：local/tests → local → 仓库根 → contracts/school-api
CONTRACTS = LOCAL.parent / "contracts" / "school-api"

LIST_FIELDS = {
    "index", "id", "name", "sign_start", "sign_end", "act_start", "act_end", "place",
    "signed", "checkin_required", "checkout_required", "checkin_start", "checkin_end",
    "checkout_start", "checkout_end", "attendance_source", "attendance_state", "state",
}


def _load(name):
    with open(CONTRACTS / name, "r", encoding="utf-8") as handle:
        return json.load(handle)


class _Budget:
    """is_joined 要三态时传的预算：够用、不过期。"""

    def expired(self):
        return False

    def timeout_s(self, seconds):
        return seconds


class ContractFilesTests(unittest.TestCase):
    def test_sample_files_are_present(self):
        for name in ("list-activity.items.json", "get-info.data.json",
                     "get-join-info.json", "signup-replies.json"):
            self.assertTrue((CONTRACTS / name).is_file(), "缺契约样例 %s" % name)


class ListActivityContractTests(unittest.TestCase):
    def setUp(self):
        self.items = _load("list-activity.items.json")

    def test_every_item_has_the_eighteen_fields(self):
        self.assertTrue(self.items)
        for item in self.items:
            self.assertEqual(set(item), LIST_FIELDS)
            self.assertIsInstance(item["signed"], bool)

    def test_window_times_parse_as_school_time(self):
        for item in self.items:
            for name in ("sign_start", "sign_end", "act_start", "act_end"):
                self.assertIsInstance(grab.parse_ts(item[name]), float, name)
            self.assertLess(grab.parse_ts(item["sign_start"]), grab.parse_ts(item["sign_end"]))

    def test_sign_state_agrees_with_the_samples_state_column(self):
        # 样例取自 2026-11-03 当天：第一条报名已截止，第二条开放中
        now = grab.parse_ts("2026-11-03 12:00:00")
        for item in self.items:
            self.assertEqual(grab.sign_state(item, now=now), item["state"], item["id"])

    def test_fetch_activities_maps_school_fields_to_the_contract_names(self):
        # 把样例按映射表反过来还原成学校列表的原始条目，再走真实的映射代码：
        # 映射改名或漏字段，这里立刻对不上
        raw_rows = [{
            "id": item["id"], "hdmc": item["name"], "hddd": item["place"],
            "bmkssj": item["sign_start"], "bmjssj": item["sign_end"],
            "hdkssj": item["act_start"], "hdjssj": item["act_end"],
            "bmzt": 1 if item["signed"] else 0,
        } for item in self.items]
        reply = {"code": 1, "data": {"count": len(raw_rows), "list": raw_rows}}
        with mock.patch.object(grab, "_post", return_value=reply):
            mapped = grab.fetch_activities()
        self.assertEqual(len(mapped), len(self.items))
        for got, want in zip(mapped, self.items):
            for name in ("id", "name", "place", "sign_start", "sign_end",
                         "act_start", "act_end", "signed"):
                self.assertEqual(got[name], want[name], name)

    def test_map_activity_is_a_pure_mapping_of_the_raw_item(self):
        """E3：列表字段映射抽成纯函数后，键集与取值仍跟契约样例对得上。"""
        raw = _load("list-activity.raw-item.json")
        mapped = grab._map_activity(raw)
        item = self.items[0]
        # 契约条目多两个展示列（index、state），映射多一个 type（学校 hdlx）：
        # 去掉这两组后键集必须完全一致，新增字段不会悄悄漏进契约。
        self.assertEqual(set(mapped) - {"type"}, set(item) - {"index", "state"})
        for ours, theirs in (("name", "hdmc"), ("place", "hddd"),
                             ("sign_start", "bmkssj"), ("sign_end", "bmjssj"),
                             ("act_start", "hdkssj"), ("act_end", "hdjssj"),
                             ("type", "hdlx")):
            self.assertEqual(mapped[ours], raw[theirs], ours)
        self.assertIs(mapped["signed"], True)
        self.assertEqual(mapped["attendance_source"], "list")
        self.assertEqual(mapped["attendance_state"], "unknown")


class GetInfoContractTests(unittest.TestCase):
    def test_attendance_fields_are_read_from_the_detail_sample(self):
        detail = _load("get-info.data.json")
        self.assertEqual(len(detail), 49, "详情 49 字段")
        parsed = grab.parse_attendance_detail(detail)
        self.assertTrue(parsed["checkin_required"])
        self.assertEqual(parsed["checkin_start"], detail["qdkssj"])
        self.assertEqual(parsed["checkin_end"], detail["qdjssj"])
        self.assertFalse(parsed["checkout_required"])
        self.assertEqual(parsed["checkout_start"], "")

    def test_cancel_and_sign_flags_are_mapped_per_key(self):
        # R2（计划 20261107-conflict-cancel）：样例里 qxbm=1、sfkybm=0，
        # 逐键映射成 cancel_allowed=True、can_sign=False；两键只来自这两个学校字段
        detail = _load("get-info.data.json")
        self.assertEqual(detail["qxbm"], 1)
        self.assertEqual(detail["sfkybm"], 0)
        parsed = grab.parse_attendance_detail(detail)
        self.assertIs(parsed["cancel_allowed"], True)
        self.assertIs(parsed["can_sign"], False)
        for qxbm, want in ((1, True), (0, False), ("1", True), ("0", False)):
            with self.subTest(qxbm=qxbm):
                changed = dict(detail, qxbm=qxbm, sfkybm=1 - int(qxbm))
                got = grab.parse_attendance_detail(changed)
                self.assertIs(got["cancel_allowed"], want)
                self.assertIs(got["can_sign"], not want)
        for dropped in ("qxbm", "sfkybm"):
            with self.subTest(dropped=dropped):
                partial = {k: v for k, v in detail.items() if k != dropped}
                got = grab.parse_attendance_detail(partial)
                key = "cancel_allowed" if dropped == "qxbm" else "can_sign"
                other = "can_sign" if dropped == "qxbm" else "cancel_allowed"
                self.assertIsNone(got[key], "字段缺失是不知道，不猜")
                self.assertIsNotNone(got[other], "另一个键不受影响")

    def test_detail_sample_window_matches_list_sample(self):
        detail = _load("get-info.data.json")
        second = _load("list-activity.items.json")[1]
        self.assertEqual(detail["bmkssj"], second["sign_start"])
        self.assertEqual(detail["bmjssj"], second["sign_end"])
        self.assertEqual(detail["hdkssj"], second["act_start"])
        self.assertEqual(detail["hdjssj"], second["act_end"])


class GetJoinInfoContractTests(unittest.TestCase):
    def _joined(self, response, budget=None):
        with mock.patch.object(grab, "_post", return_value=response):
            return grab.is_joined("00000000000000000000000000000000", budget=budget)

    def test_not_registered_sample_reads_as_not_joined(self):
        case = next(c for c in _load("get-join-info.json") if c["case"] == "not_registered")
        self.assertIs(self._joined(case["response"]), False)
        self.assertIs(self._joined(case["response"], budget=_Budget()), False)

    def test_registered_sample_reads_as_joined(self):
        case = next(c for c in _load("get-join-info.json") if c["case"] == "registered")
        self.assertEqual(case["response"]["data"]["sfbm"], 1)
        self.assertIs(self._joined(case["response"]), True)
        self.assertIs(self._joined(case["response"], budget=_Budget()), True)

    def _payload(self, data):
        return {"code": 1, "message": "操作成功！", "data": data}

    def test_cancelled_registration_reads_as_not_joined(self):
        # 报名后撤销：data 不回到 null，只把 sfcx 置 1（学校前端 9.2/9.3）。
        # 旧判据「data 非空即已报名」会把撤销过的活动永远钉成已报名，
        # 预检不再提交、收尾核对还会把它写成报名成功。
        data = {"sfbm": 1, "sfcx": 1, "bmsj": "2026-11-03 12:00:00"}
        self.assertIs(self._joined(self._payload(data)), False)
        self.assertIs(self._joined(self._payload(data), budget=_Budget()), False)
        text = {"sfbm": "1", "sfcx": "1"}
        self.assertIs(self._joined(self._payload(text)), False, "字符串 \"1\" 同样是撤销")

    def test_explicitly_signed_false_reads_as_not_joined(self):
        for data in ({"sfbm": 0}, {"sfbm": "0"}, {"sfbm": False, "sfcx": 0}):
            with self.subTest(data=data):
                self.assertIs(self._joined(self._payload(data)), False)
                self.assertIs(self._joined(self._payload(data), budget=_Budget()), False)

    def test_registered_without_cancel_flag_reads_as_joined(self):
        for data in ({"sfbm": 1, "sfcx": 0}, {"sfbm": "1", "sfcx": "0"}, {"sfbm": 1}):
            with self.subTest(data=data):
                self.assertIs(self._joined(self._payload(data)), True)
                self.assertIs(self._joined(self._payload(data), budget=_Budget()), True)

    def test_unreadable_payload_stays_joined(self):
        # 认不出的形状按已报名处理：宁可漏报一次，也不重复提交
        for data in ({"bmsj": "2026-11-03 12:00:00"}, {"sfbm": None}, {"sfbm": ""}):
            with self.subTest(data=data):
                self.assertIs(self._joined(self._payload(data)), True)

    def test_empty_payload_reads_as_not_joined(self):
        for data in (None, {}, []):
            with self.subTest(data=data):
                self.assertIs(self._joined(self._payload(data)), False)

    def test_failed_query_keeps_the_three_state_none(self):
        # 查询没成功 ≠ 未报名；budget 模式必须回 None，否则会再发一次提交
        failed = {"code": 4001, "message": "身份验证失败", "data": None}
        self.assertIsNone(self._joined(failed, budget=_Budget()))
        self.assertIs(self._joined(failed), False)

    def test_failed_query_none_dict_or_bad_code_all_return_none_with_budget(self):
        """None 绝不能被当成未报名——否则会在结果未知时再提交一次。

        三种查询没成功的回包形状都必须：带 budget 回 None（三态），
        不带 budget 回 False（旧调用方的两态口径不变）。
        """
        # 1) 回包本身是 null（_post 解析出 None）
        with self.subTest(source="exception_none"):
            self.assertIsNone(self._joined(None, budget=_Budget()),
                              "带 budget：查询异常回 None")
            self.assertIs(self._joined(None), False,
                          "不带 budget：查询异常回落 False")
        # 2) 非 dict（如字符串）
        with self.subTest(source="non_dict"):
            self.assertIsNone(self._joined("oops", budget=_Budget()),
                              "带 budget：非 dict 回 None")
            self.assertIs(self._joined("oops"), False,
                          "不带 budget：非 dict 回落 False")
        # 3) code 不是 1（如 500 系统繁忙；_post 遇到网络异常也回 code=-1，走的是这一种）
        with self.subTest(source="bad_code"):
            failed = {"code": 500, "message": "系统繁忙", "data": None}
            self.assertIsNone(self._joined(failed, budget=_Budget()),
                              "带 budget：code!=1 回 None")
            self.assertIs(self._joined(failed), False,
                          "不带 budget：code!=1 回落 False")


class SignupReplyContractTests(unittest.TestCase):
    def setUp(self):
        self.replies = _load("signup-replies.json")

    def test_every_sample_is_classified_to_its_expected_kind(self):
        self.assertTrue(self.replies)
        for sample in self.replies:
            with self.subTest(kind=sample["kind"], message=sample["message"]):
                reply = classify_signup_reply(sample["code"], sample["message"])
                self.assertEqual(reply.kind, sample["kind"])
                self.assertIn(str(sample["code"]), reply.raw)
                self.assertIn(sample["message"], reply.raw, "日志里是完整原文")
                self.assertEqual(sample["http_status"], 200)

    def test_samples_cover_every_kind_the_classifier_can_return(self):
        covered = {sample["kind"] for sample in self.replies}
        self.assertEqual(covered, {"success", "not_open", "full", "conflict", "closed",
                                   "version", "stale_ts", "no_activity", "login_invalid",
                                   "unknown"})


if __name__ == "__main__":
    unittest.main()
