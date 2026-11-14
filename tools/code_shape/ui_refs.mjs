// 前端跨层引用清点：state/ 用了 views/、controllers/ 或 app.js 的名字；views/ 用了 controllers/ 或 app.js 的名字。
//
// 量法照 design/evidence/2026-11-12/refactor-audit/README.md 的「C2」：按名字匹配、不建语法树；
// 属性访问、对象字面量的键、注释与字符串里的不算；本文件内有同名局部声明的不算。
// 精简自同目录审计脚本 globals.mjs（只保留跨层引用这部分，报表部分没有搬），量法不得改。
//
// 过渡期（ESM 地基批）清单口径：index.html 的普通脚本按加载序在前，模块入口的
// 引用图随后、被引用的在前；与测试夹具（local/tests/fixtures/ui_harness.py）同一口径。
// 清单与 import 解析函数从这里导出，ui_modules.mjs 复用。认层：普通脚本按目录；
// 模块按文件名规则并进现有四档词表——state-*/view-*/actions-* 分别并到 state/
// views/controllers 档，shared/ 下的并到 state 档（公共层的引用方向与状态档最接近，层规则的
// 精确规则由 ui_modules.mjs 单独守），main.js 与 legacy-globals.js 是过渡期的入口与桥，
// 照 root 档（不限层）。
//
// 从仓库根运行：node tools/code_shape/ui_refs.mjs
// 只读：向标准输出打印 JSON，不写任何文件。不含 local/ui/m/：index.html 不加载它。
// led.js 会被加载，和 app.js 一样算根层。

import { readFileSync } from "node:fs";
import { dirname, join, normalize } from "node:path";
import { pathToFileURL } from "node:url";

import { KEYWORDS } from "./jslex.mjs";
import { findFunctions } from "./jsscan.mjs";

const UI = "local/ui";

const isP = (t, v) => !!t && t.type === "punct" && t.value === v;
const isId = (t, v) => !!t && t.type === "id" && (v === undefined || t.value === v);

// ---- 页面脚本清单（公共口径）-----------------------------------------------

// index.html 里带 src 的 <script> 标签按出现顺序给 {src, module}；旧写法只认
// <script src="…"></script>，放宽到同时认 type="module" 的入口。
const TAG_RE = /<script\b([^>]*)>/g;
const SRC_RE = /\bsrc="([^"]+)"/;
const MODULE_TYPE_RE = /type\s*=\s*["']module["']/;

export function indexHtmlTags(htmlPath) {
  const html = readFileSync(htmlPath, "utf8");
  const out = [];
  for (const m of html.matchAll(TAG_RE)) {
    const src = SRC_RE.exec(m[1]);
    if (src) out.push({ src: src[1], module: MODULE_TYPE_RE.test(m[1]) });
  }
  return out;
}

// 模块的具名导入（只允许这一种写法，不改名）：import { 名字 } from "./相对路径"; 单行；
// 别的写法直接报错，不静默跳过。
const IMPORT_RE = /^import\s*\{([^}]*)\}\s*from\s*"(?<spec>[^"]+)"\s*;\s*$/;
const IMPORT_KEYWORD_RE = /^import\b/;

export function moduleImports(rel, src) {
  const out = [];
  for (const raw of src.split("\n")) {
    const line = raw.trim();
    if (!IMPORT_KEYWORD_RE.test(line)) continue;
    const m = IMPORT_RE.exec(line);
    if (!m) throw new Error(`${rel} 的 import 不是「import { 名字 } from "./相对路径";」的单行具名导入：${line}`);
    const names = m[1].split(",").map((s) => s.trim());
    if (names.some((n) => !/^[A-Za-z_$][\w$]*$/.test(n))) {
      throw new Error(`${rel} 的 import 列表只许逗号分隔的具名名字（不改名、不用 as）：${line}`);
    }
    if (!/^\.{1,2}\//.test(m.groups.spec)) {
      throw new Error(`${rel} 的 import 路径必须是 ./ 或 ../ 开头的相对路径：${m.groups.spec}`);
    }
    const dep = normalize(join(dirname(rel), m.groups.spec)).split("\\").join("/");
    if (dep.startsWith("..")) throw new Error(`${rel} 的 import 越出了 ui 目录：${m.groups.spec}`);
    out.push({ names, from: dep });
  }
  return out;
}

