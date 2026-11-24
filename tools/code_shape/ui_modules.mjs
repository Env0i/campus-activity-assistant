// 模块图守卫：只读清点 local/ui 的 ES Modules，向标准输出打印一份 JSON 报告。
//
// 量什么：
//   modules             模块清单与各自的层（文件名规则：state-*/view-*/actions-*、
//                       shared/ 公共层；main.js 是入口 entry，legacy-globals.js 是过渡期
//                       挂回 window 的桥 bridge；未按规则命名的记 unclassified）
//   imports             每个模块引入了哪些名字、从哪来
//   cycles              顶层循环引用（有就列出环；esm-verify H3：整张模块图起不来）
//   missing_imports     「用了别的模块定义的名字却没有 import」的清单
//   layer_violations    违反层规则的引用（编排层与入口、桥不限；公共层只引公共层；
//                       状态层只引公共层和状态层；视图层可引公共层、状态层、视图层）
//   plain_globals_used  模块直接用到的普通脚本全局名字（过渡期允许，逐项列出）。入口
//                       main.js 不进这份清单——它是过渡期的桥，对普通脚本全局名字的
//                       引用就是迁移机制本身（启动调用、放排队事件），全部迁完时它消失
//   legacy_globals_attached  legacy-globals.js 挂到 window 的名字（过渡期清单）
//   unused_legacy_globals    挂出去却没有任何普通脚本在用的名字（有就必须删）
//   unattached_module_names  普通脚本引用了「只在模块里定义」的名字、这个名字又不在挂回
//                            名单里。拼接成一个大文件时模块名恰好进了全局，这类缺陷测试
//                            发现不了，真加载下是 ReferenceError，点到了才坏
//
// 期望值 tools/code_shape/ui_modules_expect.json 由本脚本生成，不手写：
//   node tools/code_shape/ui_modules.mjs --expect > tools/code_shape/ui_modules_expect.json
// 五类问题必须为空；两份清单与实际逐项相等，多一项少一项都红（local/tests/architecture/test_ui_layers.py）。
// 词法复用同目录的 jslex.mjs 与 jsscan.mjs，名字分析复用 ui_refs.mjs 导出的函数。
//
// 从仓库根运行：node tools/code_shape/ui_modules.mjs [--expect]

import { readFileSync } from "node:fs";
import { join } from "node:path";
import { pathToFileURL } from "node:url";

import { analyzeFile, indexHtmlTags, moduleImports, scanUses, topDefs } from "./ui_refs.mjs";

const UI = "local/ui";
const ENTRY = "main.js";
const BRIDGE = "legacy-globals.js";

// 模块的层（文件名规则）。文件名决定层：state.js / state- 开头是状态层，
// view- 视图层，actions- 编排层；shared/ 下单算公共层。
export function moduleLayer(rel) {
  if (rel === ENTRY) return "entry";
  if (rel === BRIDGE) return "bridge";
  if (rel.startsWith("shared/")) return "shared";
  const base = rel.slice(rel.lastIndexOf("/") + 1);
  if (base === "state.js" || base.startsWith("state-")) return "state";
  if (base === "view.js" || base.startsWith("view-")) return "view";
  if (base === "actions.js" || base.startsWith("actions-")) return "actions";
  return "unclassified";
}

// 普通脚本的目标层（供层规则判定）：按目录映射。root 是 app.js、led.js 所在，
// 只有编排层、入口与桥可以引用。
function plainLayer(rel) {
  if (rel.startsWith("state/")) return "state";
  if (rel.startsWith("views/")) return "view";
  if (rel.startsWith("controllers/")) return "actions";
  return "root";
}

// 层规则：编排层与入口、桥不限；公共层只引公共层；状态层只引公共层和状态层；
// 视图层可引公共层、状态层、视图层；没按文件名规则命名的模块只许引公共层。
function mayReference(from, to) {
  if (from === "entry" || from === "bridge" || from === "actions") return true;
  if (from === "unclassified") return to === "shared";
  if (from === "shared") return to === "shared";
  if (from === "state") return to === "shared" || to === "state";
  if (from === "view") return to === "shared" || to === "state" || to === "view";
  return false;
}

