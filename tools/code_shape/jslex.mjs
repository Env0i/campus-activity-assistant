// JS 词法扫描：把源码切成记号，给 jsscan.mjs（找函数）与前端依赖报表共用。
// 只用 node 自带能力，不依赖任何包。
//
// 来源：design/evidence/2026-11-12/refactor-audit/scripts/jslex.mjs。量法不得改：
// 只把 tokenize 拆成若干小函数，记号形状、跳过注释与字符串的规则、正则与模板的判断都没动。
// 等价性由 lexer_equiv.py 对范围内全部 .js/.mjs 的函数表逐字比对证明。
//
// 记号形状：{ type, value, line, pos }
//   type: "id"（标识符或关键字）| "punct" | "str" | "tpl"（模板字符串的文本段）| "regex" | "num"
//   模板字符串里的 ${ … } 会展开成普通记号：先出一个 punct "${"，里面照常扫描，再出 punct "}"。

// 字符范围是 U+00A0–U+FFFF：原脚本这里写的是不间断空格，改用显式转义，范围不变。
const ID_START = /[A-Za-z_$\u00A0-\uFFFF]/;
const ID_PART = /[A-Za-z0-9_$\u00A0-\uFFFF]/;

// 这些关键字后面出现的 "/" 是正则的开头，不是除号。
const REGEX_AFTER_KEYWORD = new Set([
  "return", "typeof", "instanceof", "in", "of", "new", "delete", "void", "throw",
  "case", "do", "else", "yield", "await",
]);

// 三个字符、两个字符的标点，长的先匹配。
const PUNCT3 = ["===", "!==", "**=", "<<=", ">>=", ">>>", "...", "&&=", "||=", "??="];
const PUNCT2 = ["=>", "==", "!=", "<=", ">=", "&&", "||", "??", "?.", "++", "--", "+=", "-=", "*=",
  "/=", "%=", "&=", "|=", "^=", "<<", ">>", "**"];

// 一次 tokenize 的全部游标。拆函数后共享它，避免各自持有半套状态。
function newScanState(src) {
  return { src, i: 0, line: 1, n: src.length, tokens: [], tplStack: [], braceDepth: 0 };
}

function pushToken(st, type, value, line, pos, extra) {
  const tok = { type, value, line, pos };
  if (extra) Object.assign(tok, extra);
  st.tokens.push(tok);
}

// 前一个记号是不是「值」：是的话后面的 "/" 是除号，否则是正则。
function prevIsValue(st) {
  const t = st.tokens[st.tokens.length - 1];
  if (!t) return false;
  if (t.type === "num" || t.type === "str" || t.type === "regex" || t.type === "tpl") return true;
  if (t.type === "id") return !REGEX_AFTER_KEYWORD.has(t.value);
  if (t.type === "punct") return t.value === ")" || t.value === "]" || t.value === "}"
    || t.value === "++" || t.value === "--";
  return false;
}

// 从模板字符串的文本位置开始扫，直到遇到结尾的反引号或 ${ 。
function scanTemplateText(st) {
  const { src } = st;
  const startLine = st.line;
  const start = st.i;
  while (st.i < st.n) {
    const c = src[st.i];
    if (c === "\\") { st.i += 2; continue; }
    if (c === "`") {
      pushToken(st, "tpl", src.slice(start, st.i), startLine, start);
      st.i += 1;
      return;
    }
    if (c === "$" && src[st.i + 1] === "{") {
      pushToken(st, "tpl", src.slice(start, st.i), startLine, start);
      pushToken(st, "punct", "${", st.line, st.i);
      st.i += 2;
      st.tplStack.push(st.braceDepth);
      st.braceDepth += 1;
      return;
    }
    if (c === "\n") st.line += 1;
    st.i += 1;
  }
}

// 注释：整段跳过，只数换行。不是注释返回 false。
function readComment(st) {
  const { src } = st;
  if (src[st.i] !== "/") return false;
  if (src[st.i + 1] === "/") {
    while (st.i < st.n && src[st.i] !== "\n") st.i += 1;
    return true;
  }
  if (src[st.i + 1] !== "*") return false;
  const end = src.indexOf("*/", st.i + 2);
  const stop = end === -1 ? st.n : end + 2;
  for (let k = st.i; k < stop; k += 1) if (src[k] === "\n") st.line += 1;
  st.i = stop;
  return true;
}

// 单引号或双引号字符串。
function readString(st) {
  const { src } = st;
  const c = src[st.i];
  if (c !== '"' && c !== "'") return false;
  const start = st.i;
  const startLine = st.line;
  st.i += 1;
  while (st.i < st.n && src[st.i] !== c) {
    if (src[st.i] === "\\") st.i += 1;
    if (src[st.i] === "\n") st.line += 1;
    st.i += 1;
  }
  st.i += 1;
  pushToken(st, "str", src.slice(start + 1, st.i - 1), startLine, start);
  return true;
}

function readTemplate(st) {
  if (st.src[st.i] !== "`") return false;
  st.i += 1;
  scanTemplateText(st);
  return true;
}