// 模块入口的引用图，被引用的在前（后序）；顶层循环引用直接报错（esm-verify H3：整张图起不来）。
export function moduleGraph(entry, readFile) {
  const order = [];
  const visiting = new Set();
  const visit = (rel, path) => {
    if (order.includes(rel)) return;
    if (visiting.has(rel)) throw new Error(`模块顶层循环引用：${path.concat(rel).join(" -> ")}`);
    visiting.add(rel);
    for (const imp of moduleImports(rel, readFile(rel))) visit(imp.from, path.concat(rel));
    visiting.delete(rel);
    order.push(rel);
  };
  if (entry) visit(entry, []);
  return order;
}

// 页面脚本清单：普通脚本按加载序在前，之后是模块入口引用图（被引用的在前）。
// includeLed 给本脚本用（led.js 会被加载，和 app.js 同算根层）；测试夹具与契约拼接
// 不带 led.js——它是独立字库渲染器，不含业务契约文本。
export function pageFiles(includeLed) {
  const tags = indexHtmlTags(join(UI, "index.html"));
  const plain = [];
  const entries = [];
  for (const t of tags) {
    if (t.module) entries.push(t.src);
    else if (includeLed || t.src !== "led.js") plain.push(t.src);
  }
  if (entries.length > 1) throw new Error(`index.html 有多个模块入口：${entries.join(", ")}`);
  const read = (rel) => readFileSync(join(UI, rel), "utf8");
  const files = plain.map((rel) => ({ rel, isModule: false, src: read(rel) }));
  for (const rel of moduleGraph(entries[0] || null, read)) {
    files.push({ rel, isModule: true, src: read(rel) });
  }
  return files;
}

// ---- 层认法------------------------------------------------------------------

// 层认法：普通脚本按目录；模块按文件名规则并进现有四档词表（见文件头）。
function layerOf(rel, isModule) {
  if (!isModule) {
    if (rel.startsWith("state/")) return "state";
    if (rel.startsWith("views/")) return "views";
    if (rel.startsWith("controllers/")) return "controllers";
    return "root";
  }
  if (rel === "main.js" || rel === "legacy-globals.js") return "root";
  if (rel.startsWith("shared/")) return "state";
  const base = rel.slice(rel.lastIndexOf("/") + 1);
  if (base === "state.js" || base.startsWith("state-")) return "state";
  if (base === "view.js" || base.startsWith("view-")) return "views";
  if (base === "actions.js" || base.startsWith("actions-")) return "controllers";
  return "root";
}

// ---- 名字与引用分析（量法不得改）---------------------------------------------------

// 每个记号的花括号深度与圆方括号深度（用于判「顶层」）。
function computeDepths(file) {
  const { tokens } = file;
  const brace = new Array(tokens.length);
  const paren = new Array(tokens.length);
  let b = 0;
  let p = 0;
  for (let k = 0; k < tokens.length; k += 1) {
    const t = tokens[k];
    if (t.type === "punct" && t.value === "}") b -= 1;
    if (t.type === "punct" && (t.value === ")" || t.value === "]")) p -= 1;
    brace[k] = b;
    paren[k] = p;
    if (t.type === "punct" && (t.value === "{" || t.value === "${")) b += 1;
    if (t.type === "punct" && (t.value === "(" || t.value === "[")) p += 1;
  }
  file.brace = brace;
  file.paren = paren;
}

// 每个记号所在的最内层函数：funcs 已按起点排好，后开始的在里层。
function bindInner(file) {
  const { tokens, funcs } = file;
  const inner = new Array(tokens.length).fill(null);
  for (const f of funcs) {
    for (let k = f.startTok; k <= f.bodyClose; k += 1) inner[k] = f;
  }
  file.inner = inner;
}

