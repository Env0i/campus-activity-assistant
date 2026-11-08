# PATCHES — 2026-11-08 夜班（L7/L8 收录轮）

**本夜班补丁 = 0。** 本轮任务是把 L7（测试卫生）与 L8（无障碍）分析素材转成正式报告收录，不改代码、不改测试。各盘点的补丁判定结论如下。

## L6 docs/ 可出补丁 = 0 条

- 39 条死链全部在 docs/README.md:58-96 迁移对照表的旧路径列，右列即新路径；删改旧路径列会破坏对照功能，该表属记录性质文档。
- 指向：`../doc-refs.md` 「补丁判定：docs/ 下可出补丁 = 0 条」专节。

## L7 可出补丁 = 0 条

- 唯一候选 local/tests/test_component_builder.py:25（一行 2 处 `<tmp>`）经判定不是夹具路径，而是**被测的非法输入样本**：字面量传入 `builder.output_root()` 并断言 `assertRaises(ValueError)`，替换成 `tempfile.gettempdir()` 会把它变合法输入、破坏断言、测试意图崩坏。
- 其余 4 处 `<tmp>` 均为 docstring/注释，不执行；其中 test_retry_policy.py:5 的死链引用属「旧记录不追改」范畴。
- 指向：`../test-hygiene.md` ① 逐处判定表与「补丁判定专节：L7 可出补丁 = 0 条」；口径确认条目 **DEFERRED-L7-1** 同在该节（AGENTS.md「`<tmp>` 缺陷」字面规则是否涵盖被测非法输入样本，待用户确认）。

## L8 未派生补丁

- L8 为静态审计报告：无名称 button 0/129、缺名称输入 0/30，仅 aria-labelledby 无效 1 处（#tour-card）与 aria-modal 增强项；问题清单供后续排期，本轮不改 UI。
- 指向：`../a11y-names.md` 「问题清单」与「最严重 5 条」。
