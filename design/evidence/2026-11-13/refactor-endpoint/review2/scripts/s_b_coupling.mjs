// review2 表 B 独立复算：local/ui（不含 m/）脚本耦合（计划 D4 口径）。
// 词法原语复用仓库工具 tools/code_shape/jslex.mjs + jsscan.mjs（入库工具）；分析逻辑本轮重写。
// 从仓库根运行：node design/evidence/2026-11-13/refactor-endpoint/review2/scripts/s_b_coupling.mjs

import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";
import { KEYWORDS } from "../../../../../../tools/code_shape/jslex.mjs";
import { findFunctions } from "../../../../../../tools/code_shape/jsscan.mjs";

const UI = "local/ui";
const ASSIGN = new Set(["=", "+=", "-=", "*=", "/=", "%=", "**=", "<<=", ">>=", ">>>=",
  "&=", "|=", "^=", "&&=", "||=", "??="]);
const MUT = new Set(["push", "pop", "shift", "unshift", "splice", "sort", "reverse", "fill",
  "set", "add", "delete", "clear"]);
const D2 = new Map(Object.entries({
  "views/phone.js": "1A", "views/settings.js": "1A",
  "state/login.js": "1B", "views/login.js": "1B", "views/relogin.js": "1B",
  "views/status-cards.js": "1B",
  "views/plan-panel.js": "1C", "controllers/plan.js": "1C",
  "controllers/plan-events.js": "1C", "state/plan.js": "1C", "state/task-display.js": "1C",
  "controllers/refresh.js": "1共用", "app.js": "1共用", "state/store.js": "1共用",
}));

const isP = (t, v) => !!t && t.type === "punct" && t.value === v;
const isId = (t, v) => !!t && t.type === "id" && (v === undefined || t.value === v);

function order() {
  const html = readFileSync(join(UI, "index.html"), "utf8");
  const out = [];
  let m;
  const re = /<script\s+[^>]*src="([^"]+)"/g;
  while ((m = re.exec(html))) out.push(m[1]);
  return out;
}

function extras(known) {
  const out = [];
  const walk = (dir, rel) => {
    for (const name of readdirSync(dir).sort()) {
      if (name === "m") continue;
      const full = join(dir, name);
      const r = rel ? rel + "/" + name : name;
      if (statSync(full).isDirectory()) walk(full, r);
      else if (name.endsWith(".js") && !known.has(r)) out.push(r);
    }
  };
  walk(UI, "");
  return out;
}

