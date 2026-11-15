/* 两份认阶段改前改后的逐格对照（纯函数层）。
 * 用法（仓库根）：
 *   node design/evidence/2026-11-15/component-machine/scripts/phase_grid.mjs <开工提交短哈希> [新代码那一方的提交引用]
 * 旧函数永远从第一个提交引用经 git show 取原文；不给第二个引用时新函数读当前工作区，
 * 给了就同样经 git show 取（拿开工提交对开工提交跑一次，输出必须是 0 组不同，用来证明
 * 脚本自己没毛病）。
 * 输入网格：download.state 取空、downloading、verifying、installed、failed、cancelled；
 * status 取 missing、checking、outdated、failed、ready；ready、available、running 各取
 * 真假——共 240 组。分别用两边的 phonePhase、ocrPhase 求值，输出网格大小与不同的组数
 * （按函数分列），不同大于 0 退出 1。只用仓库路径与提交引用，不写主机路径。 */
import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const REPO = path.resolve(HERE, "../../../../..");

const OLD_FILES = [
  "local/ui/features/phone-access/state.js",
  "local/ui/features/components/state-ocr.js",
];
/* 新代码多了状态机文件：认阶段适配 import 它。从提交取时若那一份还没有这个文件就跳过。 */
const NEW_EXTRA_FILES = ["local/ui/features/components/state-machine.js"];

const IMPORT_RE = /^\s*import\s*\{[^}]*\}\s*from\s*"[^"]+"\s*;\s*$/gm;
const EXPORT_DECL_RE = /^(\s*)export\s+(?=(?:async\s+)?(?:function|const|let|var|class)\b)/gm;
const EXPORT_LIST_RE = /^\s*export\s*\{[^}]*\}\s*;\s*$/gm;

function strip(src) {
  return src.replace(IMPORT_RE, "").replace(EXPORT_DECL_RE, "$1").replace(EXPORT_LIST_RE, "");
}

function fromRef(ref, rel) {
  return execFileSync("git", ["show", ref + ":" + rel],
                      { cwd: REPO, maxBuffer: 16 * 1024 * 1024 }).toString("utf8");
}

function fromWorkspace(rel) {
  return readFileSync(path.join(REPO, rel), "utf8");
}

function loadSide(files) {
  const src = files.map(([rel, text]) => text).map(strip).join("\n");
  const sandbox = new Function(src + "\n;return { phonePhase: phonePhase, ocrPhase: ocrPhase };");
  return sandbox();
}

const baseRef = process.argv[2];
const newRef = process.argv[3] || "";
if (!baseRef) {
  console.error("用法：node phase_grid.mjs <开工提交短哈希> [新代码那一方的提交引用]");
  process.exit(2);
}

const oldSide = loadSide(OLD_FILES.map((rel) => [rel, fromRef(baseRef, rel)]));

const newFiles = [];
if (newRef) {
  for (const rel of NEW_EXTRA_FILES) {
    try {
      newFiles.push([rel, fromRef(newRef, rel)]);
    } catch (err) {
      /* 那一份还没有状态机文件：旧适配不 import 它，跳过 */
    }
  }
  for (const rel of OLD_FILES) newFiles.push([rel, fromRef(newRef, rel)]);
} else {
  for (const rel of NEW_EXTRA_FILES) newFiles.push([rel, fromWorkspace(rel)]);
  for (const rel of OLD_FILES) newFiles.push([rel, fromWorkspace(rel)]);
}
const newSide = loadSide(newFiles);

const DL_STATES = ["", "downloading", "verifying", "installed", "failed", "cancelled"];
const STATUSES = ["missing", "checking", "outdated", "failed", "ready"];
const BOOLS = [false, true];

let groups = 0;
let diffPhone = 0;
let diffOcr = 0;
const samples = [];
for (const dl of DL_STATES) {
  for (const status of STATUSES) {
    for (const ready of BOOLS) {
      for (const available of BOOLS) {
        for (const running of BOOLS) {
          groups += 1;
          const st = { running: running };
          const row = { download: { state: dl }, status: status,
                        ready: ready, available: available };
          const oldPhone = oldSide.phonePhase(st, row);
          const newPhone = newSide.phonePhase(st, row);
          const oldOcr = oldSide.ocrPhase(row);
          const newOcr = newSide.ocrPhase(row);
          if (oldPhone !== newPhone) {
            diffPhone += 1;
            if (samples.length < 10) {
              samples.push({ key: "phonePhase", dl: dl, status: status, ready: ready,
                             available: available, running: running,
                             old: oldPhone, new: newPhone });
            }
          }
          if (oldOcr !== newOcr) {
            diffOcr += 1;
            if (samples.length < 10) {
              samples.push({ key: "ocrPhase", dl: dl, status: status, ready: ready,
                             available: available, running: running,
                             old: oldOcr, new: newOcr });
            }
          }
        }
      }
    }
  }
}

console.log("网格大小：" + groups + " 组"
  + "（download.state " + DL_STATES.length + " × status " + STATUSES.length
  + " × ready/available/running 各 " + BOOLS.length + " 档）");
console.log("旧代码基准：" + baseRef
  + "；新代码：" + (newRef ? "提交 " + newRef : "当前工作区"));
console.log("phonePhase 不同的组数：" + diffPhone);
console.log("ocrPhase 不同的组数：" + diffOcr);
console.log("不同的组数合计：" + (diffPhone + diffOcr));
for (const sample of samples) {
  console.log("不同组示例：" + JSON.stringify(sample));
}
process.exit(diffPhone + diffOcr > 0 ? 1 : 0);
