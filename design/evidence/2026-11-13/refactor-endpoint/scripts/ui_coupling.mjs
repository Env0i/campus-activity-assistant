// 表 B：前端文件耦合（计划 decisions D4）。
//
// 定义与引用的识别按 D4 要求照搬 2026-11-12 审计的 jslex.mjs / jsscan.mjs（两文件逐字未改，
// 副本就在本目录，便于脚本被复制到别处时仍能运行）；load / shadowed / topDefs / scanUses
// 四个函数原样照搬自那轮的 globals.mjs，不另写一套词法。
//
// 从仓库根运行：
//   node design/evidence/2026-11-13/refactor-endpoint/scripts/ui_coupling.mjs
// ownership.py 会带 --defs 调用本脚本，取「顶层名字 → 定义文件」的 JSON。
//
// 只读，只用 node 自带能力；按名字匹配，不做作用域分析，局限与那轮 README C2 一致。

import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";
import { KEYWORDS } from "./jslex.mjs";
import { findFunctions } from "./jsscan.mjs";

const UI = "local/ui";
const ASSIGN_OPS = new Set(["=", "+=", "-=", "*=", "/=", "%=", "**=", "<<=", ">>=", ">>>=",
  "&=", "|=", "^=", "&&=", "||=", "??="]);
// 原地修改容器的方法：Map / Set / Array 上会改内容的那些。
const MUTATORS = new Set(["push", "pop", "shift", "unshift", "splice", "sort", "reverse", "fill",
  "set", "add", "delete", "clear"]);

// D2 的固定对照表（出处：.claude/plans/plan-20261113-refactor-endpoint-evidence.yaml）。
const D2_FILES = new Map(Object.entries({
  "views/phone.js": "步骤 1A 组件与手机访问",
  "views/settings.js": "步骤 1A 组件与手机访问",
  "state/login.js": "步骤 1B 登录",
  "views/login.js": "步骤 1B 登录",
  "views/relogin.js": "步骤 1B 登录",
  "views/status-cards.js": "步骤 1B 登录",
  "views/plan-panel.js": "步骤 1C 计划栏",
  "controllers/plan.js": "步骤 1C 计划栏",
  "controllers/plan-events.js": "步骤 1C 计划栏",
  "state/plan.js": "步骤 1C 计划栏",
  "state/task-display.js": "步骤 1C 计划栏",
  "controllers/refresh.js": "步骤 1 共用",
  "app.js": "步骤 1 共用",
  "state/store.js": "步骤 1 共用",
}));
const M_PREFIX = "m/";
function stepOf(rel) {
  if (rel.startsWith(M_PREFIX)) return "手机页";
  return D2_FILES.get(rel) || "未排进任何一步";
}

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

// index.html 之外、local/ui 下（不含 m/）还有的 .js：一并纳入，标注来源。
function extraScripts(order) {
  const known = new Set(order);
  const out = [];
  const walk = (dir, rel) => {
    for (const name of readdirSync(dir)) {
      if (name === "m") continue;
      const full = join(dir, name);
      const r = rel ? rel + "/" + name : name;
      if (statSync(full).isDirectory()) walk(full, r);
      else if (name.endsWith(".js") && !known.has(r)) out.push(r);
    }
  };
  walk(UI, "");
  return out.sort();
}

function layerOf(rel) {
  if (rel.startsWith("state/")) return "state";
  if (rel.startsWith("views/")) return "views";
  if (rel.startsWith("controllers/")) return "controllers";
  return "root";
}

