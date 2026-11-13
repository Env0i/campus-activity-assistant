# redo/zcode —— 重构审计补充轮的第二份独立重做（20261113-zcode-full）

- 执行方：ZCode 会话（主执行方＋11 次真实子代理派发＋8 次 SendMessage 续派，台账在 `.claude/results/20261113-zcode-full/agents.md`）
- 计划源：`.claude/plans/plan-20261113-refactor-audit-redo.yaml`（T0–T7 逐条执行）；本目录是总目标约束下的落点（yaml 的 redo/ 根目标整体移入 zcode/ 子目录，映射见第 4 节与 `00-boot.md` 第 7 节）
- 基线：`7e2d31c`；产品代码一律 `git show 7e2d31c:<路径>` 或基线树（tempfile.mkdtemp() 导出）读取，未读工作区产品文件
- 时间口径：美中时间 UTC−6（T0＝2026-11-12 09:05 CT），见 `00-boot.md`

## 1. 偏离声明

- **D1 审计者**：计划中 AA1/AA2 由指挥会话派另两个独立子代理；本环境改为主执行方派两位不同专家（证据收集者、遗留系统工程师）执行，AA3（策略对决推演师）与三级抽检（现实检验者）另派两名，四个审计角色互不相同、互不见对方意见。是否接受该替代由验收人裁定。
- **D2 时间口径**：所有时间戳用美中时间（UTC−6），格式 2026-11-12 10:05 CT；目录名日期是日历日期，与内部时间可能差一天，不追改。
- **D3 处置方式**：T7 不改 redo/ 根下他人文件，只写处置表与最小 patch 文本；本方产物（plan/**、extra/**）允许直接修正并复跑 verify。
- **D4 计划外增量**：T9、T10、AA3、攻防辩、三级抽检为本轮新增，单独放 extra/，不混入计划阶段一/二/三的产物。
- **D5 额度闸门口径**（补充，见 00-boot.md 第 5 节）：`zcode_tokens.py` 的累计数（开工前 828.44M）是项目历史累计；第 11 节闸门命令自带 `--since "<T0 本地时间>"`，故阈值按本轮自 T0 起的增量评估。按此口径本轮收尾时 113.49M，T8 因执行必越 1.2 亿硬线而跳过（见 BACKLOG 第 9 条）。

## 2. 盲做合规

T1–T5 交付（含其对账前置）完成于打开 supplement/、review/、redo/ 根他人文件之前；T6 对账时才首次打开 supplement/ 与 review/；redo/ 根他人交付自始至终未打开（T8 跳过）。第一轮五份证据文件（README/state-trace/ui-states/code-issues/inventory）按计划允许自 T1 起读取，开工时 SHA-256 记录在 00-boot.md 第 6 节。

## 3. 目录结构

```
redo/zcode/
  00-boot.md            开工核对（git 原文、专家清单全文、T0、用量、SHA-256、目录映射）
  README.md             本文件
  PLAN-RATIONALE.md     顺序依据（每条注出处）
  plan/                 计划阶段一/二/三产物（T0–T7）
    desktop.md / desktop.cites.jsonl    T1 桌面复核（257 条）
    phone.md   / phone.cites.jsonl      T2 手机页状态追踪（123 条）
    rules.md   / rules.cites.jsonl      T3 三端规则比对（106 条）
    grab.md    / grab.cites.jsonl       T4 grab 输出协议（118 条）
    prereq.md  / prereq.cites.jsonl     T5 重构前置清点（94 条）
    reconcile.md                        T6 四类对账（44 行）
    audit/AA1.md / audit/AA2.md         阶段二两份独立审计
    fix-round.md                        T7 逐条处置（44 条意见）
    scripts/                            verify_cites.py、phone_model_fields.mjs、esc_sites.mjs、grab_outputs.py、api_methods.py、spot_sample.py
    verify/                             每份交付的 verify_cites 输出、脚本输出、抽查明细
  extra/                计划外增量（D4）
    plan-redteam.md     T9 方案红队（八条判据）
    seams.md            T10 接缝清单（四类，含 T7 修正补记）
    mikado.md           T10 依赖树（24 节点，含 T7 修正补记）
    audit/AA3.md        AA3 方案对抗（六角度 21+2 条）
    defense.md          攻防辩（5 条挑战，作者回复逐字照录）
    spot-audit.md       三级抽检（5 条，只看证据）
```

## 4. plan/ 与 extra/ 的映射表

| 计划任务 | 产物（plan/） | 说明 |
|---|---|---|
| T0 引用格式与核对脚本 | scripts/verify_cites.py（自检 plan/verify/selftest.txt）；本 README 对应 yaml 的 redo/README.md | F1/F2 全字段核对＋md 引用核对，三条坏样例自检通过 |
| T1 桌面复核 | desktop.md + desktop.cites.jsonl | state-trace 全部「核」行逐行结论；U6/U11/U12 调用链与补测；两面板四段比对 |
| T2 手机页状态追踪 | scripts/phone_model_fields.mjs + phone.md + phone.cites.jsonl | 55 字段×写入 154/读取 296；12 个等待操作×七出口 |
| T3 三端规则比对 | rules.md + rules.cites.jsonl | 9 条规则×三端锚点＋差异三分类＋测试比对 |
| T4 grab 输出协议 | scripts/grab_outputs.py + grab.md + grab.cites.jsonl | 输出种类/解析方、退出码、环境变量、写文件、对照测试草案 |
| T5 重构前置清点 | scripts/esc_sites.mjs + scripts/api_methods.py + prereq.md + prereq.cites.jsonl | 行为测试缺口、Api 153/60 归块、esc 115 落点、字符串桥接名比对 |
| T6 对账 | reconcile.md | 对象＝第一轮五份＋supplement＋review；四类 44 行 |
| AA1/AA2 | audit/AA1.md、audit/AA2.md | 独立审计，互相不见意见 |
| T7 返修 | fix-round.md | 44 条意见逐条处置；返修后 verify 全过 |
| T9（增量） | extra/plan-redteam.md | 八条判据逐条判定 |
| T10（增量） | extra/seams.md、extra/mikado.md | 接缝四类；依赖树 24 节点 |
| AA3（增量） | extra/audit/AA3.md | 可行性六角度 |
| 攻防辩（增量） | extra/defense.md | 5 条回原作者，逐字照录 |
| 三级抽检（增量） | extra/spot-audit.md | 5 条只看证据 |
| T8 三方对照 | **未产出** | 额度硬闸跳过，理由见 BACKLOG 第 9 条 |

## 5. 交付计数（收尾时点）

| 交付 | 条目数 | verify |
|---|---|---|
| desktop | 257 | 0 失败 |
| phone | 123 | 0 失败 |
| rules | 106（含 T7 补做 r-085..r-106） | 0 失败 |
| grab | 118 | 0 失败 |
| prereq | 94（含 T7 补做 q-093/094） | 0 失败 |
| 合计 | 698 | 全过（plan/verify/*.txt） |
