#!/usr/bin/env node
/* T5③：清点基线 7e2d31c 桌面前端（local/ui/ 除 local/ui/m/）全部 esc( 调用点。
 *
 * 从仓库根复跑（只读，不写文件、不联网）：
 *   node design/evidence/2026-11-12/refactor-audit/redo/zcode/plan/scripts/esc_sites.mjs
 *
 * 方法：node:child_process 里 git ls-tree / git show 取基线内容；逐字符扫描
 * （处理行/块注释、单双引号串、模板字面量含嵌套插值、正则字面量启发式），
 * 在代码态识别标识符 esc 紧跟 (。所在函数 = 最近一层 function 声明名，
 * 箭头函数体不单独成帧（归属外层命名函数），顶层记「(顶层)」。
 *
 * 输出三类：def=esc 定义处；call=esc( 调用点；ref=esc 标识符的其余出现
 * （含 const esc = ... 这类同名局部变量，桌面端确有遮蔽，见 prereq.md）。
 *
 * 落点粗分类（脚本自动，人工复核在 prereq.md）：
 *   文本节点 / 双引号属性 / 单引号属性 / 事件处理器字符串 / URL / 其他。
 * 依据 esc( 之前最近的字符串字面量（JS 转义还原后）的收尾形态：
 *   尾部停在未闭合标签内的 属性名+等号+引号 → 双/单引号属性；
 *   属性名 on* → 事件处理器字符串；href/src 等 → URL；
 *   尾部停在 > 之后 → 文本节点；其余 → 其他（人工复核定）。
 */
import { spawnSync } from "node:child_process";

const COMMIT = "7e2d31c";
const SCAN_EXTS = [".js", ".html"];

function git(args) {
  const r = spawnSync("git", args, { encoding: "utf8", maxBuffer: 64 * 1024 * 1024 });
  if (r.status !== 0) throw new Error("git " + args.join(" ") + " 失败: " + r.stderr);
  return r.stdout;
}

function listUiFiles() {
  return git(["ls-tree", "-r", "--name-only", COMMIT, "--", "local/ui"])
    .split(/\r?\n/).filter(Boolean)
    .filter((p) => p.startsWith("local/ui/") && !p.startsWith("local/ui/m/"))
    .filter((p) => SCAN_EXTS.some((e) => p.endsWith(e)))
    .sort();
}

/* 还原 JS 字符串字面量的常见转义，便于看出 HTML 形态 */
function unescapeJs(raw) {
  return raw.replace(/\\(.)/g, (_, c) => (c === "n" ? "\n" : c === "t" ? "\t" : c));
}

/* 由前导 HTML 片段收尾粗分类
 * 规则：尾部停在未闭合标签内（或前导片段本身就是属性段、无 < 可判）→ 按属性分类；
 * 上一个 > 之后的剩余文字 → 文本节点；其余 → 其他（人工复核定）。 */
