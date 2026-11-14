## review2 表 F 独立复算

### 存在性

| 项目 | 结果 |
|---|---|
| pyproject.toml | 无 |
| setup.cfg | 无 |
| package.json | 无 |
| .editorconfig | 无 |
| .pre-commit-config.yaml | 无 |
| mypy.ini | 无 |
| .mypy.ini | 无 |
| .coveragerc | 无 |
| .eslintrc | 无 |
| .eslintrc.js | 无 |
| .eslintrc.json | 无 |
| .eslintrc.yml | 无 |
| eslint.config.js | 无 |
| eslint.config.mjs | 无 |
| .prettierrc | 无 |
| .prettierrc.json | 无 |
| .prettierrc.toml | 无 |
| prettier.config.js | 无 |
| .githooks/ | 无 |
| .github/workflows/ | 无 |

### requirements 文件（总行 / 非注释非空 / 未锁 == 行数）

- `local/requirements-advanced-ocr.txt`：3 / 3 / 3；未锁：ddddocr>=1.6.1；onnxruntime>=1.17；pyinstaller>=6.0
- `local/requirements-advanced-phone.txt`：2 / 2 / 2；未锁：segno>=1.6；pyinstaller>=6.0
- `local/requirements.txt`：14 / 7 / 2；未锁：playwright>=1.40；pillow>=9.0
- `requirements-dev.txt`：3 / 1 / 0
- `server/requirements.txt`：15 / 2 / 2；未锁：playwright>=1.40；ddddocr>=1.6.1

### tools/release.py 单元测试调用与 --prepare 行

- 含 unittest/pytest/compileall 的行：无
- 含 --prepare 的行数：22（tools/release.py:8 起）

- tools/code_shape/check.py 存在：True

### ruff 字符串查找（git 跟踪文本文件，共 21 行）

- AGENTS.md:112
- AGENTS.md:115
- AGENTS.md:224
- AGENTS.md:227
- design/proposals/engineering-refactor.md:67
- design/proposals/engineering-refactor.md:74
- local/tests/test_code_shape.py:228
- local/tests/test_code_shape.py:229
- local/tests/test_code_shape.py:233
- local/tests/test_code_shape.py:234
- local/tests/test_code_shape.py:244
- local/tests/test_code_shape.py:249
- local/tests/test_code_shape.py:250
- local/tests/test_code_shape.py:255
- local/tests/test_code_shape.py:256
- local/tests/test_code_shape.py:257
- local/tests/test_code_shape.py:262
- local/tests/test_code_shape.py:270
- requirements-dev.txt:3
- ruff.toml:1
- ruff.toml:3

## 复核说明（测试自动化工程师，全量核）

- 21 项存在性 test -e 逐项复核全「无」；requirements 三列数逐文件复核全等（3/3/3、2/2/2、14/7/2、3/1/0、15/2/2）并列出锁定行位置；.githooks 与 .github 均不存在；ruff 查找 21 行逐行一致并抽 22 行复核；release.py 无 unittest/pytest/compileall 行（grep 退出码 1）、--prepare 22 行（:8 起）。
- 追加事实：--prepare 分支（tools/release.py:1307-1315 调 stage_local_assets）及其调用的 build_exe/build_advanced/build_installer 三个被调脚本内同样无测试调用语句。
