// 前端全局依赖表（README「C2」），外加前端的跨层引用（「C1 ②」）和 S 以外的可变全局（「C1 ④」）。
//
// 从仓库根运行：
//   node design/evidence/2026-11-12/refactor-audit/scripts/globals.mjs
//   node design/evidence/2026-11-12/refactor-audit/scripts/globals.mjs --out <tempfile.mkdtemp() 建的空目录>
//
// 只读，只用 node 自带能力。按名字匹配，不建语法树；误差见 README。

import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { join } from "node:path";
import { KEYWORDS } from "./jslex.mjs";
import { findFunctions } from "./jsscan.mjs";

const UI = "local/ui";
const ASSIGN_OPS = new Set(["=", "+=", "-=", "*=", "/=", "%=", "**=", "<<=", ">>=", ">>>=",
  "&=", "|=", "^=", "&&=", "||=", "??="]);
// 原地修改容器的方法：Map / Set / Array 上会改内容的那些。
const MUTATORS = new Set(["push", "pop", "shift", "unshift", "splice", "sort", "reverse", "fill",
  "set", "add", "delete", "clear"]);

const isP = (t, v) => !!t && t.type === "punct" && t.value === v;
const isId = (t, v) => !!t && t.type === "id" && (v === undefined || t.value === v);

function scriptOrder(htmlPath) {
  const html = readFileSync(htmlPath, "utf8");
  const out = [];
  const re = /<script\s+[^>]*src="([^"]+)"/g;
  let m;
  while ((m = re.exec(html))) out.push(m[1]);
  return out;
}

function layerOf(rel) {
  if (rel.startsWith("state/")) return "state";
  if (rel.startsWith("views/")) return "views";
  if (rel.startsWith("controllers/")) return "controllers";
  return "root";
}