// 与 ui_refs.mjs 的 pageFiles 同一口径，但建图容忍顶层循环：ui_modules 的职责是把
// 环「列出来」，不是像拼接夹具那样遇环直接报错退出。
function pageFilesTolerant() {
  const tags = indexHtmlTags(join(UI, "index.html"));
  const plain = [];
  const entries = [];
  for (const t of tags) {
    if (t.module) entries.push(t.src);
    else plain.push(t.src);            // led.js 会被真实页面加载，普通脚本全局名字的定义集包含它
  }
  if (entries.length > 1) throw new Error(`index.html 有多个模块入口：${entries.join(", ")}`);
  const read = (rel) => readFileSync(join(UI, rel), "utf8");
  const moduleRels = [];
  const seen = new Set();
  const visit = (rel) => {
    if (seen.has(rel)) return;
    seen.add(rel);
    for (const imp of moduleImports(rel, read(rel))) visit(imp.from);
    moduleRels.push(rel);
  };
  if (entries[0]) visit(entries[0]);
  const files = plain.map((rel) => ({ rel, isModule: false, src: read(rel) }));
  for (const rel of moduleRels) files.push({ rel, isModule: true, src: read(rel) });
  return files;
}

function analyzeAll() {
  const files = pageFilesTolerant().map((item) => {
    const file = { rel: item.rel, isModule: item.isModule,
      layer: item.isModule ? moduleLayer(item.rel) : plainLayer(item.rel),
      src: item.src, ...analyzeFile(item.src) };
    file.defs = topDefs(file);
    file.skip = new Set(file.defs.map((d) => d.tok));
    return file;
  });
  // 名字 → 定义信息：普通脚本在前、模块图随后（pageFiles 的顺序），跨文件重名记第一处。
  const names = new Map();
  for (const f of files) {
    for (const d of f.defs) {
      if (names.has(d.name) && names.get(d.name).file === f.rel) continue;
      if (!names.has(d.name)) {
        names.set(d.name, { file: f.rel, isModule: f.isModule, layer: f.layer });
      }
    }
  }
  return { files, modules: files.filter((f) => f.isModule),
    plainFiles: files.filter((f) => !f.isModule), names };
}

// 每个模块的具名导入：名字 → 来源；顺带留下报表用的 import 明细与引用扫描结果。
function collectModuleImports(modules, names) {
  const importInfo = {};
  for (const f of modules) {
    const imported = new Map();
    importInfo[f.rel] = [];
    for (const imp of moduleImports(f.rel, f.src)) {
      importInfo[f.rel].push({ names: imp.names, from: imp.from });
      for (const n of imp.names) imported.set(n, imp.from);
    }
    f.imported = imported;
    f.refs = scanUses(f, names, f.skip);
  }
  return importInfo;
}

// 顶层循环引用：在模块导入图上找环，列出每条环的文件链（同一来源去重，避免同环重复列出）。
function findCycles(modules) {
  const graph = new Map(modules.map((f) => [f.rel, [...new Set(f.imported.values())]]));
  const cycles = [];
  const done = new Set();
  const stack = [];
  const visit = (rel) => {
    if (done.has(rel)) return;
    if (stack.includes(rel)) {
      cycles.push(stack.slice(stack.indexOf(rel)).concat(rel));
      return;
    }
    stack.push(rel);
    for (const dep of graph.get(rel) || []) visit(dep);
    stack.pop();
    done.add(rel);
  };
  for (const rel of graph.keys()) visit(rel);
  return cycles;
}