function classifyTail(html) {
  const lt = html.lastIndexOf("<");
  const gt = html.lastIndexOf(">");
  const attrRe = /([a-zA-Z_:][-a-zA-Z0-9_:]*)\s*=\s*(["'])[^"']*$/;
  const URL_ATTRS = ["href", "src", "action", "formaction", "xlink:href", "data-url", "data-href"];
  const attrCat = (seg) => {
    const m = seg.match(attrRe);
    if (!m) return null;
    const name = m[1].toLowerCase();
    if (/^on/.test(name)) return "事件处理器字符串";
    if (URL_ATTRS.includes(name)) return "URL";
    return m[2].charCodeAt(0) === 34 ? "双引号属性" : "单引号属性";
  };
  if (lt > gt || lt === -1) {
    /* 在未闭合标签内，或片段无 <（标签在更早的字面量里打开）*/
    const seg = lt === -1 ? html : html.slice(lt);
    const cat = attrCat(seg);
    if (cat) return cat;
    if (lt === -1 && !/[<>]/.test(html)) return "其他";
    if (lt === -1 && gt >= 0) return "文本节点";
    if (/[\s"'=][a-zA-Z_:][-a-zA-Z0-9_:]*$/.test(seg)) return "双引号属性"; /* 属性名后直接取值 */
    return "其他";
  }
  /* lt <= gt 且 lt >= 0：标签已闭合，> 之后是文本 */
  return "文本节点";
}

const BS = String.fromCharCode(92); /* 反斜杠字符，字符串扫描用 */

/* 单遍扫描：返回 [{kind:"def"|"call"|"ref", line, fn, cat, ...}] */
function scanText(rel, text) {
  const out = [];
  const n = text.length;
  const stack = [{ type: "code", brace: 0, frames: [], inTpl: false, htmlAcc: "" }];
  let line = 1;
  let pendingFn = null;
  let prevSig = "";
  let lastWord = "";
  let word = "";
  let lastLit = null; /* 最近一个字符串字面量 {end, raw} */

  const isWordStart = (c) => /[A-Za-z_$]/.test(c);
  const isWord = (c) => /[A-Za-z_$0-9]/.test(c);
  const flushWord = () => { if (word) { lastWord = word; word = ""; } };
  const regexAllowed = () =>
    prevSig === "" || "(,=:[!&|?{};+*%<>~^-".includes(prevSig) ||
    ["return", "typeof", "case", "in", "of", "new", "delete", "void", "instanceof", "do", "else"].includes(lastWord);

  let i = 0;
  while (i < n) {
    const c = text[i];
    if (c === "\n") line++;
    const top = stack[stack.length - 1];

    if (top.type === "tpl") {
      if (c === BS) { i += 2; continue; }
      if (c === "`") { stack.pop(); prevSig = "`"; lastWord = ""; word = ""; i++; continue; }
      if (c === "$" && text[i + 1] === "{") {
        stack.push({ type: "code", brace: 0, frames: [], inTpl: true, htmlAcc: top.htmlAcc });
        i += 2; prevSig = ""; lastWord = ""; word = ""; continue;
      }
      top.htmlAcc += c;
      i++; continue;
    }

    /* ---- code 态 ---- */
    if (c === "'" || c === '"') {
      flushWord();
      const q = c;
      let j = i + 1;
      let raw = "";
      while (j < n && text[j] !== q) {
        if (text[j] === BS) { raw += text[j] + (text[j + 1] || ""); if (text[j + 1] === "\n") line++; j += 2; continue; }
        if (text[j] === "\n") line++;
        raw += text[j]; j++;
      }
      lastLit = { end: j + 1, raw: unescapeJs(raw) };
      prevSig = q; lastWord = ""; word = "";
      i = j + 1; continue;
    }
    if (c === "/" && text[i + 1] === "/") {
      let j = i;
      while (j < n && text[j] !== "\n") j++;
      i = j; continue;
    }
    if (c === "/" && text[i + 1] === "*") {
      let j = i + 2;
      while (j < n && !(text[j] === "*" && text[j + 1] === "/")) { if (text[j] === "\n") line++; j++; }
      i = j + 2; continue;
    }
    if (c === "/" && regexAllowed()) {
      flushWord();
      let j = i + 1;
      let inCls = false;
      while (j < n) {
        if (text[j] === BS) { j += 2; continue; }
        if (text[j] === "[") inCls = true;
        else if (text[j] === "]") inCls = false;
        else if (text[j] === "/" && !inCls) break;
        else if (text[j] === "\n") break;
        j++;
      }
      while (j < n && /[a-z]/i.test(text[j])) j++;
      for (let q2 = i; q2 < j; q2++) if (text[q2] === "\n") line++;
      prevSig = "/"; lastWord = ""; word = "";
      i = j; continue;
    }
    if (c === "`") {
      flushWord();
      stack.push({ type: "tpl", htmlAcc: "" });
      i++; prevSig = "`"; lastWord = ""; word = ""; continue;
    }
    if (isWordStart(c)) {
      let j = i;
      while (j < n && isWord(text[j])) j++;
      const w = text.slice(i, j);
      flushWord();
      word = w;
      if (w === "function") {
        const after = text.slice(j, j + 200);
        const anon = /^\s*\(/.test(after);
        const named = after.match(/^\s*([A-Za-z_$][\w$]*)/);
        pendingFn = { name: anon ? "<anon>" : (named ? named[1] : "<anon>"), stage: "params", paren: 0 };
      }
      const before = i > 0 ? text[i - 1] : "";
      if (w === "esc" && !/[\w$.]/.test(before)) {
        let k = j;
        while (k < n && (text[k] === " " || text[k] === "\t")) k++;
        if (lastWord === "function") {
          /* 定义处：function esc(...) */
          out.push({ kind: "def", line, fn: "(定义)", cat: "-" });
        } else if (text[k] === "(") {
          /* 落点判定：调用点之前的字面量是否为直接拼接操作数 */
          let cat = null;
          let ctxText = "";
          if (top.inTpl) {
            cat = classifyTail(top.htmlAcc);
            ctxText = top.htmlAcc.slice(-120);
          } else if (lastLit && lastLit.end <= i) {
            const gap = text.slice(lastLit.end, i);
            if (/^[)\s+]*$/.test(gap)) {
              ctxText = lastLit.raw.slice(-120);
              cat = classifyTail(ctxText);
            } else {
              cat = "其他";
              ctxText = text.slice(text.lastIndexOf("\n", i) + 1, i).trim().slice(-100);
            }
          } else {
            cat = "其他";
            ctxText = "(前面没有字符串字面量)";
          }
          /* esc 结果是否被再加工（.replace 等）再落位 */
          let k2 = k + 1;
          let depth = 1;
          while (k2 < n && depth > 0) {
            if (text[k2] === "(") depth++;
            else if (text[k2] === ")") depth--;
            else if (text[k2] === "\n") line++;
            k2++;
          }
          const rest = text.slice(k2, k2 + 60).trim();
          const transformed = /^\.\s*(replace|trim|slice|split|concat|toLowerCase|toUpperCase|padStart|padEnd)/.test(rest);
          out.push({
            kind: "call", line, fn: top.frames.length ? top.frames[top.frames.length - 1].name : "(顶层)",
            cat, transformed, ctx: ctxText, rest: rest.split("\n")[0].slice(0, 60),
          });
        } else {
          /* 非调用引用：const esc = ... 遮蔽定义、.map(esc) 传参、if (esc) 判断等 */
          out.push({ kind: "ref", line, fn: top.frames.length ? top.frames[top.frames.length - 1].name : "(顶层)", cat: "-" });
        }
      }
      i = j; continue;
    }
    flushWord();
    if (c === "(") {
      if (pendingFn && pendingFn.stage === "params") { pendingFn.paren = 1; pendingFn.stage = "inParams"; }
      prevSig = "("; i++; continue;
    }
    if (c === ")") {
      if (pendingFn && pendingFn.stage === "inParams" && --pendingFn.paren <= 0) pendingFn.stage = "awaitBody";
      prevSig = ")"; i++; continue;
    }
    if (c === "{") {
      if (pendingFn && pendingFn.stage === "awaitBody") {
        top.frames.push({ name: pendingFn.name, open: top.brace + 1 });
        pendingFn = null;
      }
      top.brace++;
      prevSig = "{"; i++; continue;
    }
    if (c === "}") {
      if (stack.length > 1 && top.inTpl && top.brace === 0) { stack.pop(); prevSig = "}"; i++; continue; }
      top.brace = Math.max(0, top.brace - 1);
      while (top.frames.length && top.frames[top.frames.length - 1].open > top.brace) top.frames.pop();
      prevSig = "}"; i++; continue;
    }
    if (c === "=" && text[i + 1] === ">") { prevSig = "="; lastWord = ""; word = ""; i += 2; continue; }
    if (c === ";") { if (pendingFn && pendingFn.stage === "awaitBody") pendingFn = null; prevSig = c; i++; continue; }
    prevSig = c;
    i++;
  }
  return out;
}

function main() {
  const files = listUiFiles();
  const defs = [];
  const calls = [];
  const refs = [];
  const byFile = {};
  const byCat = {};
  const fnOf = {};
  for (const rel of files) {
    const text = git(["show", COMMIT + ":" + rel]);
    const sites = scanText(rel, text);
    for (const s of sites) {
      s.rel = rel;
      if (s.kind === "call") {
        calls.push(s);
        byFile[rel] = (byFile[rel] || 0) + 1;
        byCat[s.cat] = (byCat[s.cat] || 0) + 1;
        const key = rel + "#" + s.fn;
        fnOf[key] = (fnOf[key] || 0) + 1;
      } else if (s.kind === "def") {
        defs.push(s);
      } else {
        refs.push(s);
      }
    }
  }
  console.log("== esc 定义处 ==");
  for (const s of defs) console.log(s.rel + ":" + s.line);
  console.log("== esc( 调用点（file:line fn=所在函数 cat=落点粗分类）==");
  for (const s of calls) {
    console.log(
      s.rel + ":" + s.line + " fn=" + s.fn + " cat=" + s.cat +
      (s.transformed ? " [esc结果被再加工]" : "") +
      "\n    前文=" + JSON.stringify(s.ctx) +
      "\n    后文=" + JSON.stringify(s.rest));
  }
  console.log("== esc 非调用引用（含 const esc = ... 同名遮蔽、传参、判断）==");
  for (const s of refs) console.log(s.rel + ":" + s.line + " fn=" + s.fn);
  console.log("== 汇总 ==");
  console.log("扫描文件数=" + files.length);
  console.log("调用点=" + calls.length + " 定义=" + defs.length + " 非调用引用=" + refs.length);
  console.log("落点分类计数=" + JSON.stringify(byCat));
  console.log("按文件=" + JSON.stringify(byFile));
  console.log("所在函数分布=" + JSON.stringify(fnOf));
}

main();