// 读一个文件：记号、函数、每个记号的花括号深度和圆方括号深度、每个记号所在的最内层函数。
function load(path) {
  const src = readFileSync(path, "utf8");
  const { tokens, funcs, balanced } = findFunctions(src);
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
  // 每个记号的最内层函数：funcs 已按起点排好，后开始的在里层。
  const inner = new Array(tokens.length).fill(null);
  for (const f of funcs) {
    for (let k = f.startTok; k <= f.bodyClose; k += 1) inner[k] = f;
  }
  // 每个函数自己声明的局部名字：参数、const/let/var、嵌套函数名、catch 参数。
  for (const f of funcs) f.locals = new Set();
  const declare = (k, name) => {
    let f = inner[k];
    // 参数和函数体里的声明都记到这个函数头上；嵌套函数自己的名字记到外层。
    if (f) f.locals.add(name);
  };
  for (const f of funcs) {
    // 参数：括号里紧跟在 ( 或 , 或 ... 或 { 或 [ 后面的标识符（解构也算）。
    if (f.paramOpen === f.paramClose && tokens[f.paramOpen].type === "id") {
      f.locals.add(tokens[f.paramOpen].value);
    } else {
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
    if (f.kind === "function" && f.parent) f.parent.locals.add(f.name);
  }
  for (let k = 0; k < tokens.length; k += 1) {
    const t = tokens[k];
    if (!inner[k]) continue;
    if (isId(t, "const") || isId(t, "let") || isId(t, "var")) {
      const next = tokens[k + 1];
      if (isId(next) && !KEYWORDS.has(next.value)) {
        declare(k, next.value);
        // 同一条语句里逗号后面的声明： let a = 1, b = 2
        let j = k + 2;
        const depthB = brace[k];
        const depthP = paren[k];
        while (j < tokens.length && !isP(tokens[j], ";") && tokens[j].line === tokens[j - 1].line
               || (j < tokens.length && isP(tokens[j - 1], ","))) {
          if (isP(tokens[j], ",") && brace[j] === depthB && paren[j] === depthP
              && isId(tokens[j + 1]) && !KEYWORDS.has(tokens[j + 1].value)) {
            declare(k, tokens[j + 1].value);
          }
          if (isP(tokens[j], ";") && brace[j] === depthB) break;
          j += 1;
          if (j - k > 400) break;
        }
      } else if ((isP(next, "{") || isP(next, "[")) && next.match !== undefined) {
        for (let j = k + 2; j < next.match; j += 1) {
          if (isId(tokens[j]) && !KEYWORDS.has(tokens[j].value) && !isP(tokens[j + 1], ":")) {
            declare(k, tokens[j].value);
          }
        }
      }
    }
    if (isId(t, "catch") && isP(tokens[k + 1], "(") && isId(tokens[k + 2])) {
      declare(k, tokens[k + 2].value);
    }
  }
  return { path, src, tokens, funcs, balanced, brace, paren, inner };
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

// 从标识符 k 开始读成员链：S.login.checking、S.round["check"] …
function readChain(tokens, k) {
  const path = [tokens[k].value];
  let j = k + 1;
  for (;;) {
    if ((isP(tokens[j], ".") || isP(tokens[j], "?.")) && isId(tokens[j + 1])) {
      path.push(tokens[j + 1].value);
      j += 2;
    } else if (isP(tokens[j], "[") && tokens[j].match !== undefined) {
      path.push("[…]");
      j = tokens[j].match + 1;
    } else break;
  }
  return { path, end: j };
}

// 顶层定义：花括号深度 0、圆方括号深度 0 的 function / const / let / var / class，以及 window.X =。
function topDefs(file, baseBrace = 0, from = 0, to = file.tokens.length) {
  const { tokens, brace, paren } = file;
  const defs = [];
  const warn = [];
  for (let k = from; k < to; k += 1) {
    const t = tokens[k];
    if (t.type !== "id") continue;
    const atTop = brace[k] === baseBrace && paren[k] === 0;
    if (atTop && t.value === "function" && isId(tokens[k + 1]) && !isP(tokens[k - 1], ".")) {
      defs.push({ name: tokens[k + 1].value, kind: "function", line: t.line, tok: k + 1 });
    } else if (atTop && (t.value === "const" || t.value === "let" || t.value === "var")) {
      const next = tokens[k + 1];
      if (isId(next) && !KEYWORDS.has(next.value)) {
        defs.push({ name: next.value, kind: t.value, line: t.line, tok: k + 1 });
      } else if (isP(next, "{") || isP(next, "[")) {
        warn.push(`${file.path}:${t.line} 顶层解构声明，没有展开`);
      }
    } else if (atTop && t.value === "class" && isId(tokens[k + 1])) {
      defs.push({ name: tokens[k + 1].value, kind: "class", line: t.line, tok: k + 1 });
    } else if ((t.value === "window" || t.value === "globalThis") && isP(tokens[k + 1], ".")
               && isId(tokens[k + 2]) && isP(tokens[k + 3], "=") && !isP(tokens[k - 1], ".")) {
      defs.push({ name: tokens[k + 2].value, kind: "window", line: t.line, tok: k + 2 });
    }
  }
  return { defs, warn };
}

// 找出对一组「全局名字」的引用和写入。
// names: Map 名字 → 定义信息；skipTok: 本文件里属于声明本身的记号下标。
function scanUses(file, names, skipTok) {
  const { tokens } = file;
  const refs = [];      // { name, line, tok, call, topLevel }
  const writes = [];    // { name, path, line, how, fn }
  for (let k = 0; k < tokens.length; k += 1) {
    const t = tokens[k];
    if (t.type !== "id" || !names.has(t.value) || skipTok.has(k)) continue;
    const prev = tokens[k - 1];
    const next = tokens[k + 1];
    if (isP(prev, ".") || isP(prev, "?.")) continue;                       // 属性访问
    if (isP(next, ":") && (isP(prev, "{") || isP(prev, ","))) continue;    // 对象字面量的键
    if (isId(prev, "function")) continue;                                   // 嵌套函数自己的名字
    if (shadowed(file, k, t.value)) continue;
    const fn = file.inner[k];
    const fnName = fn ? fn.qualname : "<顶层>";
    refs.push({ name: t.value, line: t.line, tok: k, call: isP(next, "("), topLevel: !fn });

    const { path, end } = readChain(tokens, k);
    const after = tokens[end];
    const joined = path.join(".").replace(/\.\[/g, "[");
    if (after && after.type === "punct" && ASSIGN_OPS.has(after.value)) {
      writes.push({ name: t.value, path: joined, line: t.line, how: after.value, fn: fnName });
    } else if (isP(after, "++") || isP(after, "--") || isP(prev, "++") || isP(prev, "--")) {
      writes.push({ name: t.value, path: joined, line: t.line, how: "++/--", fn: fnName });
    } else if (isId(prev, "delete") && path.length > 1) {
      writes.push({ name: t.value, path: joined, line: t.line, how: "delete", fn: fnName });
    } else if (isP(after, "(") && path.length >= 2 && MUTATORS.has(path[path.length - 1])) {
      const target = path.slice(0, -1).join(".").replace(/\.\[/g, "[");
      writes.push({ name: t.value, path: target, line: t.line,
        how: `.${path[path.length - 1]}()`, fn: fnName });
    } else if (isP(prev, "(") && isId(tokens[k - 2], "assign") && isP(tokens[k - 3], ".")
               && isId(tokens[k - 4], "Object")) {
      writes.push({ name: t.value, path: joined, line: t.line, how: "Object.assign", fn: fnName });
    }
  }
  return { refs, writes };
}

// Tarjan 强连通分量。
function scc(nodes, edges) {
  let index = 0;
  const stack = [];
  const idx = new Map();
  const low = new Map();
  const on = new Set();
  const out = [];
  const visit = (v) => {
    idx.set(v, index); low.set(v, index); index += 1;
    stack.push(v); on.add(v);
    for (const w of edges.get(v) || []) {
      if (!idx.has(w)) { visit(w); low.set(v, Math.min(low.get(v), low.get(w))); }
      else if (on.has(w)) low.set(v, Math.min(low.get(v), idx.get(w)));
    }
    if (low.get(v) === idx.get(v)) {
      const comp = [];
      let w;
      do { w = stack.pop(); on.delete(w); comp.push(w); } while (w !== v);
      out.push(comp);
    }
  };
  for (const v of nodes) if (!idx.has(v)) visit(v);
  return out;
}

const lines = [];
const say = (s = "") => lines.push(s);
const result = {};

// ───────────────────────── 桌面端 ─────────────────────────
{
  const order = scriptOrder(join(UI, "index.html"));
  const files = order.map((rel) => ({ rel, layer: layerOf(rel), ...load(join(UI, rel).replace(/\\/g, "/")) }));
  const warnings = [];
  const names = new Map();     // 名字 → { file(rel), kind, line }
  const dupes = [];
  for (const f of files) {
    const { defs, warn } = topDefs(f);
    warnings.push(...warn);
    f.defs = defs;
    f.skip = new Set(defs.map((d) => d.tok));
    if (!f.balanced) warnings.push(`${f.path} 括号没配平，结果不可信`);
    for (const d of defs) {
      // 同一个文件里先 const X 再 window.X = X 只算一次定义。
      if (names.has(d.name) && names.get(d.name).file === f.rel) continue;
      if (names.has(d.name)) dupes.push({ name: d.name, a: names.get(d.name), b: { file: f.rel, line: d.line } });
      else names.set(d.name, { file: f.rel, kind: d.kind, line: d.line, layer: f.layer });
    }
  }
  for (const f of files) {
    const { refs, writes } = scanUses(f, names, f.skip);
    f.refs = refs;
    f.writes = writes;
  }

  say("# 前端全局依赖表\n");
  say("## 桌面端（local/ui/）\n");
  say(`按 \`local/ui/index.html\` 的加载顺序读了 ${files.length} 个脚本，顶层定义了 ${names.size} 个全局名字。`);
  if (warnings.length) say("\n**警告**：" + warnings.join("；"));
  say();

  // 文件一览
  const fanOut = new Map();   // rel → Map(目标文件 → Set(名字))
  const fanIn = new Map();    // rel → Map(来源文件 → Set(名字))
  const nameUsers = new Map(); // 名字 → Map(文件 → 次数)
  const loadEdges = new Map(); // 只算顶层（加载时）执行的引用
  for (const f of files) {
    fanOut.set(f.rel, new Map());
    fanIn.set(f.rel, new Map());
    loadEdges.set(f.rel, new Map());
  }
  for (const f of files) {
    for (const r of f.refs) {
      const def = names.get(r.name);
      if (def.file === f.rel) continue;
      if (!fanOut.get(f.rel).has(def.file)) fanOut.get(f.rel).set(def.file, new Set());
      fanOut.get(f.rel).get(def.file).add(r.name);
      if (!fanIn.get(def.file).has(f.rel)) fanIn.get(def.file).set(f.rel, new Set());
      fanIn.get(def.file).get(f.rel).add(r.name);
      if (!nameUsers.has(r.name)) nameUsers.set(r.name, new Map());
      nameUsers.get(r.name).set(f.rel, (nameUsers.get(r.name).get(f.rel) || 0) + 1);
      if (r.topLevel) {
        if (!loadEdges.get(f.rel).has(def.file)) loadEdges.get(f.rel).set(def.file, new Set());
        loadEdges.get(f.rel).get(def.file).add(r.name);
      }
    }
  }
  const countNames = (m) => new Set([...m.values()].flatMap((s) => [...s])).size;

  say("### 每个文件：定义了什么、依赖谁、被谁依赖\n");
  say("「依赖」= 引用了别的文件定义的名字。行数是物理行。\n");
  say("| 序 | 文件 | 层 | 行数 | 顶层定义（函数 / const / let·var）| 依赖的文件数 | 依赖的名字数 | 被几个文件依赖 | 被引用的名字数 |");
  say("|---|---|---|---|---|---|---|---|---|");
  files.forEach((f, i) => {
    const nFn = f.defs.filter((d) => d.kind === "function").length;
    const nConst = f.defs.filter((d) => d.kind === "const" || d.kind === "class" || d.kind === "window").length;
    const nLet = f.defs.filter((d) => d.kind === "let" || d.kind === "var").length;
    const nl = (f.src.match(/\n/g) || []).length;
    say(`| ${i + 1} | \`${f.rel}\` | ${f.layer} | ${nl} | ${nFn} / ${nConst} / ${nLet} | `
      + `${fanOut.get(f.rel).size} | ${countNames(fanOut.get(f.rel))} | ${fanIn.get(f.rel).size} | `
      + `${countNames(fanIn.get(f.rel))} |`);
  });

  // 同名定义
  say(`\n### 同一个名字在两个文件里都有顶层定义：${dupes.length} 处\n`);
  if (dupes.length) {
    say("| 名字 | 第一处 | 第二处 |");
    say("|---|---|---|");
    for (const d of dupes) say(`| \`${d.name}\` | \`${UI}/${d.a.file}:${d.a.line}\` | \`${UI}/${d.b.file}:${d.b.line}\` |`);
  }

  // 高扇入
  const high = [...nameUsers.entries()].filter(([, m]) => m.size >= 5)
    .sort((a, b) => b[1].size - a[1].size || a[0].localeCompare(b[0]));
  say(`\n### 被 5 个及以上其他文件引用的名字：${high.length} 个\n`);
  say("| 名字 | 定义位置 | 种类 | 引用它的文件数 | 引用次数 |");
  say("|---|---|---|---|---|");
  for (const [name, m] of high) {
    const def = names.get(name);
    const total = [...m.values()].reduce((a, b) => a + b, 0);
    say(`| \`${name}\` | \`${UI}/${def.file}:${def.line}\` | ${def.kind} | ${m.size} | ${total} |`);
  }

  // 循环依赖
  const nodes = files.map((f) => f.rel);
  const allEdges = new Map(nodes.map((n) => [n, [...fanOut.get(n).keys()]]));
  const comps = scc(nodes, allEdges).filter((c) => c.length > 1);
  say("\n### 循环依赖（文件级）\n");
  say("**全部引用都算**（函数体里的调用也算一条边）："
    + (comps.length ? `${comps.length} 组。` : "没有。"));
  for (const c of comps) {
    const inOrder = nodes.filter((n) => c.includes(n));
    say(`\n- ${inOrder.length} 个文件互相可达：` + inOrder.map((n) => `\`${n}\``).join("、"));
  }
  const acyclic = nodes.filter((n) => !comps.some((c) => c.includes(n)));
  say(`\n不在任何循环里的文件（${acyclic.length} 个）：` + acyclic.map((n) => `\`${n}\``).join("、") + "。");

  const loadGraph = new Map(nodes.map((n) => [n, [...loadEdges.get(n).keys()]]));
  const loadComps = scc(nodes, loadGraph).filter((c) => c.length > 1);
  say("\n**只算加载时就执行的引用**（不在任何函数体里的顶层代码）：" + (loadComps.length ? `${loadComps.length} 组循环。` : "没有循环。"));
  for (const c of loadComps) say("\n- " + nodes.filter((n) => c.includes(n)).map((n) => `\`${n}\``).join("、"));
  say("\n加载时引用的明细（改成 ES Modules 后，这些是必须在求值前就绪的 import）：\n");
  say("| 文件 | 加载时用到的别的文件 | 名字 |");
  say("|---|---|---|");
  for (const f of files) {
    for (const [dst, set] of loadEdges.get(f.rel)) {
      const later = nodes.indexOf(dst) > nodes.indexOf(f.rel);
      say(`| \`${f.rel}\` | \`${dst}\`${later ? "（**排在后面**）" : ""} | ${[...set].map((n) => `\`${n}\``).join("、")} |`);
    }
  }

  // 互相引用最重的文件对
  const pairs = [];
  for (let i = 0; i < nodes.length; i += 1) {
    for (let j = i + 1; j < nodes.length; j += 1) {
      const ab = fanOut.get(nodes[i]).get(nodes[j]);
      const ba = fanOut.get(nodes[j]).get(nodes[i]);
      if (ab && ba) pairs.push({ a: nodes[i], b: nodes[j], ab: ab.size, ba: ba.size });
    }
  }
  pairs.sort((x, y) => (y.ab + y.ba) - (x.ab + x.ba));
  say(`\n### 两个文件直接互相引用：${pairs.length} 对（列名字数最多的 25 对）\n`);
  say("| 文件 A | 文件 B | A 用 B 的名字数 | B 用 A 的名字数 |");
  say("|---|---|---|---|");
  for (const p of pairs.slice(0, 25)) say(`| \`${p.a}\` | \`${p.b}\` | ${p.ab} | ${p.ba} |`);

  // 层之间
  const layers = ["state", "views", "controllers", "root"];
  say("\n### 层与层之间的引用（名字数，去重后）\n");
  say("| 从 ＼ 到 | state | views | controllers | root |");
  say("|---|---|---|---|---|");
  const layerNames = new Map();
  for (const f of files) {
    for (const r of f.refs) {
      const def = names.get(r.name);
      if (def.file === f.rel) continue;
      const key = `${f.layer}>${def.layer}`;
      if (!layerNames.has(key)) layerNames.set(key, new Set());
      layerNames.get(key).add(r.name);
    }
  }
  for (const a of layers) {
    say(`| ${a} | ` + layers.map((b) => (layerNames.get(`${a}>${b}`) || new Set()).size).join(" | ") + " |");
  }

  // 越界：state → views/controllers/root；views → controllers/root
  const violations = [];
  for (const f of files) {
    const bad = f.layer === "state" ? ["views", "controllers", "root"]
      : f.layer === "views" ? ["controllers", "root"] : [];
    if (!bad.length) continue;
    const byName = new Map();
    for (const r of f.refs) {
      const def = names.get(r.name);
      if (def.file === f.rel || !bad.includes(def.layer)) continue;
      if (!byName.has(r.name)) byName.set(r.name, []);
      byName.get(r.name).push(r.line);
    }
    for (const [name, ls] of byName) {
      violations.push({ file: f.rel, layer: f.layer, name, def: names.get(name), lines: ls });
    }
  }
  const stateV = violations.filter((v) => v.layer === "state");
  const viewsV = violations.filter((v) => v.layer === "views");
  const uniq = (rows) => new Set(rows.map((v) => v.name)).size;
  const sites = (rows) => rows.reduce((n, v) => n + v.lines.length, 0);
  say(`\n### 越界引用：state/ 用了 views/、controllers/ 或根目录的名字\n`);
  say(`去重后 ${uniq(stateV)} 个名字，出现在 ${new Set(stateV.map((v) => v.file)).size} 个 state 文件里，`
    + `共 ${sites(stateV)} 处引用（下表一行是一个「文件 × 名字」，${stateV.length} 行）。\n`);
  say("| 位置（引用的行）| 用了 | 定义在 | 层 |");
  say("|---|---|---|---|");
  for (const v of stateV) {
    say(`| \`${UI}/${v.file}:${v.lines.slice(0, 6).join(",")}${v.lines.length > 6 ? "…" : ""}\` | \`${v.name}\` | `
      + `\`${UI}/${v.def.file}:${v.def.line}\` | ${v.def.layer} |`);
  }
  say(`\n### 越界引用：views/ 用了 controllers/ 或根目录的名字\n`);
  say(`去重后 ${uniq(viewsV)} 个名字，出现在 ${new Set(viewsV.map((v) => v.file)).size} 个 views 文件里，`
    + `共 ${sites(viewsV)} 处引用（下表一行是一个名字）。\n`);
  const viewsByDef = new Map();
  for (const v of viewsV) {
    if (!viewsByDef.has(v.name)) viewsByDef.set(v.name, { def: v.def, users: [] });
    viewsByDef.get(v.name).users.push(v);
  }
  say("| 名字 | 定义在 | 用它的 views 文件（行）| 次数 |");
  say("|---|---|---|---|");
  for (const [name, info] of [...viewsByDef.entries()].sort((a, b) =>
    b[1].users.reduce((n, u) => n + u.lines.length, 0) - a[1].users.reduce((n, u) => n + u.lines.length, 0))) {
    const total = info.users.reduce((n, u) => n + u.lines.length, 0);
    say(`| \`${name}\` | \`${UI}/${info.def.file}:${info.def.line}\` | `
      + info.users.map((u) => `\`${u.file}\`:${u.lines.slice(0, 5).join(",")}${u.lines.length > 5 ? "…" : ""}`).join("；")
      + ` | ${total} |`);
  }
  const apiCalls = files.filter((f) => f.layer === "views")
    .map((f) => ({ rel: f.rel, lines: f.refs.filter((r) => r.name === "api").map((r) => r.line) }))
    .filter((x) => x.lines.length);
  say(`\n其中 views/ 直接发桥接请求（调 \`api(…)\`）的文件 ${apiCalls.length} 个，`
    + `共 ${apiCalls.reduce((n, x) => n + x.lines.length, 0)} 处：`
    + apiCalls.map((x) => `\`${x.rel}\` ${x.lines.length} 处`).join("、") + "。");

  // S 的写入
  const sWrites = [];
  for (const f of files) for (const w of f.writes) if (w.name === "S") sWrites.push({ ...w, file: f.rel, layer: f.layer });
  const fieldOf = (p) => p.split(/[.[]/).slice(0, 2).join(".");
  const byField = new Map();
  for (const w of sWrites) {
    const fld = fieldOf(w.path);
    if (!byField.has(fld)) byField.set(fld, []);
    byField.get(fld).push(w);
  }
  say(`\n### 状态仓库 \`S\` 的写入：${sWrites.length} 处，分布在 ${new Set(sWrites.map((w) => w.file)).size} 个文件\n`);
  say("按 `S` 的一级字段汇总。「写入」含赋值、自增、`delete`、`Object.assign` 和容器的变更方法（`.set()` `.add()` `.push()` 等）。\n");
  say("| 字段 | 写入处数 | state/ | views/ | controllers/ | 根目录 | 写它的文件 |");
  say("|---|---|---|---|---|---|---|");
  for (const [fld, ws] of [...byField.entries()].sort((a, b) => b[1].length - a[1].length)) {
    const n = (l) => ws.filter((w) => w.layer === l).length;
    const fs = [...new Set(ws.map((w) => w.file))];
    say(`| \`${fld}\` | ${ws.length} | ${n("state")} | ${n("views")} | ${n("controllers")} | ${n("root")} | `
      + fs.map((x) => `\`${x}\``).join("、") + " |");
  }
  // S 字面量里声明了哪些一级字段（state/store.js 里 const S = { … } 深度 1 的键）。
  const store = files.find((f) => f.rel === "state/store.js");
  const declared = new Map();
  {
    const sDef = store.defs.find((d) => d.name === "S");
    const open = sDef.tok + 2;                      // S = {
    const close = store.tokens[open].match;
    const base = store.brace[open] + 1;
    for (let k = open + 1; k < close; k += 1) {
      const t = store.tokens[k];
      if (t.type === "id" && store.brace[k] === base && store.paren[k] === 0
          && isP(store.tokens[k + 1], ":")
          && (isP(store.tokens[k - 1], "{") || isP(store.tokens[k - 1], ","))) {
        declared.set(t.value, t.line);
      }
    }
  }
  const written = new Set([...byField.keys()].map((x) => x.slice(2)));
  const undeclared = [...written].filter((x) => !declared.has(x)).sort();
  const neverWritten = [...declared.keys()].filter((x) => !written.has(x));
  say(`\n#### \`S\` 的字段：字面量里声明了 ${declared.size} 个，别处写入但没有声明的 ${undeclared.length} 个\n`);
  say("没有声明、运行中才挂上去的字段（读 `state/store.js` 看不到它们）：\n");
  say("| 字段 | 第一处写入 | 写入处数 |");
  say("|---|---|---|");
  for (const name of undeclared) {
    const ws = byField.get(`S.${name}`);
    say(`| \`S.${name}\` | \`${UI}/${ws[0].file}:${ws[0].line}\` | ${ws.length} |`);
  }
  say("\n声明了、但脚本没数到写入的字段（只在声明时给初值，或经别名修改）："
    + (neverWritten.map((x) => `\`S.${x}\`（${declared.get(x)}）`).join("、") || "没有") + "。");

  const viewS = sWrites.filter((w) => w.layer === "views");
  say(`\n#### views/ 里直接写 \`S\` 的位置：${viewS.length} 处\n`);
  say("| 位置 | 写了什么 | 方式 | 所在函数 |");
  say("|---|---|---|---|");
  for (const w of viewS) say(`| \`${UI}/${w.file}:${w.line}\` | \`${w.path}\` | \`${w.how}\` | \`${w.fn}\` |`);

  // S 以外的可变全局
  const mutable = new Map();   // 名字 → { def, writes: [], readers: Map }
  for (const [name, def] of names) {
    if (name === "S") continue;
    if (def.kind === "let" || def.kind === "var") mutable.set(name, { def, writes: [] });
  }
  for (const f of files) {
    for (const w of f.writes) {
      if (w.name === "S") continue;
      const def = names.get(w.name);
      if (!mutable.has(w.name)) {
        if (def.kind === "function") continue;
        mutable.set(w.name, { def, writes: [] });
      }
      mutable.get(w.name).writes.push({ ...w, file: f.rel, layer: f.layer });
    }
  }
  say(`\n### \`S\` 以外的可变全局：${mutable.size} 个\n`);
  say("顶层的 `let` / `var`，以及被别处改写了属性或内容的顶层 `const` 对象。\n");
  say("| 名字 | 定义位置 | 种类 | 写入处数 | 写的位置（文件:行 路径 方式）| 读它的文件 |");
  say("|---|---|---|---|---|---|");
  for (const [name, info] of [...mutable.entries()].sort((a, b) =>
    a[1].def.file.localeCompare(b[1].def.file) || a[1].def.line - b[1].def.line)) {
    const users = nameUsers.get(name) || new Map();
    const own = files.find((f) => f.rel === info.def.file).refs.filter((r) => r.name === name).length;
    const readers = [`\`${info.def.file}\`（本文件 ${own} 处）`,
      ...[...users.keys()].map((u) => `\`${u}\``)];
    const ws = info.writes.slice(0, 10).map((w) =>
      `\`${w.file}:${w.line}\` \`${w.path}\` \`${w.how}\``).join("；")
      + (info.writes.length > 10 ? ` 等 ${info.writes.length} 处` : "");
    say(`| \`${name}\` | \`${UI}/${info.def.file}:${info.def.line}\` | ${info.def.kind} | ${info.writes.length} | `
      + `${ws || "（只有声明时的初值）"} | ${readers.join("、")} |`);
  }
  const viewNonS = [...mutable.entries()].flatMap(([name, info]) =>
    info.writes.filter((w) => w.layer === "views").map((w) => ({ name, ...w })));
  say(`\n其中由 views/ 文件写入的有 ${viewNonS.length} 处，涉及 ${new Set(viewNonS.map((w) => w.name)).size} 个名字：`
    + [...new Set(viewNonS.map((w) => w.name))].map((n) => `\`${n}\``).join("、") + "。");

  // 写入多的对象（自己就是一个小状态仓库）：按一级字段汇总。
  for (const [name, info] of mutable) {
    if (info.writes.length <= 10) continue;
    const perField = new Map();
    for (const w of info.writes) {
      const fld = w.path.split(/[.[]/).slice(0, 2).join(".");
      if (!perField.has(fld)) perField.set(fld, []);
      perField.get(fld).push(w);
    }
    say(`\n#### \`${name}\` 按字段：${perField.size} 个字段，${info.writes.length} 处写入\n`);
    say("| 字段 | 写入处数 | 写它的函数（行）|");
    say("|---|---|---|");
    for (const [fld, ws] of [...perField.entries()].sort((x, y) => y[1].length - x[1].length)) {
      const byFn = new Map();
      for (const w of ws) {
        const top = w.fn.split(" > ")[0];
        if (!byFn.has(top)) byFn.set(top, []);
        byFn.get(top).push(w.line);
      }
      const txt = [...byFn.entries()].slice(0, 8)
        .map(([n, ls]) => `\`${n}\`:${ls.slice(0, 4).join(",")}${ls.length > 4 ? "…" : ""}`).join("、")
        + (byFn.size > 8 ? ` 等 ${byFn.size} 个函数` : "");
      say(`| \`${fld}\` | ${ws.length} | ${txt} |`);
    }
  }

  // 每个文件依赖谁（明细）
  say("\n### 依赖明细：每个文件用了别的文件的哪些名字\n");
  for (const f of files) {
    const out = fanOut.get(f.rel);
    if (!out.size) { say(`- \`${f.rel}\`：不依赖别的文件。`); continue; }
    say(`- \`${f.rel}\` →`);
    for (const [dst, set] of [...out.entries()].sort((a, b) => b[1].size - a[1].size)) {
      say(`  - \`${dst}\`（${set.size}）：` + [...set].sort().map((n) => `\`${n}\``).join("、"));
    }
  }

  result.desktop = {
    order, names: Object.fromEntries(names),
    files: files.map((f) => ({ rel: f.rel, layer: f.layer, defs: f.defs.map(({ tok, ...d }) => d),
      refs: f.refs.map(({ tok, ...r }) => r), writes: f.writes })),
    cycles: comps, loadCycles: loadComps, dupes,
  };
}

// ───────────────────────── 手机页 ─────────────────────────
{
  const order = scriptOrder(join(UI, "m/index.html"));
  say("\n## 手机页（local/ui/m/）\n");
  say(`\`local/ui/m/index.html\` 只加载 ${order.length} 个脚本：${order.map((o) => `\`m/${o}\``).join("、")}。没有文件间依赖。`);
  const path = `${UI}/m/app.js`;
  const f = load(path);
  const { tokens, brace } = f;

  // 两大块：const PhoneModel = { … } 和 if (typeof document !== "undefined") { … }
  let modelOpen = -1;
  let docOpen = -1;
  for (let k = 0; k < tokens.length; k += 1) {
    if (brace[k] !== 0) continue;
    if (isId(tokens[k], "const") && isId(tokens[k + 1], "PhoneModel") && isP(tokens[k + 3], "{")) modelOpen = k + 3;
    if (isId(tokens[k], "if") && isP(tokens[k + 1], "(") && isId(tokens[k + 2], "typeof")
        && isId(tokens[k + 3], "document")) {
      const close = tokens[k + 1].match;
      if (isP(tokens[close + 1], "{")) docOpen = close + 1;
    }
  }
  const modelClose = tokens[modelOpen].match;
  const docClose = tokens[docOpen].match;
  say(`\n- \`PhoneModel\`（纯函数对象）：\`${path}:${tokens[modelOpen].line}-${tokens[modelClose].line}\`，`
    + `${tokens[modelClose].line - tokens[modelOpen].line + 1} 行。`);
  say(`- 页面逻辑（\`if (typeof document !== "undefined")\` 块）：\`${path}:${tokens[docOpen].line}-${tokens[docClose].line}\`，`
    + `${tokens[docClose].line - tokens[docOpen].line + 1} 行。`);

  // PhoneModel 的成员：深度 1 的键
  const members = [];
  for (let k = modelOpen + 1; k < modelClose; k += 1) {
    if (brace[k] !== 1 || f.paren[k] !== 0) continue;
    const t = tokens[k];
    const prev = tokens[k - 1];
    if (t.type === "id" && (isP(prev, "{") || isP(prev, ",") || isP(prev, "}"))
        && (isP(tokens[k + 1], "(") || isP(tokens[k + 1], ":"))) {
      const fn = f.funcs.find((x) => x.depth === 0 && x.name === t.value
        && x.startTok >= k - 1 && x.startTok <= k + 2);
      members.push({ name: t.value, line: t.line, isFn: !!fn || isP(tokens[k + 1], "("),
        lines: fn ? fn.lines : 0 });
    }
  }
  const fnMembers = members.filter((m) => m.isFn);
  say(`\n### \`PhoneModel\` 成员：${members.length} 个（函数 ${fnMembers.length} 个，常量 ${members.length - fnMembers.length} 个）\n`);
  say("最长的 15 个函数：\n");
  say("| 行数 | 位置 | 名字 |");
  say("|---|---|---|");
  for (const m of [...fnMembers].sort((a, b) => b.lines - a.lines).slice(0, 15)) {
    say(`| ${m.lines} | \`${path}:${m.line}\` | \`PhoneModel.${m.name}\` |`);
  }

  // 页面块里的定义（深度 1）
  const { defs } = topDefs(f, 1, docOpen + 1, docClose);
  const blockFns = defs.filter((d) => d.kind === "function");
  const blockConsts = defs.filter((d) => d.kind !== "function");
  say(`\n### 页面块里的定义：函数 ${blockFns.length} 个，\`const\` ${blockConsts.filter((d) => d.kind === "const").length} 个，`
    + `\`let\` / \`var\` ${blockConsts.filter((d) => d.kind !== "const").length} 个\n`);
  say("非函数的定义：" + blockConsts.map((d) => `\`${d.name}\`（${d.kind}，${d.line}）`).join("、") + "。");

  // 对块内名字的写入（主要是 model.xxx）
  const blockNames = new Map(defs.map((d) => [d.name, { file: "m/app.js", kind: d.kind, line: d.line }]));
  const skip = new Set(defs.map((d) => d.tok));
  const { refs, writes } = scanUses(f, blockNames, skip);
  const stateWrites = writes.filter((w) => blockNames.get(w.name).kind !== "function");
  const byTarget = new Map();
  for (const w of stateWrites) {
    const key = w.path.split(/[.[]/).slice(0, 2).join(".");
    if (!byTarget.has(key)) byTarget.set(key, []);
    byTarget.get(key).push(w);
  }
  // 读：model.xxx 出现但不是写入
  const readCount = new Map();
  for (const r of refs) {
    if (blockNames.get(r.name).kind === "function") continue;
    const { path: p } = readChain(tokens, r.tok);
    const key = p.slice(0, 2).join(".").replace(/\.\[/g, "[");
    const fnName = f.inner[r.tok] ? f.inner[r.tok].qualname.split(" > ")[0] : "<块顶层>";
    if (!readCount.has(key)) readCount.set(key, new Set());
    readCount.get(key).add(fnName);
  }
  say(`\n### 页面块里的可变状态：${byTarget.size} 个被写入的目标，共 ${stateWrites.length} 处写入\n`);
  say("按「对象.一级字段」汇总；「所在函数」取最外层的具名函数。\n");
  say("| 目标 | 写入处数 | 写它的函数（行）| 用到它的函数数 |");
  say("|---|---|---|---|");
  for (const [key, ws] of [...byTarget.entries()].sort((a, b) => b[1].length - a[1].length)) {
    const byFn = new Map();
    for (const w of ws) {
      const top = w.fn.split(" > ")[0];
      if (!byFn.has(top)) byFn.set(top, []);
      byFn.get(top).push(w.line);
    }
    const txt = [...byFn.entries()].slice(0, 10)
      .map(([n, ls]) => `\`${n}\`:${ls.slice(0, 4).join(",")}${ls.length > 4 ? "…" : ""}`).join("、")
      + (byFn.size > 10 ? ` 等 ${byFn.size} 个函数` : "");
    say(`| \`${key}\` | ${ws.length} | ${txt} | ${(readCount.get(key) || new Set()).size} |`);
  }

  // 页面块调用 PhoneModel 的哪些成员
  const used = new Map();
  for (let k = docOpen; k < docClose; k += 1) {
    if (isId(tokens[k], "PhoneModel") && isP(tokens[k + 1], ".") && isId(tokens[k + 2])
        && !isP(tokens[k - 1], ".")) {
      used.set(tokens[k + 2].value, (used.get(tokens[k + 2].value) || 0) + 1);
    }
  }
  const unused = fnMembers.filter((m) => !used.has(m.name)).map((m) => m.name);
  say(`\n### 页面块对 \`PhoneModel\` 的调用：用到 ${used.size} 个成员，共 ${[...used.values()].reduce((a, b) => a + b, 0)} 处\n`);
  say(`页面块没有直接调用的函数成员 ${unused.length} 个（可能只在 \`PhoneModel\` 内部互调，或只给测试用）：`
    + unused.map((n) => `\`${n}\``).join("、") + "。");

  result.phone = { members, defs: defs.map(({ tok, ...d }) => d), writes: stateWrites,
    used: Object.fromEntries(used) };
}

process.stdout.write(lines.join("\n") + "\n");
const outIdx = process.argv.indexOf("--out");
if (outIdx !== -1 && process.argv[outIdx + 1]) {
  mkdirSync(process.argv[outIdx + 1], { recursive: true });
  writeFileSync(join(process.argv[outIdx + 1], "globals.json"), JSON.stringify(result, null, 1));
}
