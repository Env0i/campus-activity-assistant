#!/usr/bin/env node
/* phone_model_fields.mjs —— T2「手机页状态追踪」清点脚本（只读）。
 *
 * 作用：对基线提交 7e2d31c 的 local/ui/m/app.js 做静态解析，列出页面状态对象
 * model（基线第 1386-1422 行的字面量）的每个字段：全部写入点与读取点
 * （行号 + 所在函数名），输出 JSON 到 stdout。
 *
 * 复跑（仓库根）：
 *   node design/evidence/2026-11-12/refactor-audit/redo/zcode/plan/scripts/phone_model_fields.mjs
 *
 * 实现：child_process 执行 `git show 7e2d31c:local/ui/m/app.js` 取基线内容；
 * 自写词法扫描（跳过注释、字符串、正则字面量）得记号流，再单遍扫描：
 *   1) 花括号配对 + 函数帧识别，得每个位置所在的函数名；函数名尽力回溯——
 *      具名函数/方法用名字，赋值箭头用赋值目标，调用实参里的箭头用
 *      「最近调用名›回调」，起不出名字记 <anon@行>；表达式体箭头不单独成帧，
 *      其体归入外层函数。
 *   2) model 访问分类：
 *      写入 = 直接赋值 model.X = …／复合赋值 += 等／子字段赋值 model.X.y = …／
 *             条件赋值（同一词形，条件在行上）／原地变更方法
 *             model.X.clear()/add()/delete()/push()…／Object.assign(model,…)；
 *      读取 = 其余表达式引用；裸 model（作实参传递、PhoneUI 导出）单独记。
 *
 * 已知解析不到的形态（phone.md 有对应说明）：
 *   a) 经局部别名写入：`const pending = model.pending; pending.done = true` ——
 *      不在 model.X 词形上，脚本数不到；pending 的别名写入在 phone.md 人工补注。
 *   b) 计算成员 model[expr]、with/eval/Proxy —— 基线没有，也无法静态枚举。
 *   c) 模板字符串 ${…} 内的引用按整段字符串处理不数（基线没有模板字符串）。
 *   d) 字符串下标 window["model"] 数不到（基线没有）。
 *   e) 解构写入 [model.a] = … / ({a: model.b} = …) 基线不存在；脚本不识别，出现会漏数。
 *   f) const model = {…} 字面量本身不算写入点，登记为各字段的声明位置（declaredAt）。
 * 行号 = 基线 7e2d31c 的物理行（1 起）。
 */
import { execFileSync } from "node:child_process";

const COMMIT = "7e2d31c";
const FILE = "local/ui/m/app.js";
const MUTATORS = new Set(["push", "pop", "shift", "unshift", "splice", "clear", "add",
  "delete", "set", "remove", "insert", "extend", "update", "sort", "reverse", "fill"]);
const KEYWORDS = new Set(["if", "else", "for", "while", "do", "switch", "case", "default",
  "try", "catch", "finally", "return", "typeof", "instanceof", "new", "delete", "void",
  "in", "of", "var", "let", "const", "function", "class", "extends", "super", "this",
  "null", "true", "false", "break", "continue", "throw", "await", "async", "yield"]);
const ASSIGN_OPS = ["=", "+=", "-=", "*=", "/=", "%=", "&&=", "||=", "??="];

function loadBaseline() {
  return execFileSync("git", ["show", `${COMMIT}:${FILE}`],
    { maxBuffer: 64 * 1024 * 1024, encoding: "utf8" });
}

