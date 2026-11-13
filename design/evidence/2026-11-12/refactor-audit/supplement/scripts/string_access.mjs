#!/usr/bin/env node
// string_access.mjs —— 扫描前端代码中经字符串访问的全局与桥接方法名
//
// 用法：node design/evidence/2026-11-12/refactor-audit/supplement/scripts/string_access.mjs <repo-root>
// 输出 JSON 到 stdout，字段：
//   api_calls        —— api("xxx") / controller.api("xxx") 里的字符串参数集合
//   onBackend_kinds  —— window.onBackend.<kind> 的 kind 值集合（前端定义 + 后端 _emit 传入）
//   window_bracket   —— window["xxx"] 字符串键访问
//   phone_actions    —— phone_rules.py ACTION_PARAMS 白名单（Python 侧字符串）
//   other_evals      —— eval / Function / setTimeout("...") 等动态执行模式
//
// 基线：7e2d31c，所有行号以它为准。脚本只扫 git show 7e2d31c 检出的文件，
// 不读工作树里未提交的改动。

import fs from "node:fs";
import path from "node:path";
import { execSync } from "node:child_process";

const repoRoot = process.argv[2];
if (!repoRoot) {
  console.error("用法: node string_access.mjs <repo-root>");
  process.exit(1);
}

function gitShow(revPath) {
  try {
    return execSync(`git show "${revPath}"`, { cwd: repoRoot, encoding: "utf-8", maxBuffer: 20 * 1024 * 1024 });
  } catch {
    return "";
  }
}

function gitGrep(pattern, rev, glob) {
  try {
    return execSync(`git grep -n "${pattern}" ${rev} -- ${glob}`, { cwd: repoRoot, encoding: "utf-8", maxBuffer: 10 * 1024 * 1024 });
  } catch {
    return "";
  }
}

function extractQuotedStrings(text, openChar = '"') {
  const results = new Set();
  const closeChar = openChar === '"' ? '"' : "'";
  // 简单正则，处理转义
  const re = openChar === '"' ? /"((?:[^"\\]|\\.)*)"/g : /'((?:[^'\\]|\\.)*)'/g;
  let m;
  while ((m = re.exec(text)) !== null) {
    results.add(m[1]);
  }
  return results;
}

function extractApiCalls(text) {
  // api("xxx", ...) 或 api('xxx', ...) 或 controller.api("xxx")
  const results = new Set();
  const re = /(?:controller\.)?api\(\s*["']([^"']+)["']/g;
  let m;
  while ((m = re.exec(text)) !== null) {
    results.add(m[1]);
  }
  return results;
}

function extractOnBackendKinds(text) {
  // window.onBackend = { kind: ..., ... }
  const results = new Set();
  const re = /window\.onBackend\s*=\s*\{([\s\S]*?)\n\}/;
  const m = text.match(re);
  if (!m) return results;
  // 解析 kind: 后面是 (payload) => ... 或 function(...) 或 ...
  const kindRe = /(\w+)\s*:\s*(?:\(payload\)|\([^)]*\)|function|=>\s*\w)/g;
  let km;
  while ((km = kindRe.exec(m[1])) !== null) {
    results.add(km[1]);
  }
  return results;
}

function extractWindowBracket(text) {
  const results = new Set();
  const re = /window\[\s*["']([^"']+)["']\s*\]/g;
  let m;
  while ((m = re.exec(text)) !== null) {
    results.add(m[1]);
  }
  return results;
}

function extractOnBackendEmitKinds(text) {
  // 后端 _emit(kind, payload) 传入的 kind 值
  const results = new Set();
  const re = /self\._emit\(\s*["']([^"']+)["']\s*,/g;
  let m;
  while ((m = re.exec(text)) !== null) {
    results.add(m[1]);
  }
  return results;
}

function extractPhoneActionParams(text) {
  // ACTION_PARAMS = { "key": {...}, ... }
  const results = new Set();
  const re = /"(\w+)"\s*:\s*\{[^}]*\}/g;
  let m;
  while ((m = re.exec(text)) !== null) {
    results.add(m[1]);
  }
  // 也处理 set() 形式的空参数
  const re2 = /"(\w+)"\s*:\s*set\(\)/g;
  let m2;
  while ((m2 = re2.exec(text)) !== null) {
    results.add(m2[1]);
  }
  return results;
}

