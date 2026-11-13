// 列出基线（7e2d31c）桌面前端（local/ui 下，不含 m/ 手机页）里 esc(...) 的全部调用点，并按结果落点粗分类，供人工确认。
// 从仓库任意位置运行，只读，不联网：
//   node design/evidence/2026-11-12/refactor-audit/redo/scripts/esc_sites.mjs            # 汇总加非文本节点明细
//   node .../esc_sites.mjs --all                                                         # 全部调用点
//   node .../esc_sites.mjs --json
//
// 口径（每一步在数什么）：
// 1. 调用点 = 标识符 esc 后紧跟 "("，且前一个字符不是标识符字符或 "."（排除 foo.esc( 与 desc( 一类）。
//    定义 `function esc(` 本身不算调用点。
// 2. 落点 = 这次调用所在的字符串拼接里，紧挨在 esc(...) 前面的 HTML 片段处于什么位置：
//    先取同一条语句里 esc( 之前的文本（到上一个分号为止，最多 600 字符），把里面的字符串字面量内容拼起来，
//    非字符串的部分（变量、其他调用）用占位符代替；再看拼出的片段：
//      - 最后一个 "<" 在最后一个 ">" 之后 → 处在标签内部：
//          末尾是  on…="  或  on…='  → 事件处理器字符串
//          末尾是  href="/src="/action="（及单引号）→ URL
//          末尾是  ="  → 双引号属性；末尾是  ='  → 单引号属性；末尾是  =  → 无引号属性；其余 → 标签内其他
//      - 否则若片段里有 ">" → 文本节点
//      - 否则（片段里没有任何标签字符）→ 其他（不在 HTML 串里，如赋给 textContent、拼日志、拼 title 文本等）
//    这是启发式：模板字符串里的 ${…}、跨语句的拼接、变量里预先拼好的片段它看不到，所以明细里列出全部非「文本节点」的点，
//    需要人工回到代码里确认。
// 3. 同一文件里的 esc 定义落点不计。
import { execFileSync } from "node:child_process";

const BASE = "7e2d31c";
const root = execFileSync("git", ["rev-parse", "--show-toplevel"], { cwd: new URL(".", import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1"), encoding: "utf8" }).trim();
const sh = (args) => execFileSync("git", args, { cwd: root, encoding: "utf8", maxBuffer: 1 << 26 });
const files = sh(["ls-tree", "-r", "--name-only", BASE, "local/ui"]).split("\n").filter((f) => f.endsWith(".js") && !f.startsWith("local/ui/m/"));

function literalsBefore(text) {
  // 把一段 JS 代码里的字符串字面量内容拼起来；非字符串部分记为 \u0001
  let out = "", i = 0;
  const n = text.length;
  while (i < n) {
    const c = text[i];
    if (c === "'" || c === '"') {
      let k = i + 1, buf = "";
      while (k < n && text[k] !== c) { if (text[k] === "\\") { buf += text[k + 1] || ""; k += 2; continue; } buf += text[k]; k++; }
      out += buf; i = k + 1; continue;
    }
    if (c === "`") {
      let k = i + 1, buf = "";
      while (k < n && text[k] !== "`") {
        if (text[k] === "\\") { buf += text[k + 1] || ""; k += 2; continue; }
        if (text[k] === "$" && text[k + 1] === "{") { let d = 1; k += 2; while (k < n && d > 0) { if (text[k] === "{") d++; else if (text[k] === "}") d--; k++; } buf += "\u0001"; continue; }
        buf += text[k]; k++;
      }
      out += buf; i = k + 1; continue;
    }
    if (/\s|\+/.test(c)) { i++; continue; }
    if (out[out.length - 1] !== "\u0001") out += "\u0001";
    // 跳过一个连续的非空白、非引号、非加号的记号（变量、调用、运算符）
    while (i < n && !/[\s+'"`]/.test(text[i])) i++;
  }
  return out;
}

function classify(before) {
  const stmtStart = Math.max(before.lastIndexOf(";"), before.lastIndexOf("{\n") );
  let seg = before.slice(Math.max(0, stmtStart + 1)).slice(-600);
  const frag = literalsBefore(seg);
  const lt = frag.lastIndexOf("<"), gt = frag.lastIndexOf(">");
  if (lt > gt) {
    const tail = frag.slice(lt);
    if (/\bon[a-z]+\s*=\s*["']$/i.test(tail)) return "事件处理器字符串";
    if (/\b(href|src|action|formaction|poster|xlink:href)\s*=\s*["']?$/i.test(tail)) return "URL";
    if (/=\s*"$/.test(tail)) return "双引号属性";
    if (/=\s*'$/.test(tail)) return "单引号属性";
    if (/=\s*$/.test(tail)) return "无引号属性";
    return "标签内其他";
  }
  if (gt >= 0) return "文本节点";
  return "其他";
}

const sites = [];
for (const f of files) {
  const src = sh(["show", `${BASE}:${f}`]).replace(/\r\n/g, "\n");
  const re = /(?<![\w$.])esc\(/g;
  let m;
  while ((m = re.exec(src))) {
    const before = src.slice(0, m.index);
    const lineStart = src.lastIndexOf("\n", m.index) + 1;
    const lineText = src.slice(lineStart, src.indexOf("\n", m.index) < 0 ? src.length : src.indexOf("\n", m.index));
    if (/^\s*function\s+esc\(/.test(lineText)) continue;
    const line = src.slice(0, m.index).split("\n").length;
    sites.push({ file: f, line, kind: classify(before), text: lineText.trim().slice(0, 110) });
  }
}
const byKind = {}, byFile = {};
for (const s of sites) { byKind[s.kind] = (byKind[s.kind] || 0) + 1; byFile[s.file] = (byFile[s.file] || 0) + 1; }
if (process.argv.includes("--json")) {
  console.log(JSON.stringify({ base: BASE, total: sites.length, byKind, byFile, sites }, null, 1));
} else {
  console.log(`基线 ${BASE}  桌面前端 ${files.length} 个脚本（不含手机页）；esc 调用点共 ${sites.length} 处，分布在 ${Object.keys(byFile).length} 个文件`);
  console.log("按落点：" + Object.entries(byKind).map(([k, v]) => `${k} ${v}`).join("，"));
  console.log("按文件：" + Object.entries(byFile).sort((a, b) => b[1] - a[1]).map(([k, v]) => `${k.replace("local/ui/", "")} ${v}`).join("，"));
  const shown = process.argv.includes("--all") ? sites : sites.filter((s) => s.kind !== "文本节点");
  console.log(process.argv.includes("--all") ? "\n## 全部调用点" : "\n## 非「文本节点」的调用点（需人工确认）");
  for (const s of shown) console.log(`${s.file.replace("local/ui/", "")}:${s.line}\t${s.kind}\t${s.text}`);
}
