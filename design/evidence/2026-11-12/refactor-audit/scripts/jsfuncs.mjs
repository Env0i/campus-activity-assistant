// 量 JS 函数的行数。measure.py 会调它；也可以单独跑：
//   node design/evidence/2026-11-12/refactor-audit/scripts/jsfuncs.mjs local/ui/app.js [更多文件…]
// 输出一份 JSON：[{ file, lines, balanced, functions: [{ name, kind, start, end, lines, depth }] }]
// 口径和误差见上一级目录的 README.md「C1 ③」。

import { readFileSync } from "node:fs";
import { findFunctions } from "./jsscan.mjs";

const files = process.argv.slice(2);
const out = [];
for (const file of files) {
  const src = readFileSync(file, "utf8");
  // 物理行数：和 wc -l 一致（数换行符），末行没有换行时补一行。
  const newlines = (src.match(/\n/g) || []).length;
  const lines = src.length && !src.endsWith("\n") ? newlines + 1 : newlines;
  const { funcs, balanced } = findFunctions(src);
  out.push({
    file: file.replace(/\\/g, "/"),
    lines,
    balanced,
    functions: funcs.map((f) => ({
      name: f.qualname, kind: f.kind, start: f.start, end: f.end, lines: f.lines, depth: f.depth,
    })),
  });
}
process.stdout.write(JSON.stringify(out));
