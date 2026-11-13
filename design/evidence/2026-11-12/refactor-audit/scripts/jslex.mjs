// JS 词法扫描：给 jsfuncs.mjs 和 globals.mjs 共用。只用 node 自带能力，不依赖任何包。
//
// 做什么：把源码切成记号（标识符、标点、字符串、模板、正则、数字），跳过注释。
// 不做什么：不建语法树，不做作用域分析。口径和误差见上一级目录的 README.md。
//
// 记号形状：{ type, value, line, pos }
//   type: "id"（标识符或关键字）| "punct" | "str" | "tpl"（模板字符串的文本段）| "regex" | "num"
//   模板字符串里的 ${ … } 会展开成普通记号：先出一个 punct "${"，里面照常扫描，再出 punct "}"。

const ID_START = /[A-Za-z_$ -￿]/;
const ID_PART = /[A-Za-z0-9_$ -￿]/;

// 这些关键字后面出现的 "/" 是正则的开头，不是除号。
const REGEX_AFTER_KEYWORD = new Set([
  "return", "typeof", "instanceof", "in", "of", "new", "delete", "void", "throw",
  "case", "do", "else", "yield", "await",
]);

// 三个字符、两个字符的标点，长的先匹配。
const PUNCT3 = ["===", "!==", "**=", "<<=", ">>=", ">>>", "...", "&&=", "||=", "??="];
const PUNCT2 = ["=>", "==", "!=", "<=", ">=", "&&", "||", "??", "?.", "++", "--", "+=", "-=", "*=",
  "/=", "%=", "&=", "|=", "^=", "<<", ">>", "**"];

export function tokenize(src) {
  const tokens = [];
  let i = 0;
  let line = 1;
  const n = src.length;
  // 模板字符串可以嵌套：栈里记每个 ${ 开始时的花括号深度，遇到配对的 } 就回到模板文本。
  const tplStack = [];
  let braceDepth = 0;

  // 前一个记号是不是「值」：是的话后面的 "/" 是除号，否则是正则。
  function prevIsValue() {
    const t = tokens[tokens.length - 1];
    if (!t) return false;
    if (t.type === "num" || t.type === "str" || t.type === "regex" || t.type === "tpl") return true;
    if (t.type === "id") return !REGEX_AFTER_KEYWORD.has(t.value);
    if (t.type === "punct") return t.value === ")" || t.value === "]" || t.value === "}"
      || t.value === "++" || t.value === "--";
    return false;
  }

  // 从模板字符串的文本位置开始扫，直到遇到结尾的反引号或 ${ 。
  function scanTemplateText() {
    const startLine = line;
    const start = i;
    while (i < n) {
      const c = src[i];
      if (c === "\\") { i += 2; continue; }
      if (c === "`") {
        tokens.push({ type: "tpl", value: src.slice(start, i), line: startLine, pos: start });
        i += 1;
        return;
      }
      if (c === "$" && src[i + 1] === "{") {
        tokens.push({ type: "tpl", value: src.slice(start, i), line: startLine, pos: start });
        tokens.push({ type: "punct", value: "${", line, pos: i });
        i += 2;
        tplStack.push(braceDepth);
        braceDepth += 1;
        return;
      }
      if (c === "\n") line += 1;
      i += 1;
    }
  }

  while (i < n) {
    const c = src[i];
    if (c === "\n") { line += 1; i += 1; continue; }
    if (c === " " || c === "\t" || c === "\r" || c === "﻿") { i += 1; continue; }

    // 注释：整段跳过，只数换行。
    if (c === "/" && src[i + 1] === "/") {
      while (i < n && src[i] !== "\n") i += 1;
      continue;
    }
    if (c === "/" && src[i + 1] === "*") {
      const end = src.indexOf("*/", i + 2);
      const stop = end === -1 ? n : end + 2;
      for (let k = i; k < stop; k += 1) if (src[k] === "\n") line += 1;
      i = stop;
      continue;
    }

    // 字符串
    if (c === '"' || c === "'") {
      const start = i;
      const startLine = line;
      i += 1;
      while (i < n && src[i] !== c) {
        if (src[i] === "\\") i += 1;
        if (src[i] === "\n") line += 1;
        i += 1;
      }
      i += 1;
      tokens.push({ type: "str", value: src.slice(start + 1, i - 1), line: startLine, pos: start });
      continue;
    }

    // 模板字符串
    if (c === "`") {
      i += 1;
      scanTemplateText();
      continue;
    }

    // 正则字面量
    if (c === "/" && !prevIsValue()) {
      const start = i;
      i += 1;
      let inClass = false;
      while (i < n) {
        const d = src[i];
        if (d === "\\") { i += 2; continue; }
        if (d === "\n") break;            // 正则不跨行；走到这里说明判错了，按除号处理
        if (d === "[") inClass = true;
        else if (d === "]") inClass = false;
        else if (d === "/" && !inClass) break;
        i += 1;
      }
      if (src[i] === "/") {
        i += 1;
        while (i < n && /[a-z]/.test(src[i])) i += 1;
        tokens.push({ type: "regex", value: src.slice(start, i), line, pos: start });
        continue;
      }
      // 判错：退回去当除号
      i = start + 1;
      tokens.push({ type: "punct", value: "/", line, pos: start });
      continue;
    }

    // 数字
    if (/[0-9]/.test(c) || (c === "." && /[0-9]/.test(src[i + 1] || ""))) {
      const start = i;
      i += 1;
      while (i < n && /[0-9A-Za-z_.]/.test(src[i])) {
        // 1e+3、1e-3 里的符号
        if ((src[i] === "e" || src[i] === "E") && (src[i + 1] === "+" || src[i + 1] === "-")
            && !/^0[xXbBoO]/.test(src.slice(start, i))) i += 1;
        i += 1;
      }
      tokens.push({ type: "num", value: src.slice(start, i), line, pos: start });
      continue;
    }

    // 标识符和关键字
    if (ID_START.test(c)) {
      const start = i;
      i += 1;
      while (i < n && ID_PART.test(src[i])) i += 1;
      tokens.push({ type: "id", value: src.slice(start, i), line, pos: start });
      continue;
    }

    // 标点
    const three = src.slice(i, i + 3);
    const two = src.slice(i, i + 2);
    if (src.slice(i, i + 4) === ">>>=") {
      tokens.push({ type: "punct", value: ">>>=", line, pos: i });
      i += 4;
      continue;
    }
    if (PUNCT3.includes(three)) {
      tokens.push({ type: "punct", value: three, line, pos: i });
      i += 3;
      continue;
    }
    if (PUNCT2.includes(two)) {
      tokens.push({ type: "punct", value: two, line, pos: i });
      i += 2;
      continue;
    }
    if (c === "{") braceDepth += 1;
    if (c === "}") {
      braceDepth -= 1;
      if (tplStack.length && tplStack[tplStack.length - 1] === braceDepth) {
        // 这是 ${ … } 的收尾：出一个 "}"，然后回到模板文本继续扫。
        tplStack.pop();
        tokens.push({ type: "punct", value: "}", line, pos: i, tplEnd: true });
        i += 1;
        scanTemplateText();
        continue;
      }
    }
    tokens.push({ type: "punct", value: c, line, pos: i });
    i += 1;
  }
  return tokens;
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
// 模板里的 ${ } 不算深度变化的来源之外的东西：它也加一层，所以 ${} 里面的名字不会被当成顶层声明。
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