// 参数的局部名字：括号里紧跟在 ( 或 , 或 ... 或 { 或 [ 或 : 后面的标识符（解构也算）。
function paramLocals(f, tokens) {
  if (f.paramOpen === f.paramClose && tokens[f.paramOpen].type === "id") {
    f.locals.add(tokens[f.paramOpen].value);
    return;
  }
  for (let k = f.paramOpen + 1; k < f.paramClose; k += 1) {
    const t = tokens[k];
    const prev = tokens[k - 1];
    if (t.type === "id" && !KEYWORDS.has(t.value)
        && (isP(prev, "(") || isP(prev, ",") || isP(prev, "...") || isP(prev, "{")
            || isP(prev, "[") || isP(prev, ":"))
        && !isP(tokens[k + 1], ":")) {
      f.locals.add(t.value);
    }
  }
}

// 同一条 let 语句里逗号后面的声明：let a = 1, b = 2。
function commaDeclarations(file, k, declare) {
  const { tokens, brace, paren } = file;
  let j = k + 2;
  const depthB = brace[k];
  const depthP = paren[k];
  while ((j < tokens.length && !isP(tokens[j], ";") && tokens[j].line === tokens[j - 1].line)
         || (j < tokens.length && isP(tokens[j - 1], ","))) {
    if (isP(tokens[j], ",") && brace[j] === depthB && paren[j] === depthP
        && isId(tokens[j + 1]) && !KEYWORDS.has(tokens[j + 1].value)) {
      declare(k, tokens[j + 1].value);
    }
    if (isP(tokens[j], ";") && brace[j] === depthB) break;
    j += 1;
    if (j - k > 400) break;
  }
}

// 解构声明 const { a, b } = … / const [a] = …。
function destructuredNames(file, k, next, declare) {
  const { tokens } = file;
  if ((!isP(next, "{") && !isP(next, "[")) || next.match === undefined) return;
  for (let j = k + 2; j < next.match; j += 1) {
    if (isId(tokens[j]) && !KEYWORDS.has(tokens[j].value) && !isP(tokens[j + 1], ":")) {
      declare(k, tokens[j].value);
    }
  }
}

// 每个函数自己声明的局部名字：参数、const/let/var、嵌套函数名、catch 参数。
function collectLocals(file) {
  const { tokens, funcs, inner } = file;
  for (const f of funcs) f.locals = new Set();
  const declare = (k, name) => {
    // 参数和函数体里的声明都记到这个函数头上；嵌套函数自己的名字记到外层。
    const f = inner[k];
    if (f) f.locals.add(name);
  };
  for (const f of funcs) {
    paramLocals(f, tokens);
    if (f.kind === "function" && f.parent) f.parent.locals.add(f.name);
  }
  for (let k = 0; k < tokens.length; k += 1) {
    const t = tokens[k];
    if (!inner[k]) continue;
    if (isId(t, "const") || isId(t, "let") || isId(t, "var")) {
      const next = tokens[k + 1];
      if (isId(next) && !KEYWORDS.has(next.value)) {
        declare(k, next.value);
        commaDeclarations(file, k, declare);
      } else {
        destructuredNames(file, k, next, declare);
      }
    }
    if (isId(t, "catch") && isP(tokens[k + 1], "(") && isId(tokens[k + 2])) {
      declare(k, tokens[k + 2].value);
    }
  }
}

// 单个源码文件的完整分析：记号、函数、深度、局部名。给本脚本与 ui_modules.mjs 共用。
export function analyzeFile(src) {
  const { tokens, funcs, balanced } = findFunctions(src);
  const file = { tokens, funcs, balanced };
  computeDepths(file);
  bindInner(file);
  collectLocals(file);
  return file;
}

// 这个记号处，名字 name 是不是被某一层外层函数的局部声明遮住了。
function shadowed(file, k, name) {
  let f = file.inner[k];
  while (f) {
    if (f.locals.has(name)) return true;
    f = f.parent;
  }
  return false;
}