function load(path) {
  const src = readFileSync(path, "utf8");
  const { tokens, funcs, balanced } = findFunctions(src);
  const brace = new Array(tokens.length).fill(0);
  const paren = new Array(tokens.length).fill(0);
  let b = 0, p = 0;
  for (let k = 0; k < tokens.length; k += 1) {
    const t = tokens[k];
    if (t.type === "punct" && t.value === "}") b -= 1;
    if (t.type === "punct" && (t.value === ")" || t.value === "]")) p -= 1;
    brace[k] = b; paren[k] = p;
    if (t.type === "punct" && (t.value === "{" || t.value === "${")) b += 1;
    if (t.type === "punct" && (t.value === "(" || t.value === "[")) p += 1;
  }
  const inner = new Array(tokens.length).fill(null);
  for (const f of funcs) for (let k = f.startTok; k <= f.bodyClose; k += 1) inner[k] = f;
  for (const f of funcs) f.locals = new Set();
  for (const f of funcs) {
    if (f.paramOpen === f.paramClose && tokens[f.paramOpen].type === "id") {
      f.locals.add(tokens[f.paramOpen].value);
    } else {
      for (let k = f.paramOpen + 1; k < f.paramClose; k += 1) {
        const t = tokens[k], prev = tokens[k - 1];
        if (t.type === "id" && !KEYWORDS.has(t.value)
          && (isP(prev, "(") || isP(prev, ",") || isP(prev, "...") || isP(prev, "{")
            || isP(prev, "[") || isP(prev, ":")) && !isP(tokens[k + 1], ":")) {
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
      const nx = tokens[k + 1];
      if (isId(nx) && !KEYWORDS.has(nx.value)) {
        inner[k].locals.add(nx.value);
        let j = k + 2;
        while (j < tokens.length && tokens[j].line === tokens[j - 1].line) {
          if (isP(tokens[j], ",") && brace[j] === brace[k] && paren[j] === paren[k]
            && isId(tokens[j + 1]) && !KEYWORDS.has(tokens[j + 1].value)) {
            inner[k].locals.add(tokens[j + 1].value);
          }
          if (isP(tokens[j], ";") && brace[j] === brace[k]) break;
          j += 1;
        }
      }
    }
    if (isId(t, "catch") && isP(tokens[k + 1], "(") && isId(tokens[k + 2])) {
      inner[k].locals.add(tokens[k + 2].value);
    }
  }
  return { src, tokens, funcs, balanced, brace, paren, inner };
}

function shadowed(file, k, name) {
  let f = file.inner[k];
  while (f) {
    if (f.locals.has(name)) return true;
    f = f.parent;
  }
  return false;
}

function topDefs(file) {
  const { tokens, brace, paren } = file;
  const defs = [];
  for (let k = 0; k < tokens.length; k += 1) {
    const t = tokens[k];
    if (t.type !== "id") continue;
    const top = brace[k] === 0 && paren[k] === 0;
    if (top && t.value === "function" && isId(tokens[k + 1]) && !isP(tokens[k - 1], ".")) {
      defs.push({ name: tokens[k + 1].value, kind: "function", line: t.line, tok: k + 1 });
    } else if (top && (t.value === "const" || t.value === "let" || t.value === "var")) {
      const nx = tokens[k + 1];
      if (isId(nx) && !KEYWORDS.has(nx.value)) {
        defs.push({ name: nx.value, kind: t.value, line: t.line, tok: k + 1 });
      }
    } else if (top && t.value === "class" && isId(tokens[k + 1])) {
      defs.push({ name: tokens[k + 1].value, kind: "class", line: t.line, tok: k + 1 });
    } else if ((t.value === "window" || t.value === "globalThis") && isP(tokens[k + 1], ".")
      && isId(tokens[k + 2]) && isP(tokens[k + 3], "=") && !isP(tokens[k - 1], ".")) {
      defs.push({ name: tokens[k + 2].value, kind: "window", line: t.line, tok: k + 2 });
    }
  }
  return defs;
}

function chain(tokens, k) {
  const path = [tokens[k].value];
  let j = k + 1;
  for (;;) {
    if ((isP(tokens[j], ".") || isP(tokens[j], "?.")) && isId(tokens[j + 1])) {
      path.push(tokens[j + 1].value); j += 2;
    } else if (isP(tokens[j], "[") && tokens[j].match !== undefined) {
      path.push("[…]"); j = tokens[j].match + 1;
    } else break;
  }
  return path;
}

function uses(file, skipTok) {
  const { tokens } = file;
  const refs = [], writes = [];
  for (let k = 0; k < tokens.length; k += 1) {
    const t = tokens[k];
    if (t.type !== "id" || skipTok.has(k)) continue;
    const prev = tokens[k - 1], nx = tokens[k + 1];
    if (isP(prev, ".") || isP(prev, "?.")) continue;
    if (isP(nx, ":") && (isP(prev, "{") || isP(prev, ","))) continue;
    if (isId(prev, "function")) continue;
    if (shadowed(file, k, t.value)) continue;
    const fn = file.inner[k];
    const fnName = fn ? fn.qualname : "<顶层>";
    refs.push({ name: t.value, line: t.line });
    const path = chain(tokens, k);
    const after = tokens[chainEnd(tokens, k)];
    const joined = path.join(".").replace(/\.\[/g, "[");
    const w = (target, how) => writes.push({ name: t.value, path: target, line: t.line, how, fn: fnName });
    if (after && after.type === "punct" && ASSIGN.has(after.value)) w(joined, after.value);
    else if (isP(after, "++") || isP(after, "--") || isP(prev, "++") || isP(prev, "--")) w(joined, "++/--");
    else if (isId(prev, "delete") && path.length > 1) w(joined, "delete");
    else if (isP(after, "(") && path.length >= 2 && MUT.has(path[path.length - 1])) {
      w(path.slice(0, -1).join(".").replace(/\.\[/g, "["), "." + path[path.length - 1] + "()");
    } else if (isP(prev, "(") && isId(tokens[k - 2], "assign") && isP(tokens[k - 3], ".")
      && isId(tokens[k - 4], "Object")) w(joined, "Object.assign");
  }
  return { refs, writes };
}

function chainEnd(tokens, k) {
  let j = k + 1;
  for (;;) {
    if ((isP(tokens[j], ".") || isP(tokens[j], "?.")) && isId(tokens[j + 1])) j += 2;
    else if (isP(tokens[j], "[") && tokens[j].match !== undefined) j = tokens[j].match + 1;
    else break;
  }
  return j;
}

const stepOf = (rel) => (rel.startsWith("m/") ? "手机页" : (D2.get(rel) || "未排进"));

const orderRels = order();
const rels = [...orderRels, ...extras(new Set(orderRels))];
const files = rels.map((rel) => ({ rel, ...load(join(UI, rel)) }));

const names = new Map();
const sameFileDupes = [];
for (const f of files) {
  f.defs = topDefs(f);
  f.skip = new Set(f.defs.map((d) => d.tok));
  const seen = new Map();
  for (const d of f.defs) {
    if (seen.has(d.name)) sameFileDupes.push(`${d.name}: ${f.rel}:${seen.get(d.name)} 与 :${d.line}`);
    else seen.set(d.name, d.line);
    if (!names.has(d.name)) names.set(d.name, f.rel);
  }
}
const defSum = files.reduce((a, f) => a + f.defs.length, 0);

const STEP1 = new Set([...D2.keys()]);
for (const f of files) {
  const { refs, writes } = uses(f, f.skip);
  f.refs = refs;
  f.sWrites = writes.filter((x) => x.name === "S").length;
}

console.log("## review2 表 B 独立复算");
console.log();
console.log("| 序 | 文件 | 归属 | 行数 | 顶层函数数 | 全局名字数 | S 写入处数 |");
console.log("|---|---|---|---|---|---|---|");
files.forEach((f, i) => {
  const body = f.src.replace(/\r\n/g, "\n");
  const lines = (body.endsWith("\n") ? body.slice(0, -1) : body).split("\n").length;
  const fnCount = f.defs.filter((d) => d.kind === "function").length;
  console.log(`| ${i + 1} | \`local/ui/${f.rel}\` | ${stepOf(f.rel)} | ${lines} | ${fnCount} | ${f.defs.length} | ${f.sWrites} |`);
});
console.log();
console.log(`文件总数 ${files.length}（index.html ${orderRels.length} + 额外 ${files.length - orderRels.length}）；同一名字跨文件顶层定义 0 处核对值：${
  (() => { const seen = new Map(); let dup = 0;
    for (const f of files) for (const d of f.defs) { if (seen.has(d.name) && seen.get(d.name) !== f.rel) dup += 1; else seen.set(d.name, f.rel); }
    return dup; })()}；同文件同名 ${sameFileDupes.length} 处${sameFileDupes.length ? "：" + sameFileDupes.join("；") : ""}；唯一名 ${names.size} / 逐文件合计 ${defSum}。`);
console.log();
console.log("### 未排进脚本与步骤 1 文件的相互引用");
console.log();
console.log("| 文件 | 引用步骤1定义名数 | 名字 | 被步骤1引用名数 | 名字 |");
console.log("|---|---|---|---|---|");
let nUnplaced = 0;
for (const f of files) {
  if (stepOf(f.rel) !== "未排进") continue;
  nUnplaced += 1;
  const outN = new Set(f.refs.map((r) => r.name).filter((n) => {
    const d = names.get(n);
    return d && STEP1.has(d) && d !== f.rel;
  }));
  const inN = new Set();
  for (const g of files) {
    if (!STEP1.has(g.rel)) continue;
    for (const r of g.refs) if (names.get(r.name) === f.rel) inN.add(r.name);
  }
  const fmt = (s) => [...s].sort().join("、") || "—";
  console.log(`| \`local/ui/${f.rel}\` | ${outN.size} | ${fmt(outN)} | ${inN.size} | ${fmt(inN)} |`);
}
console.log();
console.log(`未排进脚本共 ${nUnplaced} 个。`);
