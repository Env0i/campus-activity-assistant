# 交接回执:2026-11-05 夜间审计 + 标准化(Codex/GLM → Claude)

写单人:审计代理(模型 GLM-5.3-Flash)。本文件不入库(沿用 B2 决定)。
**接手第一课:本回执的每一条声明都可能错(11-04 回执就错 B5/B7 两处)。先跑 §0 的对账命令,再信正文。**

## 0. 接手自检(先跑这个,对不上就停下来查)

```bash
cd <工作区根>
git branch --show-current        # 应为 chore/standardize-20261105
git log --oneline -2             # 应为 189bf27(chore(std): 批4b 补遗) → 099ded3(chore: 收第一轮五修)
git log --oneline 4ec0b3d..HEAD | wc -l   # 应为 26(1 笔收五修 + 25 笔 std)
git rev-parse origin/main        # 应仍为 4ec0b3d…(没有 push 过)
git tag | wc -l                  # 应为 0
git -c core.quotepath=false status --porcelain | wc -l   # 应为 27(全部是 11-04 的存量未提交改动)
```
工作区全量验证(应全绿):
```bash
python -X utf8 -m unittest discover -s local/tests -p "test_*.py"   # 1699 OK, skipped=4
python -m pytest server/tests -q                                     # 122 passed
node server/bot/test_bot_runtime.js && node server/bot/test_handled_messages.js   # 37 项 0 败 / 8 过
python -m compileall -q local server tools && node --check local/ui/app.js
```

## 1. 仓库现状(两轮干了什么)

- **第一轮(审计)**:469 文件五层审计,报告在 `reports/`(八件套+COVERAGE 469 行覆盖账)。修复了五处已复现缺陷(<tmp> 夹具、时钟双读、组件查询崩溃、update.js 两处文案丢失),每个修复都有「改前红/改后绿/反向对照」三件套,补丁在 `reports/PATCHES/fix-*.patch`。密钥零泄漏,硬边界无违反。
- **第二轮(标准化)**:立了八节家规 `reports/STANDARD.md`,按目录分批整改,**已按批提交 26 笔**(099ded3 之后,每笔正文标注依据的 STANDARD 节),台账 `reports/STANDARDIZATION.md` 469 行逐文件对齐(合规 147/已改 53/保留 120/不适用 149)。
- **工作树里还躺着的未提交改动 = 27 项存量(11-04 你自己留的)+ 5 处本代理故意不入库的文件**,见 §3。

## 2. 先读哪些文件(按序)

1. `reports/STANDARDIZATION.md` — 469 行台账 + 提交映射(C1-C25 ↔ sha)+ 未完成项清单(8 条,全部带前提)
2. `reports/AUDIT.md` — 第一轮总账(五层各一句结论)
3. `reports/FINDINGS.md` — 全部发现逐条(现象/证据/根因/严重度/修没修)
4. `reports/PROTOTYPE-GAP.md` — 99 处原型差距逐条(**72 处未实现=待排期的工程,不是 bug**)
5. `reports/DECISION-CHECK.md` — D1-D9/B 组/两份 plan 落地核对 + C1-C9 判据冲突
6. `reports/RISK.md`、`reports/BACKLOG.md`、`reports/DEFERRED.md` — 盲区/卡住项/留人定项
7. `reports/EVIDENCE-INDEX.md` — 全部命令与输出(要复核任何结论从这里找命令)
8. `.claude/handoff/2026-11-04-receipt.md` — 上一份回执,**注意 B5/B7/C1 三处标注与仓库现状矛盾**(见 §4)

## 3. 工作区里未提交的东西(一个字没动,别当垃圾清了)

- **27 项存量**:11-04 会话留下的未提交改动(UI/文档/测试/证据),内容合法,等你自己决定提交。
- **5 处本代理故意不入库**(有前提,不是漏):
  1. `local/ui/views/relogin.js` 全部——存量 N1 接线 + 第一轮 Fix E(空 flow 去重)+ :74 批注;单提会得到引用不存在代码的坏树,必须随 N1 一起提交。
  2. `local/ui/views/update.js`——存量文案重写 + Fix D 渲染修复,同上纠缠。
  3. `local/tests/test_ui_contract.py` 的 Fix E 用例——依赖 relogin N1。
  4. `local/tests/test_application_services.py`、`local/tests/test_phone_ui.py` 的 Fix A 遗留 hunk——嵌在存量里。
  5. `design/specs/assistance-panels.md` §3 状态表重写——与存量 3 行上下文纠缠。
  这五处对应的 patch 在 `reports/PATCHES/std-4a/8b/…` 与 `fix-*` 里都有,想分开提交需先提交存量。

## 4. 已知的坑与未了事项(全部带前提,不是遗漏)

1. **交接矛盾待你澄清**:11-04 回执说 B5(验证码文案)完成、B7(gui.py 删除)完成、C1(规格红线)改写——仓库里三处都没做。根因疑似 11-04 回执自述的「中途清空重做」还原后未重做。重做还是改回执,需人定。
2. **服务器行为类修复全部冻结**:F-08(登录失效判定只认 4001)/F-09(时区)/F-10(404 连击序)/F-11(is_joined 三态)/原子写——改代码容易,但没有服务器真实回归能力,动了就是盲改。
3. **条款 r5 没做**:入口路径+「直发→直接提交」清理会触发条款升版和全体重新同意,你拍板过「只记录未排期」。条款正文(`docs/USER_AGREEMENT.md`、`docs/PRIVACY_POLICY.md`、`local/ui/index.html` 内嵌)今晚一字未动,别顺手改。
4. **`gui.py` 删除**(B7)没执行,和第 1 条绑在一起。
5. **BL-1**:v1.1.1「已发布」本机无 tag 可追溯,需要 GitHub Release 侧证据。
6. **72 条原型缺口**:清单在 PROTOTYPE-GAP.md,最大的三块=手机页整块/计划栏结果态/设置抽屉。做之前先读台账里「phone_service 等服务层未深审」的提醒。

## 5. 技术坑(接手就会踩)

- `local/tests/test_runtime_bundle.py` 必须用 `PYTHONPATH=local` 跑,否则 import 就炸(不是代码坏了)。
- `<tmp>` 是文档占位符,永远别写进代码;测试里允许的唯一例外是 `test_component_builder.py:25` 的负向输入(断言必须拒绝它)。
- 扫 except-pass 要用多行正则,单行正则会漏(第一轮教训);行尾 `# noqa` 注释也是盲区。
- 本机测试基线:1699 例,只有 1 个已知间歇 flake(`test_login_state_hours_left_is_always_none` 的 Windows 临时目录句柄竞争,单跑必绿)。
- 中文路径/输出在这个环境有 GBK 显示问题,跑命令带 `PYTHONIOENCODING=utf-8`。

## 6. 红线(AGENTS.md + 本轮延续的纪律)

只服务本人账号、不批量占位;不 push/不合并/不打 tag/未经授权不 commit;不读 .env 与 data 目录;历史记录(decisions/evidence/CHANGELOG 已发布段)不追改;`reports/` 与本 handoff 不入库。
