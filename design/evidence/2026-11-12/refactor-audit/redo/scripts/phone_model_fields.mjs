// 列出基线（7e2d31c）local/ui/m/app.js 里 model 对象每个字段的写入点与读取点。
// 从仓库任意位置运行，只读，不联网：
//   node design/evidence/2026-11-12/refactor-audit/redo/scripts/phone_model_fields.mjs            # 汇总表
//   node .../phone_model_fields.mjs --detail                                                      # 每个字段的写入点、读取点明细
//   node .../phone_model_fields.mjs --json                                                        # 机器可读
//
// 口径（每一步在数什么）：
// 1. 先把注释、字符串、正则字面量抹成空格（保留换行，行号不变）；模板字符串里的 ${...} 表达式保留，因为它们是代码。
// 2. 找所有 `model.<字段>` 出现处，看紧跟的内容判断类别：
//    写入   = `model.x = ...`、复合赋值（+= -= ||= 等）、`++` `--`、`delete model.x`
//    容器改 = `model.x.add(` `.delete(` `.clear(` `.push(` 等就地修改方法
//    内部写 = `model.x.y = ...`、`model.x[k] = ...`（改的是字段里面的东西）
//    读取   = 其余出现处
// 3. 所在函数：按花括号栈找最近的函数头（function 声明、方法简写、箭头函数）；找不到记 <顶层>。
// 4. 「传出」：`model` 作为实参整个传给别的函数（那个函数可能写它，需要另读）；「整体取用」：`= model`、`{...} = model`。
// 5. 声明 = `const model = { ... }` 字面量最外层的键；写入点出现但字面量里没有的字段标「未声明」。
// 6. 范围：PhoneModel 纯函数区里形参也叫 model 的访问同样统计，scope 标 PhoneModel；页面逻辑区标 page。
import { execFileSync } from "node:child_process";

const BASE = "7e2d31c";
const FILE = "local/ui/m/app.js";
const src = execFileSync("git", ["show", `${BASE}:${FILE}`], { encoding: "utf8", maxBuffer: 1 << 26 }).replace(/\r\n/g, "\n");
const lines = src.split("\n");

// ---------- 1. 抹掉注释、字符串、正则 ----------
function mask(text) {
  const out = text.split("");
  const n = text.length;
  let i = 0;
  let lastSig = "";       // 上一个有意义的字符，用来判断 / 是除号还是正则
  const blank = (a, b) => { for (let k = a; k < b; k++) if (out[k] !== "\n") out[k] = " "; };
  const tpl = (start) => {   // 处理模板字符串，返回结束位置（含闭合反引号之后）
    let k = start + 1;
    while (k < n) {
      const c = text[k];
      if (c === "\\") { blank(k, k + 2); k += 2; continue; }
      if (c === "`") { return k + 1; }
      if (c === "$" && text[k + 1] === "{") {
        blank(k, k + 2);
        k += 2;
        let depth = 1;
        while (k < n && depth > 0) {   // ${ } 里是代码：保留，但里面的字符串/嵌套模板要继续处理
          const d = text[k];
          if (d === "'" || d === '"') { const e = skipStr(k, d); blank(k, e); k = e; continue; }
          if (d === "`") { const e = tpl(k); blank(k, e); k = e; continue; }
          if (d === "{") depth++;
          if (d === "}") { depth--; if (depth === 0) { blank(k, k + 1); k++; break; } }
          k++;
        }
        continue;
      }
      blank(k, k + 1);
      k++;
    }
    return k;
  };
  const skipStr = (start, q) => {
    let k = start + 1;
    while (k < n) {
      if (text[k] === "\\") { k += 2; continue; }
      if (text[k] === q) return k + 1;
      if (text[k] === "\n") return k;   // 容错：单引号串不跨行
      k++;
    }
    return k;
  };
  while (i < n) {
    const c = text[i];
    const d = text[i + 1];
    if (c === "/" && d === "/") { let k = i; while (k < n && text[k] !== "\n") k++; blank(i, k); i = k; continue; }
    if (c === "/" && d === "*") { let k = text.indexOf("*/", i + 2); k = k < 0 ? n : k + 2; blank(i, k); i = k; continue; }
    if (c === "'" || c === '"') { const e = skipStr(i, c); blank(i, e); i = e; lastSig = "a"; continue; }
    if (c === "`") { const e = tpl(i); blank(i, i + 1); if (text[e - 1] === "`") blank(e - 1, e); i = e; lastSig = "a"; continue; }
    if (c === "/") {
      const regexOk = lastSig === "" || "(,=:[!&|?{};+-*%<>~^".includes(lastSig);
      if (regexOk) {
        let k = i + 1, inClass = false;
        while (k < n && text[k] !== "\n") {
          if (text[k] === "\\") { k += 2; continue; }
          if (text[k] === "[") inClass = true;
          else if (text[k] === "]") inClass = false;
          else if (text[k] === "/" && !inClass) break;
          k++;
        }
        if (k < n && text[k] === "/") { k++; while (/[a-z]/i.test(text[k] || "")) k++; blank(i, k); i = k; lastSig = "a"; continue; }
      }
    }
    if (!/\s/.test(c)) lastSig = c;
    i++;
  }
  return out.join("");
}
const code = mask(src);

