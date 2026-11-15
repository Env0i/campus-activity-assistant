# 重新登录对话框的接线：搬之前与搬之后都在守

搬文件最怕的是「接线被搬丢了，测试却没反应」。这份文件给两件事：一是 `wireRelogin` 的每一处绑定与「登录按钮」那一处接线各有一条自己的断言（换掉这一行就必须变红），二是这些断言在**搬之前**与**搬之后**都成立。

## 一、21 处接线

测试文件 `local/tests/test_ui_relogin_wiring.py`，每处一句断言，断的是用户看得到的结果（对话框开没开、落到哪一步、按钮可不可点）或发出的桥接请求。变异脚本 `scripts/mutate_wiring.py` 把这一处绑定换成空动作，跑对应用例。

| 接线（控件 / 事件） | 守它的用例 | 搬之前第一条失败断言 | 搬之后第一条失败断言 | 两面是否一致 |
|---|---|---|---|---|
| `#btn-rl-auto` click | `test_auto_login_button_asks_the_backend_once` | `Lists differ: ['advanced_compo…` | 同左 | 同 |
| `#btn-lg-next` click | `test_next_button_starts_relogin_with_the_typed_account` | 用例名失败（请求没发出） | 同左 | 同 |
| `#btn-rl-code` click | `test_code_button_submits_the_typed_code` | 用例名失败 | 同左 | 同 |
| `#btn-rl-browser` click | `test_browser_button_closes_then_opens_the_school_page` | `True is not false : 改用浏览器登录要先关…` | 同左 | 同 |
| `#btn-bad-browser` click | `test_bad_password_browser_button_also_opens_the_school_page` | `True is not false` | 同左 | 同 |
| `#btn-bad-update` click | `test_update_password_button_returns_to_the_form` | `'bad' != 'login'` | 同左 | 同 |
| `#btn-lg-back` click | `test_back_button_returns_from_the_captcha_step` | `'cap' != 'login'` | 同左 | 同 |
| `#btn-lg-webopen` click | `test_school_page_button_waits_for_the_browser` | `'login' != 'lgwait'` | 同左 | 同 |
| `#btn-rl-cancel` click | `test_cancel_closes_the_dialog_and_cancels_the_flow` | `True is not false : 点「取消」要把对话框…` | 同左 | 同 |
| `#btn-rl-done` click | `test_done_closes_the_dialog_without_touching_the_backend` | `True is not false` | 同左 | 同 |
| `#lg-here` click | `test_way_card_here_shows_the_form_again` | `'browser' != 'here'` | 同左 | 同 |
| `#lg-web` click | `test_way_card_browser_hides_the_form` | `'here' != 'browser'` | 同左 | 同 |
| `#lg-eye` click | `test_eye_button_shows_the_password_as_plain_text` | `'password' != 'text'` | 同左 | 同 |
| `#rl-user` input | `test_typing_the_account_enables_next` | `True is not false : 账号输入后「下一步」…` | 同左 | 同 |
| `#rl-pass` input | `test_typing_the_password_enables_next` | `True is not false : 密码输入后「下一步」…` | 同左 | 同 |
| `#rl-pass` keydown Enter | `test_enter_in_the_password_field_submits_the_form` | 用例名失败 | 同左 | 同 |
| `#rl-save` change | `test_ticking_save_rewrites_the_explanation` | `'勾了保存' not found in '没勾保存：密码只用…` | 同左 | 同 |
| `#rl-code` input | `test_four_digit_code_enables_the_login_button` | `True is not false : 四位验证码要能点「登录」` | 同左 | 同 |
| `#rl-code` keydown Enter | `test_enter_in_the_code_field_submits_it` | 用例名失败 | 同左 | 同 |
| `#dlg-relogin` cancel | `test_escape_on_the_dialog_closes_it` | `True is not false : Esc 要能把对话框…` | 同左 | 同 |
| `#btn-login` click（`app.js` → 搬后 `main.js`） | `test_expired_login_button_opens_the_relogin_dialog` | `False is not true : 点「登录」要把重新登…` | 同左 | 同 |

**汇总：搬之前 21 处全部变红、存活 0；搬之后同样 21 处全部变红、存活 0，每一处红出来的用例与第一条失败断言都一样。**

搬之前的量法：把开工 HEAD `fb3e035` 导出成一棵树，把本批新写的接线测试补进那棵树（测试是本批新加的，老树上没有），再照同一份清单变异。搬之后的量法：直接在工作区做。

## 二、真加载冒烟（三条断言、两条用例）

搬文件还会碰上一类拼接式测试看不见的毛病：模块里定义的名字没挂回 `window`，普通脚本在加载期就找不到。这类只有真加载能测。同文件末尾 `NativeLoadWireTests` 里两条用例、三条断言：

| 用例 | 断的是哪三条 | 搬之前 | 搬之后 |
|---|---|---|---|
| `test_native_login_button_opens_and_cancel_closes_the_dialog` | ① 登录结论为已失效时点「登录」，对话框要打开；② 点「取消」要关上 | 通过 | 通过 |
| `test_native_narrow_window_keeps_the_login_button_working` | ③ 430×820 窄窗口真加载，普通脚本阶段不抛错、登录按钮仍能打开对话框 | 通过 | 通过 |

## 三、把接线删掉就红（副本里做的）

在副本里删掉 `main.js` 里那两行接线（`$("#btn-login").addEventListener("click", loginEntry);` 与 `wireRelogin();`），真加载冒烟第一条立刻变红：

```
FAIL: test_native_login_button_opens_and_cancel_closes_the_dialog
AssertionError: False is not true : 真加载下点「登录」要打开对话框
```

这条反证说明冒烟不是空跑：接线真的搬丢了，它就会红。

## 四、复跑命令

```bash
# 搬之后：21 处接线逐处变异
python -B design/evidence/2026-11-15/login-move/scripts/mutate_wiring.py --phase post
# 搬之前：用开工 HEAD 的导出树量
python -B design/evidence/2026-11-15/login-move/scripts/mutate_wiring.py --phase pre --tree <导出树>
# 接线测试本身（含三条真加载）
python -B -m unittest discover -s local/tests -p test_ui_relogin_wiring.py
```