function lex(src) {
  const toks = [];
  let i = 0, line = 1;
  const n = src.length;
  const isRegexPos = () => {
    const p = toks.length ? toks[toks.length - 1] : null;
    if (!p) return true;
    if (p.t === "num" || p.t === "str" || p.t === "regex") return false;
    if (p.t === "punct") return !(p.v === ")" || p.v === "]");
    if (p.t === "id") return KEYWORDS.has(p.v) && p.v !== "this";
    return true;
  };
  while (i < n) {
    const c = src[i];
    if (c === "\n") { line += 1; i += 1; continue; }
    if (c === " " || c === "\t" || c === "\r") { i += 1; continue; }
    if (c === "/" && src[i + 1] === "/") { while (i < n && src[i] !== "\n") i += 1; continue; }
    if (c === "/" && src[i + 1] === "*") {
      i += 2;
      while (i < n && !(src[i] === "*" && src[i + 1] === "/")) { if (src[i] === "\n") line += 1; i += 1; }
      i += 2; continue;
    }
    if (c === '"' || c === "'") {
      const startLine = line; let j = i + 1;
      while (j < n && src[j] !== c) { if (src[j] === "\\") j += 1; if (src[j] === "\n") line += 1; j += 1; }
      toks.push({ t: "str", v: src.slice(i, j + 1), line: startLine });
      i = j + 1; continue;
    }
    if (c === "`") { /* 模板串整段按一个字符串记号（已知限制，见文件头） */
      const startLine = line; let j = i + 1, depth = 0;
      while (j < n) {
        if (src[j] === "\\") { j += 2; continue; }
        if (src[j] === "$" && src[j + 1] === "{") { depth += 1; j += 2; continue; }
        if (src[j] === "{" && depth > 0) { depth += 1; j += 1; continue; }
        if (src[j] === "}" && depth > 0) { depth -= 1; j += 1; continue; }
        if (src[j] === "`" && depth === 0) break;
        if (src[j] === "\n") line += 1;
        j += 1;
      }
      toks.push({ t: "str", v: src.slice(i, j + 1), line: startLine });
      i = j + 1; continue;
    }
    if (c === "/" && isRegexPos()) {
      const startLine = line; let j = i + 1, inCls = false;
      while (j < n) {
        if (src[j] === "\\") { j += 2; continue; }
        if (src[j] === "[") inCls = true;
        else if (src[j] === "]") inCls = false;
        else if (src[j] === "/" && !inCls) break;
        if (src[j] === "\n") line += 1;
        j += 1;
      }
      j += 1;
      while (j < n && /[A-Za-z]/.test(src[j])) j += 1;
      toks.push({ t: "regex", v: src.slice(i, j), line: startLine });
      i = j; continue;
    }
    if (/[0-9]/.test(c)) {
      let j = i;
      while (j < n && /[0-9a-zA-Z._$]/.test(src[j])) j += 1;
      if (src[j - 1] === ".") j -= 1;
      toks.push({ t: "num", v: src.slice(i, j), line });
      i = j; continue;
    }
    if (/[A-Za-z_$]/.test(c)) {
      let j = i;
      while (j < n && /[A-Za-z0-9_$]/.test(src[j])) j += 1;
      toks.push({ t: "id", v: src.slice(i, j), line });
      i = j; continue;
    }
    const three = src.slice(i, i + 3), two = src.slice(i, i + 2);
    if (["===", "!==", "**=", "...", "&&=", "||=", "??="].includes(three)) {
      toks.push({ t: "punct", v: three, line }); i += 3; continue;
    }
    if (["=>", "==", "!=", "<=", ">=", "&&", "||", "++", "--", "+=", "-=", "*=",
      "/=", "%=", "?.", "??", "&=", "|=", "^=", "<<", ">>"].includes(two)) {
      toks.push({ t: "punct", v: two, line }); i += 2; continue;
    }
    toks.push({ t: "punct", v: c, line }); i += 1;
  }
  return toks;
}

function matchBack(toks, idx, closeCh, openCh) {
  let depth = 0;
  for (let k = idx; k >= 0; k -= 1) {
    const v = toks[k].v;
    if (v === closeCh) depth += 1;
    else if (v === openCh) { depth -= 1; if (depth === 0) return k; }
  }
  return -1;
}