function extractOtherEvals(text) {
  const results = [];
  const patterns = [
    { name: "eval", re: /\beval\s*\(/g },
    { name: "new Function", re: /new\s+Function\s*\(/g },
    { name: "setTimeout(string)", re: /setTimeout\(\s*["']/g },
    { name: "setInterval(string)", re: /setInterval\(\s*["']/g },
    { name: "Function constructor", re: /Function\s*\(/g },
  ];
  for (const p of patterns) {
    const re = new RegExp(p.re.source, "g");
    let m;
    while ((m = re.exec(text)) !== null) {
      // 提取行号
      const lineNum = text.substring(0, m.index).split("\n").length;
      results.push({ pattern: p.name, line: lineNum });
    }
  }
  return results;
}

// ---- 扫描所有前端 JS 文件 ----

const filesGlob = execSync("git ls-tree -r --name-only 7e2d31c -- local/ui/", { cwd: repoRoot, encoding: "utf-8" })
  .split("\n").filter(f => f.endsWith(".js"));

const apiCalls = new Set();
const onBackendKinds = new Set();
const windowBracket = new Map();  // key -> file:line[]
const onBackendKindsByEmit = new Set();
const otherEvals = [];
const escCallsites = new Map();  // file -> 调用次数

for (const file of filesGlob) {
  const content = gitShow(`7e2d31c:${file}`);
  if (!content) continue;

  for (const name of extractApiCalls(content)) {
    apiCalls.add(name);
  }
  for (const kind of extractOnBackendKinds(content)) {
    onBackendKinds.add(kind);
  }

  // window["xxx"] 按位置记录
  const bracketRe = /window\[\s*["']([^"']+)["']\s*\]/g;
  let bm;
  while ((bm = bracketRe.exec(content)) !== null) {
    const lineNum = content.substring(0, bm.index).split("\n").length;
    const key = bm[1];
    if (!windowBracket.has(key)) windowBracket.set(key, []);
    windowBracket.get(key).push(`${file}:${lineNum}`);
  }

  // esc() 调用计数（第三节需要）
  let escCount = 0;
  const escRe = /\besc\s*\(/g;
  while (escRe.test(content)) escCount++;
  if (escCount > 0) escCallsites.set(file, escCount);

  // 其他 eval/Function 等
  for (const hit of extractOtherEvals(content)) {
    hit.file = file;
    otherEvals.push(hit);
  }
}

// ---- 后端文件扫描 ----

const appPy = gitShow("7e2d31c:local/app.py");
for (const kind of extractOnBackendEmitKinds(appPy)) {
  onBackendKindsByEmit.add(kind);
}

const phoneRulesPy = gitShow("7e2d31c:local/domain/phone_rules.py");
const phoneActions = extractPhoneActionParams(phoneRulesPy);

// ---- 输出 ----

const result = {
  api_calls: Array.from(apiCalls).sort(),
  onBackend_kinds_frontend: Array.from(onBackendKinds).sort(),
  onBackend_kinds_by_emit_backend: Array.from(onBackendKindsByEmit).sort(),
  window_bracket: Object.fromEntries([...windowBracket.entries()].sort()),
  phone_action_params: Array.from(phoneActions).sort(),
  esc_callsites: Object.fromEntries([...escCallsites.entries()].sort((a, b) => b[1] - a[1])),
  esc_total_calls: [...escCallsites.values()].reduce((s, n) => s + n, 0),
  other_evals: otherEvals,
  notes: [
    "所有扫描基于 git show 7e2d31c 检出的文件，不读工作树。",
    "onBackend_kinds_frontend = window.onBackend 定义的 kind（前端）；",
    "onBackend_kinds_by_emit_backend = 后端 _emit 传入的 kind（可能有前端没处理的）。",
    "两者的差集就是后端推了但前端没接的 kind（应该为空）。",
    "esc_callsites 用正则 \\besc\\s*\\( 匹配函数调用，一行多个算多个。",
    "当前版本 esc() 正则是 /[&<>\"]/g，不含单引号（第三节风险点）。",
  ],
};

console.log(JSON.stringify(result, null, 2));