// 行号表
const lineStart = [0];
for (let i = 0; i < code.length; i++) if (code[i] === "\n") lineStart.push(i + 1);
const lineOf = (pos) => { let lo = 0, hi = lineStart.length - 1; while (lo < hi) { const mid = (lo + hi + 1) >> 1; if (lineStart[mid] <= pos) lo = mid; else hi = mid - 1; } return lo + 1; };

// ---------- 3. 函数栈 ----------
const CONTROL = new Set(["if", "for", "while", "switch", "catch", "with", "function", "return", "else", "do", "try", "finally"]);
const funcAt = new Array(code.length);   // 每个位置的函数路径（稍后只对需要的位置求值）
const events = [];                        // {pos, chain}
{
  const stack = [];
  let stmtStart = 0;
  for (let i = 0; i < code.length; i++) {
    const c = code[i];
    if (c === "{") {
      const header = code.slice(stmtStart, i).replace(/^[\s,]+/, "").trim();
      let name = null;
      let m;
      if ((m = /^(?:async\s+)?function\s*\*?\s*([\w$]*)\s*\([^]*\)\s*$/.exec(header))) name = m[1] || "<匿名函数>";
      else if (/=>\s*$/.test(header)) {
        const a = /(?:const|let|var)\s+([\w$]+)\s*=\s*(?:async\s*)?(?:\([^]*\)|[\w$]+)\s*=>\s*$/.exec(header)
          || /([\w$]+)\s*:\s*(?:async\s*)?(?:\([^]*\)|[\w$]+)\s*=>\s*$/.exec(header);
        name = a ? a[1] : "<回调>";
      } else if ((m = /^(?:async\s+)?(?:get\s+|set\s+)?([\w$]+)\s*\([^()]*\)\s*$/.exec(header)) && !CONTROL.has(m[1])) name = m[1];
      stack.push(name);
      stmtStart = i + 1;
    } else if (c === "}") {
      stack.pop();
      stmtStart = i + 1;
    } else if (c === ";") {
      stmtStart = i + 1;
    }
    if (i % 1 === 0) events.push(null);
    if (c === "m") {   // 只在可能的 model 处记函数链，节省内存
      if (code.startsWith("model", i)) funcAt[i] = stack.filter(Boolean).slice();
    }
  }
}
const chainName = (chain) => {
  if (!chain || !chain.length) return "<顶层>";
  const named = chain.filter((x) => !x.startsWith("<"));
  if (!named.length) return chain[chain.length - 1];
  const last = chain[chain.length - 1];
  return last.startsWith("<") ? named[named.length - 1] + ">" + last : last;
};