// 用了别的模块定义的名字却没有 import；违反层规则的引用；模块用到的普通脚本全局名字。
function scanModuleUses(modules, files, names, importInfo) {
  const missing = [];
  const violations = [];
  const usedPlain = new Set();
  for (const f of modules) {
    for (const r of f.refs) {
      const def = names.get(r.name);
      if (!def) continue;
      if (def.isModule) {
        if (def.file !== f.rel && !f.imported.has(r.name)) {
          missing.push({ file: f.rel, name: r.name, line: r.line, defined_in: def.file });
        }
      } else if (f.rel !== ENTRY) {
        usedPlain.add(r.name);
      }
    }
    for (const imp of importInfo[f.rel]) {
      const target = files.find((x) => x.rel === imp.from);
      if (target && !mayReference(f.layer, target.layer)) {
        violations.push({ from: f.rel, from_layer: f.layer, to: imp.from,
          to_layer: target.layer, names: imp.names });
      }
    }
  }
  missing.sort((a, b) => a.file.localeCompare(b.file) || a.name.localeCompare(b.name));
  violations.sort((a, b) => a.from.localeCompare(b.from) || a.to.localeCompare(b.to));
  return { missing, violations, usedPlain };
}

// legacy-globals.js 挂出去的名字，以及其中没有任何普通脚本在用的（有就必须删）。
function legacyNames(files, plainFiles, names) {
  const bridgeFile = files.find((f) => f.rel === BRIDGE);
  const attached = bridgeFile
    ? bridgeFile.defs.filter((d) => d.kind === "window").map((d) => d.name).sort()
    : [];
  const unused = attached.filter((name) => {
    const probe = new Map([[name, names.get(name) || { file: BRIDGE, layer: "bridge" }]]);
    return !plainFiles.some((p) => scanUses(p, probe, p.skip).some((r) => r.name === name));
  });
  return { attached, unused: unused.sort() };
}

// 普通脚本引用「只在模块里定义」的名字而它不在挂回名单：真加载下普通脚本拿不到模块
// 作用域里的名字，是 ReferenceError。量法沿用 scanUses（属性访问、对象键、注释与字符串
// 不算，本文件有同名局部声明不算）；名字集里普通脚本的顶层定义在前，凡定义被普通脚本
// 占据的名字不在此列——只有「任何普通脚本都没有同名定义」的才算只在模块里。
function unattachedModuleNames(plainFiles, names, attached) {
  const attachedSet = new Set(attached);
  const out = [];
  for (const f of plainFiles) {
    for (const r of scanUses(f, names, f.skip)) {
      const def = names.get(r.name);
      if (def && def.isModule && !attachedSet.has(r.name)) {
        out.push({ file: f.rel, name: r.name, line: r.line, defined_in: def.file });
      }
    }
  }
  out.sort((a, b) => a.file.localeCompare(b.file) || a.name.localeCompare(b.name)
    || a.line - b.line || a.defined_in.localeCompare(b.defined_in));
  return out;
}

function buildReport() {
  const { files, modules, plainFiles, names } = analyzeAll();
  const importInfo = collectModuleImports(modules, names);
  const cycles = findCycles(modules);
  const { missing, violations, usedPlain } = scanModuleUses(modules, files, names, importInfo);
  const { attached, unused } = legacyNames(files, plainFiles, names);
  const unattached = unattachedModuleNames(plainFiles, names, attached);
  return {
    ui: UI,
    modules: modules.map((f) => ({ file: f.rel, layer: f.layer })),
    imports: importInfo,
    cycles,
    missing_imports: missing,
    layer_violations: violations,
    plain_globals_used: [...usedPlain].sort(),
    legacy_globals_attached: attached,
    unused_legacy_globals: unused,
    unattached_module_names: unattached,
  };
}

// 期望值文件只含守卫比对的七段：五类问题（必须为空）加两份清单（逐项相等）。
function expectSection(report) {
  return {
    cycles: report.cycles,
    missing_imports: report.missing_imports,
    layer_violations: report.layer_violations,
    unattached_module_names: report.unattached_module_names,
    unused_legacy_globals: report.unused_legacy_globals,
    plain_globals_used: report.plain_globals_used,
    legacy_globals_attached: report.legacy_globals_attached,
  };
}

function main() {
  const report = buildReport();
  const payload = process.argv.includes("--expect") ? expectSection(report) : report;
  process.stdout.write(JSON.stringify(payload, null, 2) + "\n");
}

// 直接运行本文件时才出报告；被别的工具 import 时只取函数。
if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) main();