function analyze(src) {
  const toks = lex(src);
  const lines = src.replace(/\r\n/g, "\n").split("\n");
  const totalLines = lines.length;
  const lineOf = (ln) => (lines[ln - 1] || "").trim();

  /* 1) const model = { … } 字面量的初始字段 */
  const initFields = new Map();
  let open = -1;
  for (let k = 0; k < toks.length - 3; k += 1) {
    if (toks[k].v === "const" && toks[k + 1].v === "model" && toks[k + 2].v === "="
        && toks[k + 3].v === "{") { open = k + 3; break; }
  }
  if (open >= 0) {
    /* 向前找配对的 }（matchBack 是给“从闭括号往回找”用的，这里从开括号起算） */
    let depth = 0, close = -1;
    for (let k = open; k < toks.length; k += 1) {
      const v = toks[k].v;
      if (v === "{") depth += 1;
      else if (v === "}") { depth -= 1; if (depth === 0) { close = k; break; } }
    }
    for (let k = open; k <= close; k += 1) {
      const v = toks[k].v;
      if (v === "{" || v === "[" || v === "(") { depth += 1; continue; }
      if (v === "}" || v === "]" || v === ")") { depth -= 1; continue; }
      if (depth === 1 && toks[k].t === "id" && toks[k + 1] && toks[k + 1].v === ":"
          && !initFields.has(toks[k].v)) {
        initFields.set(toks[k].v, toks[k].line);
      }
    }
  }

  /* 2) 单遍扫描：花括号栈 + 函数帧 + model 访问分类 */
  const braces = [];
  const curFn = () => {
    for (let k = braces.length - 1; k >= 0; k -= 1) if (braces[k].isFn) return braces[k];
    return null;
  };
  const fnLabel = (fr) => (fr ? fr.name : "<顶层>");
  const accesses = [];
  const objectAssign = [];

  for (let k = 0; k < toks.length; k += 1) {
    const tok = toks[k];
    if (tok.t === "punct") {
      if (tok.v === "{") {
        let isFn = false, name = `<anon@${tok.line}>`, fnLine = tok.line;
        const p = k > 0 ? toks[k - 1] : null;
        if (p && p.v === "=>") {
          isFn = true;
          let parenIdx = -1;
          if (k >= 2 && toks[k - 2].v === ")") parenIdx = matchBack(toks, k - 2, ")", "(");
          let hint = null;
          if (parenIdx > 0) {
            const before = toks[parenIdx - 1];
            if (before && before.t === "id" && !KEYWORDS.has(before.v)) hint = before.v;
            else if (before && before.v === "=") {
              for (let b = parenIdx - 2; b >= 0 && b >= parenIdx - 4; b -= 1) {
                if (toks[b].t === "id" && !KEYWORDS.has(toks[b].v)) { hint = toks[b].v; break; }
              }
            } else {
              for (let b = parenIdx - 1; b >= 0 && b >= parenIdx - 6; b -= 1) {
                if (toks[b].t === "id" && !KEYWORDS.has(toks[b].v)) { hint = `${toks[b].v}›回调`; break; }
              }
            }
          }
          name = hint ? `${hint}@${tok.line}` : `<anon@${tok.line}>`;
        } else if (p && p.v === ")") {
          const op = matchBack(toks, k - 1, ")", "(");
          const t = op > 0 ? toks[op - 1] : null;
          if (t && t.t === "id") {
            if (t.v === "function") {
              isFn = true; fnLine = t.line;
              const b = op >= 2 ? toks[op - 2] : null;
              name = (b && b.t === "id" && !KEYWORDS.has(b.v)) ? `${b.v}@${t.line}` : `<anon@${t.line}>`;
            } else if (!KEYWORDS.has(t.v)) { isFn = true; name = `${t.v}@${t.line}`; fnLine = t.line; }
          }
        }
        braces.push({ isFn, name, line: fnLine });
        continue;
      }
      if (tok.v === "}") { braces.pop(); continue; }
      continue;
    }
    if (tok.t === "id" && tok.v === "Object" && toks[k + 1] && toks[k + 1].v === "."
        && toks[k + 2] && toks[k + 2].v === "assign" && toks[k + 3] && toks[k + 3].v === "("
        && toks[k + 4] && toks[k + 4].v === "model") {
      objectAssign.push({ line: tok.line, fn: fnLabel(curFn()), target: "model" });
      continue;
    }
    if (tok.t === "id" && tok.v === "model") {
      const prev = k > 0 ? toks[k - 1] : null;
      const next = toks[k + 1];
      if (prev && (prev.v === "." || prev.v === "??." || prev.v === "?.")) continue;
      if (prev && (prev.v === "const" || prev.v === "let" || prev.v === "var")) continue;
      if (next && next.v === ":" && prev && (prev.v === "{" || prev.v === ",")) continue;
      const fn = fnLabel(curFn());
      if (next && next.v === ".") {
        const F = toks[k + 2];
        if (!F || F.t !== "id") { accesses.push({ kind: "computed", field: "?", line: tok.line, fn }); continue; }
        let j = k + 3, sub = null, isWrite = false, form = "assign";
        if (toks[j] && toks[j].v === "." && toks[j + 1] && toks[j + 1].t === "id") {
          sub = toks[j + 1].v; j += 2;
        }
        if (toks[j] && ASSIGN_OPS.includes(toks[j].v)) {
          isWrite = true;
          form = toks[j].v === "=" ? (sub ? "assign-sub" : "assign") : `compound${toks[j].v}`;
        } else if (toks[j] && toks[j].v === "(" && sub && MUTATORS.has(sub)) {
          isWrite = true; form = `mutate:${sub}`;
        }
        accesses.push({ kind: isWrite ? "write" : "read", field: F.v, sub, form, line: tok.line, fn });
        continue;
      }
      if (next && next.v === "[") { accesses.push({ kind: "computed", field: "?", line: tok.line, fn }); continue; }
      accesses.push({ kind: "bare", field: "", line: tok.line, fn });
    }
  }

  /* 3) 汇总成字段表 */
  const fields = new Map();
  const ensure = (name) => {
    if (!fields.has(name)) {
      fields.set(name, { name, declaredAt: initFields.get(name) || null, writes: [], reads: [] });
    }
    return fields.get(name);
  };
  for (const name of initFields.keys()) ensure(name);
  const bare = [];
  let computed = 0;
  for (const a of accesses) {
    if (a.kind === "bare") { bare.push({ line: a.line, fn: a.fn }); continue; }
    if (a.kind === "computed") { computed += 1; continue; }
    if (a.kind !== "write") continue;
    const e = ensure(a.field);
    e.writes.push({ line: a.line, fn: a.fn, form: a.form, sub: a.sub || "", code: lineOf(a.line) });
  }
  for (const a of accesses) {
    if (a.kind === "read") ensure(a.field).reads.push({ line: a.line, fn: a.fn, code: lineOf(a.line) });
  }
  const list = [...fields.values()].map((e) => ({
    name: e.name,
    declaredAt: e.declaredAt,
    dynamic: !initFields.has(e.name),
    writes: e.writes.sort((x, y) => x.line - y.line || x.sub.localeCompare(y.sub)),
    reads: e.reads.sort((x, y) => x.line - y.line),
  }));
  const writePoints = list.reduce((s, f) => s + f.writes.length, 0);
  const readPoints = list.reduce((s, f) => s + f.reads.length, 0);
  return {
    baseline: `${COMMIT}:${FILE}`,
    totalLines,
    counts: {
      fields: list.length, writePoints, readPoints,
      bareModelRefs: bare.length, computedAccesses: computed,
      objectAssignWrites: objectAssign.length,
    },
    objectAssign,
    bareModelRefs: bare,
    fields: list,
  };
}

const src = loadBaseline();
process.stdout.write(JSON.stringify(analyze(src), null, 1));
