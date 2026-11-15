// 整理补丁的记号序列比对：六个文件在「整理之前」与「整理之后」两个提交里的
// tokenize 记号序列（tools/code_shape/jslex.mjs，注释不进记号）必须完全相同。
// 两个提交引用都经 git show 读，不读工作区——仓库里就能复跑。
//
// 用法（仓库根执行）：
//   node design/evidence/2026-11-15/ocr-panel-move/scripts/tidy_tokens.mjs 9c3fd44 <整理那一笔的短哈希>
// 第二个引用取自 git log（整理那一笔）；全部相同退出 0，有任何不同退出 1。
import { execFileSync } from "node:child_process";
import { tokenize } from "../../../../../tools/code_shape/jslex.mjs";

const FILES = [
  "local/ui/legacy-globals.js",
  "local/ui/features/phone-access/actions-panel.js",
  "local/ui/features/components/state.js",
  "local/ui/features/login/state-recovery.js",
  "local/ui/features/phone-access/state.js",
  "local/ui/views/settings.js",
];

const show = (ref, rel) => execFileSync("git", ["show", `${ref}:${rel}`],
  { encoding: "utf8", maxBuffer: 64 * 1024 * 1024 });
const shape = (toks) => toks.map((t) => t.type + ":" + t.value);

const [before, after] = process.argv.slice(2);
if (!before || !after) {
  console.error("用法：node design/evidence/2026-11-15/ocr-panel-move/scripts/tidy_tokens.mjs <整理之前的提交> <整理之后的提交>");
  process.exit(1);
}

let sameCount = 0;
for (const rel of FILES) {
  const a = shape(tokenize(show(before, rel)));
  const b = shape(tokenize(show(after, rel)));
  const same = a.length === b.length && a.every((v, i) => v === b[i]);
  if (same) sameCount += 1;
  console.log(`${same ? "相同" : "不同"}  ${rel}  记号数 ${a.length} → ${b.length}`);
  if (!same) {
    for (let i = 0; i < Math.max(a.length, b.length); i += 1) {
      if (a[i] !== b[i]) {
        console.log("  第 " + i + " 个记号不同：整理前 " + a[i] + " vs 整理后 " + b[i]);
        break;
      }
    }
  }
}
console.log(`比对完成：${sameCount}/${FILES.length} 个文件的记号序列完全相同`);
if (sameCount !== FILES.length) process.exit(1);