// 顶层定义：花括号深度 0、圆方括号深度 0 的 function / const / let / var / class，以及 window.X =。
export function topDefs(file) {
  const { tokens, brace, paren } = file;
  const defs = [];
  for (let k = 0; k < tokens.length; k += 1) {
    const t = tokens[k];
    if (t.type !== "id") continue;
    const atTop = brace[k] === 0 && paren[k] === 0;
    if (atTop && t.value === "function" && isId(tokens[k + 1]) && !isP(tokens[k - 1], ".")) {
      defs.push({ name: tokens[k + 1].value, kind: "function", line: t.line, tok: k + 1 });
    } else if (atTop && (t.value === "const" || t.value === "let" || t.value === "var")) {
      const next = tokens[k + 1];
      if (isId(next) && !KEYWORDS.has(next.value)) {
        defs.push({ name: next.value, kind: t.value, line: t.line, tok: k + 1 });
      }
    } else if (atTop && t.value === "class" && isId(tokens[k + 1])) {
      defs.push({ name: tokens[k + 1].value, kind: "class", line: t.line, tok: k + 1 });
    } else if ((t.value === "window" || t.value === "globalThis") && isP(tokens[k + 1], ".")
               && isId(tokens[k + 2]) && isP(tokens[k + 3], "=") && !isP(tokens[k - 1], ".")) {
      defs.push({ name: tokens[k + 2].value, kind: "window", line: t.line, tok: k + 2 });
    }
  }
  return defs;
}

// 找出对一组「全局名字」的引用。skipTok：本文件里属于声明本身的记号下标。
export function scanUses(file, names, skipTok) {
  const { tokens } = file;
  const refs = [];
  for (let k = 0; k < tokens.length; k += 1) {
    const t = tokens[k];
    if (t.type !== "id" || !names.has(t.value) || skipTok.has(k)) continue;
    const prev = tokens[k - 1];
    const next = tokens[k + 1];
    if (isP(prev, ".") || isP(prev, "?.")) continue;                    // 属性访问
    if (isP(next, ":") && (isP(prev, "{") || isP(prev, ","))) continue; // 对象字面量的键
    if (isId(prev, "function")) continue;                                // 嵌套函数自己的名字
    if (shadowed(file, k, t.value)) continue;
    refs.push({ name: t.value, line: t.line });
  }
  return refs;
}

// ---- 本脚本自己的报表（跨层引用清点）----------------------------------------------

function loadAll() {
  return pageFiles(true).map((item) => {
    const file = { rel: item.rel, isModule: item.isModule,
      layer: layerOf(item.rel, item.isModule), src: item.src, ...analyzeFile(item.src) };
    return file;
  });
}

// 越界的判定：从某层出发，定义在哪些层/文件里的名字算越界。
function isViolation(fromLayer, def) {
  if (fromLayer === "state") {
    return def.layer === "views" || def.layer === "controllers" || def.layer === "root";
  }
  if (fromLayer === "views") {
    return def.layer === "controllers" || def.layer === "root";
  }
  return false;
}

// 名字 → 定义信息。同一文件里先 const X 再 window.X = X 只算一次；跨文件重名仍记第一处。
function collectNames(files) {
  const names = new Map();
  for (const f of files) {
    f.defs = topDefs(f);
    f.skip = new Set(f.defs.map((d) => d.tok));
    for (const d of f.defs) {
      if (names.has(d.name) && names.get(d.name).file === f.rel) continue;
      if (!names.has(d.name)) {
        names.set(d.name, { file: f.rel, kind: d.kind, line: d.line, layer: f.layer });
      }
    }
  }
  return names;
}

// 一组「文件 × 名字」的行，按文件、名字排序。
function rows(files, names, fromLayer) {
  const out = [];
  for (const f of files) {
    if (f.layer !== fromLayer) continue;
    const byName = new Map();
    for (const r of f.refs) {
      const def = names.get(r.name);
      if (!def || def.file === f.rel || !isViolation(fromLayer, def)) continue;
      byName.set(r.name, (byName.get(r.name) || 0) + 1);
    }
    for (const [name, count] of byName) {
      out.push({ file: f.rel, name, count });
    }
  }
  out.sort((a, b) => a.file.localeCompare(b.file) || a.name.localeCompare(b.name));
  return out;
}

function main() {
  const files = loadAll();
  const names = collectNames(files);
  for (const f of files) {
    f.refs = scanUses(f, names, f.skip);
    if (!f.balanced) {
      process.stderr.write(`${f.rel} 括号没配平，结果不可信\n`);
    }
  }
  process.stdout.write(JSON.stringify({
    ui: UI,
    files: files.length,
    state: rows(files, names, "state"),
    views: rows(files, names, "views"),
  }, null, 2) + "\n");
}

// 直接运行本文件时才清点；被 ui_modules.mjs import 时只取上面导出的函数。
if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) main();