// —— 以下四个函数照搬自 design/evidence/2026-11-12/refactor-audit/scripts/globals.mjs ——
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
  const inner = new Array(tokens.length).fill(null);
  for (const f of funcs) {
    for (let k = f.startTok; k <= f.bodyClose; k += 1) inner[k] = f;
  }
  for (const f of funcs) f.locals = new Set();
  const declare = (k, name) => {
    let f = inner[k];
    if (f) f.locals.add(name);
  };
  for (const f of funcs) {
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

function shadowed(file, k, name) {
  let f = file.inner[k];
  while (f) {
    if (f.locals.has(name)) return true;
    f = f.parent;
  }
  return false;
}

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

function scanUses(file, names, skipTok) {
  const { tokens } = file;
  const refs = [];
  const writes = [];
  for (let k = 0; k < tokens.length; k += 1) {
    const t = tokens[k];
    if (t.type !== "id" || !names.has(t.value) || skipTok.has(k)) continue;
    const prev = tokens[k - 1];
    const next = tokens[k + 1];
    if (isP(prev, ".") || isP(prev, "?.")) continue;
    if (isP(next, ":") && (isP(prev, "{") || isP(prev, ","))) continue;
    if (isId(prev, "function")) continue;
    if (shadowed(file, k, t.value)) continue;
    const fn = file.inner[k];
    const fnName = fn ? fn.qualname : "<顶层>";
    refs.push({ name: t.value, line: t.line, tok: k, call: isP(next, "("), topLevel: !fn });
    writes.push(...collectWrites(tokens, k, fnName));
  }
  return { refs, writes };
}

function collectWrites(tokens, k, fnName) {
  const out = [];
  const chain = readChainText(tokens, k);
  const after = tokens[chain.end];
  const joined = chain.path.join(".").replace(/\.\[/g, "[");
  if (after && after.type === "punct" && ASSIGN_OPS.has(after.value)) {
    out.push({ name: tokens[k].value, path: joined, line: tokens[k].line, how: after.value, fn: fnName });
  } else if (isP(after, "++") || isP(after, "--") || isP(tokens[k - 1], "++") || isP(tokens[k - 1], "--")) {
    out.push({ name: tokens[k].value, path: joined, line: tokens[k].line, how: "++/--", fn: fnName });
  } else if (isId(tokens[k - 1], "delete") && chain.path.length > 1) {
    out.push({ name: tokens[k].value, path: joined, line: tokens[k].line, how: "delete", fn: fnName });
  } else if (isP(after, "(") && chain.path.length >= 2 && MUTATORS.has(chain.path[chain.path.length - 1])) {
    const target = chain.path.slice(0, -1).join(".").replace(/\.\[/g, "[");
    out.push({ name: tokens[k].value, path: target, line: tokens[k].line,
      how: `.${chain.path[chain.path.length - 1]}()`, fn: fnName });
  } else if (isP(tokens[k - 1], "(") && isId(tokens[k - 2], "assign") && isP(tokens[k - 3], ".")
             && isId(tokens[k - 4], "Object")) {
    out.push({ name: tokens[k].value, path: joined, line: tokens[k].line, how: "Object.assign", fn: fnName });
  }
  return out;
}

function readChainText(tokens, k) {
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
// —— 照搬结束 ——

function physicalLines(src) {
  const body = src.replace(/\r\n/g, "\n");
  return (body.endsWith("\n") ? body.slice(0, -1) : body).split("\n").length;
}

const lines = [];
const say = (s = "") => lines.push(s);

const order = scriptOrder(join(UI, "index.html"));
const rels = [...order, ...extraScripts(order)];
const files = rels.map((rel) => ({
  rel,
  layer: layerOf(rel),
  extra: !order.includes(rel),
  ...load(join(UI, rel)),
}));

const names = new Map(); // 名字 → { file(rel), kind, line }
const dupes = [];        // 同一名字在两个文件里都有顶层定义
const sameFileDupes = []; // 同一文件里同名顶层定义出现两次以上
for (const f of files) {
  const seenInFile = new Map();
  const { defs, warn } = topDefs(f);
  f.defs = defs;
  f.skip = new Set(defs.map((d) => d.tok));
  for (const d of defs) {
    const prev = seenInFile.get(d.name);
    if (prev) sameFileDupes.push(`${d.name}: ${f.rel}:${prev} 与 :${d.line}`);
    else seenInFile.set(d.name, d.line);
    if (names.has(d.name) && names.get(d.name).file !== f.rel) {
      dupes.push(`${d.name}: ${names.get(d.name).file} / ${f.rel}`);
    } else if (!names.has(d.name)) {
      names.set(d.name, { file: f.rel, kind: d.kind, line: d.line });
    }
  }
  for (const w of warn) say(`<!-- ${w} -->`);
}
const perFileDefSum = files.reduce((acc, f) => acc + f.defs.length, 0);

const sNames = new Map([["S", { file: "(state store)" }]]);
for (const f of files) {
  f.lineCount = physicalLines(f.src);
  const { refs, writes } = scanUses(f, names, f.skip);
  f.refs = refs;
  const sw = scanUses(f, sNames, f.skip).writes;
  f.sWrites = sw.length;
}

const STEP1 = new Set([...D2_FILES.keys()]);
function defsInStep1(name) {
  const d = names.get(name);
  return !!d && STEP1.has(d.file);
}

// 每个未排进脚本与步骤 1 文件的相互引用
const crossRows = [];
for (const f of files) {
  if (stepOf(f.rel) !== "未排进任何一步") continue;
  const outNames = new Set(f.refs.map((r) => r.name).filter((n) => {
    const d = names.get(n);
    return d && STEP1.has(d.file) && d.file !== f.rel;
  }));
  const inNames = new Set();
  for (const g of files) {
    if (!STEP1.has(g.rel)) continue;
    for (const r of g.refs) {
      const d = names.get(r.name);
      if (d && d.file === f.rel) inNames.add(r.name);
    }
  }
  crossRows.push({
    rel: f.rel,
    outCount: outNames.size,
    outList: [...outNames].sort().join("、") || "—",
    inCount: inNames.size,
    inList: [...inNames].sort().join("、") || "—",
  });
}

if (process.argv.includes("--defs")) {
  const out = {};
  for (const [name, d] of names) out[name] = d.file;
  process.stdout.write(JSON.stringify({ defs: out, dupes }) + "\n");
} else {
  say("### B1 每个脚本：行数、顶层函数、全局名字、S 写入");
  say("");
  say("量什么：local/ui 下不含 m/ 的每个脚本（按 index.html 加载顺序，不在顺序里的附后并标注）；行数是物理行；顶层函数数只数 function 声明；全局名字数是顶层定义（function/const/let/var/class/window.X）个数；S 写入处数按 globals.mjs 的写入判定。");
  say("");
  say("| 序 | 文件 | 层 | 归属 | 行数 | 顶层函数数 | 全局名字数 | S 写入处数 |");
  say("|---|---|---|---|---|---|---|---|");
  files.forEach((f, i) => {
    const funcs = f.defs.filter((d) => d.kind === "function").length;
    const mark = f.extra ? "（不在 index.html）" : "";
    say(`| ${i + 1} | \`local/ui/${f.rel}\`${mark} | ${f.layer} | ${stepOf(f.rel)} | ${f.lineCount} | ${funcs} | ${f.defs.length} | ${f.sWrites} |`);
  });
  say("");
  say(`文件总数：${files.length}（index.html 顺序 ${order.length} 个，另外发现 ${files.length - order.length} 个）。`);
  say(`同一名字在两个文件里都有顶层定义：${dupes.length} 处${dupes.length ? "：" + dupes.join("；") : ""}。`);
  say(`同一文件内同名顶层定义：${sameFileDupes.length} 处${sameFileDupes.length ? "：" + sameFileDupes.join("；") : ""}；全局名字按唯一名计 ${names.size} 个，逐文件定义合计 ${perFileDefSum} 个（两数之差即同名重复定义）。`);
  say("");
  say("### B2 未排进任何一步的脚本与步骤 1 文件的相互引用");
  say("");
  say("量什么：左边是它引用的定义在步骤 1 文件（1A、1B、1C、共用）里的名字数与清单；右边是它定义、被步骤 1 文件引用的名字数与清单。按名字匹配，排除属性访问、对象字面量键、本文件同名局部声明。");
  say("");
  say("| 文件 | 引用步骤 1 定义的名字数 | 名字 | 被步骤 1 引用的名字数 | 名字 |");
  say("|---|---|---|---|---|");
  for (const r of crossRows) {
    say(`| \`local/ui/${r.rel}\` | ${r.outCount} | ${r.outList} | ${r.inCount} | ${r.inList} |`);
  }
  say("");
  say(`未排进脚本共 ${crossRows.length} 个。`);
  process.stdout.write(lines.join("\n") + "\n");
}