// ---------- 5. 声明 ----------
const decl = new Map();
const declText = new Map();
let pageStartLine = 0;
{
  const m = /const\s+model\s*=\s*\{/.exec(code);
  if (!m) throw new Error("找不到 const model = {");
  const open = m.index + m[0].length - 1;
  let depth = 0, i = open, close = -1;
  for (; i < code.length; i++) {
    if (code[i] === "{" || code[i] === "[" || code[i] === "(") depth++;
    else if (code[i] === "}" || code[i] === "]" || code[i] === ")") { depth--; if (depth === 0) { close = i; break; } }
  }
  depth = 0;
  for (let k = open; k <= close; k++) {
    const c = code[k];
    if (c === "{" || c === "[" || c === "(") depth++;
    else if (c === "}" || c === "]" || c === ")") depth--;
    else if (depth === 1) {
      const mm = /^([A-Za-z_$][\w$]*)\s*:(?!:)/.exec(code.slice(k));
      if (mm && (k === open + 1 || /[\s,{]/.test(code[k - 1])) && !/[\w$]/.test(code[k - 1] || "")) { decl.set(mm[1], lineOf(k)); declText.set(mm[1], src.slice(k, Math.min(src.indexOf("\n", k) < 0 ? src.length : src.indexOf("\n", k), k + 60)).trimEnd()); k += mm[1].length; }
    }
  }
  const pg = /if\s*\(\s*typeof\s+document\s*!==\s*"undefined"\s*\)\s*\{/.exec(src);   // 字符串没被抹的原文里找
  pageStartLine = pg ? lineOf(pg.index) : lineOf(m.index);
  decl.set("__literal__", [lineOf(m.index), lineOf(close)]);
}

// ---------- 2. 找 model.字段 ----------
const MUTATORS = new Set(["add", "delete", "clear", "push", "pop", "shift", "unshift", "splice", "sort", "reverse", "set", "fill"]);
const fields = new Map();
const touch = (name) => { if (!fields.has(name)) fields.set(name, { name, writes: [], mutates: [], inner: [], reads: [] }); return fields.get(name); };
const passed = [];
const whole = [];
const re = /(?<![\w$.])model\s*\.\s*([A-Za-z_$][\w$]*)/g;
let mt;
while ((mt = re.exec(code))) {
  const name = mt[1];
  const startPos = mt.index;
  const line = lineOf(startPos);
  const chain = funcAt[startPos];
  const eol = src.indexOf("\n", startPos);
  const rec = { line, func: chainName(chain), scope: line < pageStartLine ? "PhoneModel" : "page", text: src.slice(startPos, Math.min(eol < 0 ? src.length : eol, startPos + 90)).trimEnd() };
  let k = startPos + mt[0].length;
  const rest = code.slice(k, k + 200);
  const before = code.slice(Math.max(0, startPos - 12), startPos);
  const f = touch(name);
  let m2;
  if (/(\+\+|--)\s*$/.test(before) || /\bdelete\s+$/.test(before)) { f.writes.push(Object.assign(rec, { how: "前置自增/delete" })); continue; }
  if ((m2 = /^\s*(\+\+|--)/.exec(rest))) { f.writes.push(Object.assign(rec, { how: m2[1] })); continue; }
  if ((m2 = /^\s*(\|\|=|&&=|\?\?=|\+=|-=|\*=|\/=|%=|=)(?![=>])/.exec(rest))) { f.writes.push(Object.assign(rec, { how: m2[1] })); continue; }
  if ((m2 = /^\s*\.\s*([A-Za-z_$][\w$]*)\s*\(/.exec(rest)) && MUTATORS.has(m2[1])) { f.mutates.push(Object.assign(rec, { how: "." + m2[1] + "()" })); continue; }
  // 内部写：链式属性或下标后跟赋值
  let r = rest, consumed = 0, chainKeys = "";
  for (;;) {
    const p = /^\s*(\.\s*[A-Za-z_$][\w$]*|\[[^\]]*\])/.exec(r);
    if (!p) break;
    chainKeys += p[1].replace(/\s+/g, "");
    r = r.slice(p[0].length); consumed += p[0].length;
  }
  if (chainKeys && (m2 = /^\s*(\|\|=|&&=|\?\?=|\+=|-=|\*=|\/=|%=|=)(?![=>])/.exec(r))) { f.inner.push(Object.assign(rec, { how: chainKeys + " " + m2[1] })); continue; }
  f.reads.push(rec);
}
// 传出与整体取用（model 后面不跟点）
const re2 = /(?<![\w$.])model(?![\w$])(?!\s*\.)/g;
while ((mt = re2.exec(code))) {
  const line = lineOf(mt.index);
  const text = lines[line - 1].trim();
  if (/^\s*const\s+model\s*=/.test(lines[line - 1]) || /^\s*model\s*[:,]/.test(lines[line - 1].trim())) continue;
  if (/\bmodel\s*=>/.test(code.slice(mt.index, mt.index + 12))) continue;
  const around = code.slice(Math.max(0, mt.index - 40), mt.index + 12);
  if (/=\s*model\s*[;,)]?\s*$/.test(code.slice(Math.max(0, mt.index - 12), mt.index + 7)) || /\}\s*=\s*model/.test(around)) whole.push({ line, text });
  else passed.push({ line, func: chainName(funcAt[mt.index]) , text: text.slice(0, 90) });
}


// ---------- 别名写：const x = model.字段; 之后 x.属性 = ... 也是在改字段里面的东西 ----------
// 有效范围：从这次声明到「同名别名的下一次声明」或 60 行以内，取先到者。
const aliasWrites = [];
{
  const ra = /(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*model\s*\.\s*([A-Za-z_$][\w$]*)\s*;/g;
  const decls = [];
  let ma;
  while ((ma = ra.exec(code))) decls.push({ alias: ma[1], field: ma[2], index: ma.index, mlen: ma[0].length, model: ma.index + ma[0].search(/model/) });
  decls.forEach((dc, i) => {
    const next = decls.slice(i + 1).find((x) => x.alias === dc.alias);
    const declLine = lineOf(dc.index);
    const esc = dc.alias.replace(/\$/g, "\$");
    const rw = new RegExp(String.raw`(?<![\w$.])` + esc + String.raw`\s*\.\s*([A-Za-z_$][\w$]*)\s*(\|\|=|&&=|\?\?=|\+=|-=|=)(?![=>])`, "g");
    rw.lastIndex = dc.index + dc.mlen;
    let mw;
    while ((mw = rw.exec(code))) {
      const ln = lineOf(mw.index);
      if (ln - declLine > 60 || (next && mw.index > next.index)) break;
      aliasWrites.push({ field: dc.field, alias: dc.alias, declLine, line: ln, prop: mw[1], how: mw[2], func: chainName(funcAt[dc.model]), text: lines[ln - 1].trim().slice(0, 90) });
    }
  });
}

// ---------- 输出 ----------
const rows = [...fields.values()].map((f) => ({
  name: f.name,
  declared: decl.has(f.name) ? decl.get(f.name) : null,
  nWrite: f.writes.length, nMutate: f.mutates.length, nInner: f.inner.length, nRead: f.reads.length,
  writeFuncs: [...new Set([...f.writes, ...f.mutates, ...f.inner].map((x) => x.func))],
  writes: f.writes, mutates: f.mutates, inner: f.inner, reads: f.reads,
})).sort((a, b) => a.name.localeCompare(b.name));
const declaredNotUsed = [...decl.keys()].filter((k) => k !== "__literal__" && !fields.has(k));

if (process.argv.includes("--json")) {
  console.log(JSON.stringify({ base: BASE, file: FILE, pageStartLine, literal: decl.get("__literal__"), declaredCount: decl.size - 1, rows, declaredNotUsed, aliasWrites, declText: Object.fromEntries(declText), passed, whole }, null, 1));
} else {
  console.log(`基线 ${BASE}  文件 ${FILE}  共 ${lines.length} 行；页面逻辑区从第 ${pageStartLine} 行起；model 字面量 ${decl.get("__literal__").join("-")} 行`);
  console.log(`字面量声明的字段 ${decl.size - 1} 个；代码里出现 model.<字段> 的字段 ${rows.length} 个；声明了但全文没有 model.字段 出现的 ${declaredNotUsed.length} 个：${declaredNotUsed.join("、") || "无"}`);
  const writtenRows = rows.filter((r) => r.nWrite + r.nMutate + r.nInner > 0);
  console.log(`被写入（含容器就地修改、内部字段写）的字段 ${writtenRows.length} 个；写入点合计 ${rows.reduce((s, r) => s + r.nWrite + r.nMutate + r.nInner, 0)} 处（其中直接赋值类 ${rows.reduce((s, r) => s + r.nWrite, 0)}，容器就地修改 ${rows.reduce((s, r) => s + r.nMutate, 0)}，内部字段写 ${rows.reduce((s, r) => s + r.nInner, 0)}）；读取点合计 ${rows.reduce((s, r) => s + r.nRead, 0)} 处`);
  const undeclared = rows.filter((r) => r.nWrite + r.nMutate + r.nInner > 0 && r.declared === null).map((r) => r.name);
  console.log(`被写入但字面量里没声明的字段 ${undeclared.length} 个：${undeclared.join("、") || "无"}`);
  console.log(`经别名写字段内部（const x = model.字段; x.属性 = ...）${aliasWrites.length} 处：${aliasWrites.map((a) => a.field + "." + a.prop + "@" + a.line).join("、") || "无"}`);
  console.log(`整个 model 作为实参传出 ${passed.length} 处，整体取用 ${whole.length} 处（见 --detail）`);
  console.log("\n字段\t声明行\t写\t容器改\t内部写\t读\t写入所在函数");
  for (const r of rows) console.log([r.name, r.declared ?? "未声明", r.nWrite, r.nMutate, r.nInner, r.nRead, r.writeFuncs.join("、") || "-"].join("\t"));
  if (process.argv.includes("--detail")) {
    for (const r of rows) {
      console.log(`\n## ${r.name}  声明行 ${r.declared ?? "未声明"}`);
      for (const w of r.writes) console.log(`  写   ${w.line}\t${w.scope}\t${w.func}\t${w.how}`);
      for (const w of r.mutates) console.log(`  容器改 ${w.line}\t${w.scope}\t${w.func}\t${w.how}`);
      for (const w of r.inner) console.log(`  内部写 ${w.line}\t${w.scope}\t${w.func}\t${w.how}`);
      console.log(`  读   ${r.reads.map((x) => x.line + "@" + x.func).join(" ")}`);
    }
    console.log("\n## model 作为实参传出");
    for (const p of passed) console.log(`  ${p.line}\t${p.func}\t${p.text}`);
    console.log("\n## model 整体取用");
    for (const p of whole) console.log(`  ${p.line}\t${p.text}`);
  }
}