// 正则字面量。判错（不闭合）时退回去当除号。
function readRegex(st) {
  const { src } = st;
  if (src[st.i] !== "/" || prevIsValue(st)) return false;
  const start = st.i;
  st.i += 1;
  let inClass = false;
  while (st.i < st.n) {
    const d = src[st.i];
    if (d === "\\") { st.i += 2; continue; }
    if (d === "\n") break;            // 正则不跨行；走到这里说明判错了，按除号处理
    if (d === "[") inClass = true;
    else if (d === "]") inClass = false;
    else if (d === "/" && !inClass) break;
    st.i += 1;
  }
  if (src[st.i] === "/") {
    st.i += 1;
    while (st.i < st.n && /[a-z]/.test(src[st.i])) st.i += 1;
    pushToken(st, "regex", src.slice(start, st.i), st.line, start);
    return true;
  }
  // 判错：退回去当除号
  st.i = start + 1;
  pushToken(st, "punct", "/", st.line, start);
  return true;
}

function readNumber(st) {
  const { src } = st;
  const c = src[st.i];
  if (!/[0-9]/.test(c) && !(c === "." && /[0-9]/.test(src[st.i + 1] || ""))) return false;
  const start = st.i;
  st.i += 1;
  while (st.i < st.n && /[0-9A-Za-z_.]/.test(src[st.i])) {
    // 1e+3、1e-3 里的符号
    if ((src[st.i] === "e" || src[st.i] === "E") && (src[st.i + 1] === "+" || src[st.i + 1] === "-")
        && !/^0[xXbBoO]/.test(src.slice(start, st.i))) st.i += 1;
    st.i += 1;
  }
  pushToken(st, "num", src.slice(start, st.i), st.line, start);
  return true;
}

function readIdentifier(st) {
  const { src } = st;
  if (!ID_START.test(src[st.i])) return false;
  const start = st.i;
  st.i += 1;
  while (st.i < st.n && ID_PART.test(src[st.i])) st.i += 1;
  pushToken(st, "id", src.slice(start, st.i), st.line, start);
  return true;
}

// 标点；花括号顺带记深度，模板里 ${ … } 的收尾要回到模板文本。
function readPunct(st) {
  const { src } = st;
  const i = st.i;
  if (src.slice(i, i + 4) === ">>>=") {
    pushToken(st, "punct", ">>>=", st.line, i);
    st.i = i + 4;
    return;
  }
  const three = src.slice(i, i + 3);
  if (PUNCT3.includes(three)) {
    pushToken(st, "punct", three, st.line, i);
    st.i = i + 3;
    return;
  }
  const two = src.slice(i, i + 2);
  if (PUNCT2.includes(two)) {
    pushToken(st, "punct", two, st.line, i);
    st.i = i + 2;
    return;
  }
  const c = src[i];
  if (c === "{") st.braceDepth += 1;
  if (c === "}") {
    st.braceDepth -= 1;
    if (st.tplStack.length && st.tplStack[st.tplStack.length - 1] === st.braceDepth) {
      // 这是 ${ … } 的收尾：出一个 "}"，然后回到模板文本继续扫。
      st.tplStack.pop();
      pushToken(st, "punct", "}", st.line, i, { tplEnd: true });
      st.i = i + 1;
      scanTemplateText(st);
      return;
    }
  }
  pushToken(st, "punct", c, st.line, i);
  st.i = i + 1;
}

export function tokenize(src) {
  const st = newScanState(src);
  while (st.i < st.n) {
    const c = st.src[st.i];
    if (c === "\n") { st.line += 1; st.i += 1; continue; }
    if (c === " " || c === "\t" || c === "\r" || c === "﻿") { st.i += 1; continue; }
    if (readComment(st) || readString(st) || readTemplate(st) || readRegex(st)
        || readNumber(st) || readIdentifier(st)) continue;
    readPunct(st);
  }
  return st.tokens;
}

// 给每个括号记号标上配对的下标（open ↔ close），并返回是否配平。
// "${" 当作 "{" 的一种开括号，和 "}" 配对。
export function matchBrackets(tokens) {
  const pairs = { ")": "(", "]": "[", "}": "{" };
  const stack = [];
  let balanced = true;
  for (let k = 0; k < tokens.length; k += 1) {
    const t = tokens[k];
    if (t.type !== "punct") continue;
    if (t.value === "(" || t.value === "[" || t.value === "{" || t.value === "${") {
      stack.push(k);
    } else if (t.value === ")" || t.value === "]" || t.value === "}") {
      const openIdx = stack.pop();
      if (openIdx === undefined) { balanced = false; continue; }
      const open = tokens[openIdx].value === "${" ? "{" : tokens[openIdx].value;
      if (open !== pairs[t.value]) balanced = false;
      tokens[openIdx].match = k;
      t.match = openIdx;
    }
  }
  if (stack.length) balanced = false;
  return balanced;
}

// 每个记号所在的花括号深度（只数 { }，不数圆括号和方括号）。
// 模板里的 ${ } 也加一层，所以 ${} 里面的名字不会被当成顶层声明。
export function braceDepths(tokens) {
  const depths = new Array(tokens.length);
  let d = 0;
  for (let k = 0; k < tokens.length; k += 1) {
    const t = tokens[k];
    if (t.type === "punct" && t.value === "}") d -= 1;
    depths[k] = d;
    if (t.type === "punct" && (t.value === "{" || t.value === "${")) d += 1;
  }
  return depths;
}

export const KEYWORDS = new Set([
  "break", "case", "catch", "class", "const", "continue", "debugger", "default", "delete", "do",
  "else", "export", "extends", "finally", "for", "function", "if", "import", "in", "instanceof",
  "let", "new", "return", "super", "switch", "this", "throw", "try", "typeof", "var", "void",
  "while", "with", "yield", "async", "await", "of", "static", "get", "set", "null", "true",
  "false", "undefined",
]);
