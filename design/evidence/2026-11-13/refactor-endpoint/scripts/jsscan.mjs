// 在 jslex.mjs 的记号流上找函数。给 jsfuncs.mjs（量行数）和 globals.mjs（找谁在写状态）共用。
//
// 计入的函数（口径见 README「C1 ③」）：
//   1. function 声明与表达式（含 async、生成器）
//   2. 带花括号体的箭头函数；表达式体的箭头函数不计
//   3. 对象字面量与类里的方法简写、getter、setter：形如  名字 ( … ) {
// 行数 = 函数头所在行 到 配对的 } 所在行，两头都算。

import { tokenize, matchBrackets } from "./jslex.mjs";

// 这些关键字后面跟 ( … ) { 是控制语句，不是方法定义。
const CONTROL = new Set(["if", "for", "while", "switch", "catch", "with", "function", "return",
  "typeof", "await", "new", "do", "else", "try", "finally"]);

function isPunct(t, v) { return !!t && t.type === "punct" && t.value === v; }
function isId(t, v) { return !!t && t.type === "id" && (v === undefined || t.value === v); }

// 给匿名函数起名：看函数头前面是「名字 =」「名字 :」「a.b.名字 =」还是别的。
// headIdx 是函数头的第一个记号（function / async / 参数的左括号 / 单个参数名）。
function nameFromContext(tokens, headIdx) {
  const prev = tokens[headIdx - 1];
  const prev2 = tokens[headIdx - 2];
  if (isPunct(prev, "=") && prev2) {
    if (prev2.type === "id") {
      // a.b.c = function … → 取整条成员链
      let k = headIdx - 2;
      const parts = [tokens[k].value];
      while (isPunct(tokens[k - 1], ".") && isId(tokens[k - 2])) {
        parts.unshift(tokens[k - 2].value);
        k -= 2;
      }
      return parts.join(".");
    }
    if (isPunct(prev2, "]")) return "<computed>";
  }
  if (isPunct(prev, ":") && prev2 && (prev2.type === "id" || prev2.type === "str")) {
    return prev2.value;
  }
  return "";
}

export function findFunctions(src) {
  const tokens = tokenize(src);
  const balanced = matchBrackets(tokens);
  const funcs = [];

  for (let k = 0; k < tokens.length; k += 1) {
    const t = tokens[k];

    // 1. function 关键字
    if (isId(t, "function") && !isPunct(tokens[k - 1], ".")) {
      let j = k + 1;
      if (isPunct(tokens[j], "*")) j += 1;
      let name = "";
      if (isId(tokens[j]) && !isPunct(tokens[j], "(")) {
        if (tokens[j].type === "id" && isPunct(tokens[j + 1], "(")) { name = tokens[j].value; j += 1; }
      }
      if (!isPunct(tokens[j], "(") || tokens[j].match === undefined) continue;
      const bodyOpen = tokens[j].match + 1;
      if (!isPunct(tokens[bodyOpen], "{") || tokens[bodyOpen].match === undefined) continue;
      let head = k;
      if (isId(tokens[k - 1], "async")) head = k - 1;
      const kind = name ? "function" : "function-expr";
      if (!name) name = nameFromContext(tokens, head);
      funcs.push({ name, kind, startTok: head, bodyOpen, bodyClose: tokens[bodyOpen].match,
        paramOpen: j, paramClose: tokens[j].match });
      continue;
    }

    // 2. 箭头函数，只收带花括号体的
    if (isPunct(t, "=>") && isPunct(tokens[k + 1], "{") && tokens[k + 1].match !== undefined) {
      let head = k - 1;
      let paramOpen = -1;
      let paramClose = -1;
      if (isPunct(tokens[k - 1], ")") && tokens[k - 1].match !== undefined) {
        head = tokens[k - 1].match;
        paramOpen = head;
        paramClose = k - 1;
      } else {
        paramOpen = k - 1;      // 单个参数名，没有括号
        paramClose = k - 1;
      }
      if (isId(tokens[head - 1], "async")) head -= 1;
      const name = nameFromContext(tokens, head);
      funcs.push({ name, kind: "arrow", startTok: head, bodyOpen: k + 1,
        bodyClose: tokens[k + 1].match, paramOpen, paramClose });
      continue;
    }

    // 3. 方法简写： 名字 ( … ) {   名字不是控制关键字，前面也不是 function
    if ((t.type === "id" || t.type === "str") && isPunct(tokens[k + 1], "(")
        && tokens[k + 1].match !== undefined) {
      if (t.type === "id" && CONTROL.has(t.value)) continue;
      const prev = tokens[k - 1];
      if (isId(prev, "function") || isPunct(prev, "*") && isId(tokens[k - 2], "function")) continue;
      if (isPunct(prev, ".") || isPunct(prev, "?.")) continue;      // a.b(…) { 不是合法定义
      const bodyOpen = tokens[k + 1].match + 1;
      if (!isPunct(tokens[bodyOpen], "{") || tokens[bodyOpen].match === undefined) continue;
      let head = k;
      while (isId(tokens[head - 1]) && ["async", "get", "set", "static"].includes(tokens[head - 1].value)
             && !isPunct(tokens[head - 2], ".")) head -= 1;
      if (isPunct(tokens[head - 1], "*")) head -= 1;
      funcs.push({ name: t.value, kind: "method", startTok: head, bodyOpen,
        bodyClose: tokens[bodyOpen].match, paramOpen: k + 1, paramClose: tokens[k + 1].match });
    }
  }

  // 补行号、嵌套层数和外层函数名
  funcs.sort((a, b) => a.startTok - b.startTok);
  const stack = [];
  for (const f of funcs) {
    f.start = tokens[f.startTok].line;
    f.end = tokens[f.bodyClose].line;
    f.lines = f.end - f.start + 1;
    while (stack.length && stack[stack.length - 1].bodyClose < f.startTok) stack.pop();
    f.depth = stack.length;
    f.parent = stack.length ? stack[stack.length - 1] : null;
    if (!f.name) f.name = `<anonymous@${f.start}>`;
    f.qualname = f.parent ? `${f.parent.qualname} > ${f.name}` : f.name;
    stack.push(f);
  }
  return { tokens, funcs, balanced };
}

// 某个记号下标落在哪个函数里（最内层）；不在任何函数里返回 null。
export function enclosingFunction(funcs, tokIdx) {
  let best = null;
  for (const f of funcs) {
    if (f.startTok <= tokIdx && tokIdx <= f.bodyClose) {
      if (!best || f.startTok >= best.startTok) best = f;
    }
  }
  return best;
}
