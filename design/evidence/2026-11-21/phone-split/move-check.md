# 手机页拆分逐字核对（move_check）

- 结论：**PASS（0 项失败）**
- 原文来源：`git show HEAD:local/ui/m/app.js`（非空行 3296 行）
- 新文件清单（按 `local/ui/m/index.html` 顺序，共 12 份）：`model.js`、`model-conflict.js`、`model-list.js`、`model-run.js`、`model-relogin.js`、`ui-session.js`、`ui-status.js`、`ui-list.js`、`ui-sync.js`、`ui-plan.js`、`ui-relogin.js`、`ui-shell.js`
- PhoneModel 成员核对：101 个
- DOM 顶层声明（函数与 const）核对：72 个
- 新文件非空行合计：3337 行（含新增文件头注释 24 行）

全部 PhoneModel 成员、DOM 顶层声明及非空行频次均与 HEAD 原文逐字一致。
