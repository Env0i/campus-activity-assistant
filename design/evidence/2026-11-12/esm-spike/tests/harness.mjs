// harness.mjs — ESM 测试工具样机
// Part A: 按 import 关系递归读模块源码（替代 read_ui_scripts 思路）
// Part B: 在 node 里注入假 DOM 后动态 import，跑行为断言
//
// 设计说明：
// - 不用任何 npm 依赖，只用 node 标准库 (fs, path, url)
// - 不用 jsdom/happy-dom，手写极简 mock
// - 假模块 (app.mjs, state.mjs, views.mjs, utils.mjs) 放在同目录

import { readFileSync } from 'node:fs';
import { resolve, dirname, relative, sep } from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

// ============================================================
// Part A — 递归解析 import，按拓扑输出源码，做文本断言
// ============================================================

/**
 * 从源码里用正则找出所有本地 import 的模块路径
 * 匹配模式：import ... from 'xxx' 或 import ... from "xxx"
 * 只提取相对路径（./ 或 ../ 开头），.js / .mjs 结尾
 */
function extractLocalImports(source) {
  const results = [];
  const re = /import\s+(?:[\s\S]*?from\s+)?['"]([^'"]+)['"]/g;
  let match;
  while ((match = re.exec(source)) !== null) {
    const spec = match[1];
    if (spec.startsWith('./') || spec.startsWith('../')) {
      if (spec.endsWith('.js') || spec.endsWith('.mjs')) {
        results.push(spec);
      }
    }
  }
  return results;
}

/**
 * 递归收集所有被 import 链触达的本地模块（.mjs / .js）。
 * 返回一个数组，元素形如 { path, source }。
 * visited 用绝对路径做 key，保证不重复读。
 */
function collectModules(entryAbsPath, visited = new Map()) {
  const absPath = resolve(entryAbsPath);
  if (visited.has(absPath)) return visited.get(absPath);

  const source = readFileSync(absPath, 'utf8');
  const dir = dirname(absPath);
  const imports = extractLocalImports(source);

  const node = { path: absPath, source, imports: [] };
  visited.set(absPath, node);

  for (const imp of imports) {
    const childAbs = resolve(dir, imp);
    node.imports.push(childAbs);
    collectModules(childAbs, visited);
  }

  return visited;
}

/** 简单拓扑排序：叶子在前，根（无被依赖者）在后。用 Kahn 算法。 */
function topoSort(nodesMap) {
  // nodesMap: Map<absPath, {path, source, imports: [childAbsPath]}>
  // 我们需要反过来建反向图，找出"被谁依赖"
  const inDegree = new Map();
  const reverse = new Map();
  for (const path of nodesMap.keys()) {
    inDegree.set(path, 0);
    reverse.set(path, []);
  }

  for (const [path, node] of nodesMap) {
    for (const child of node.imports) {
      if (inDegree.has(child)) {
        // child 被 path 依赖 —— path 在 child 之后
        // inDegree 表示"等待多少个前序节点"，这里反了：叶子节点（无 child）在最前
      }
    }
  }

  // 重新建模：edge = importer -> importee（依赖方向）
  // 拓扑序要求 importee 先于 importer
  // 入度 = 有多少人依赖我；出度 = 我依赖多少人
  // Kahn 算法：从入度 0 开始（没人依赖，即根）——这不是我们要的
  // 反转：从出度 0 开始（不依赖别人，即叶子）

  const outDegree = new Map();
  const dependents = new Map(); // child -> [parent]
  for (const path of nodesMap.keys()) {
    outDegree.set(path, 0);
    dependents.set(path, []);
  }
  for (const [path, node] of nodesMap) {
    outDegree.set(path, node.imports.length);
    for (const child of node.imports) {
      if (dependents.has(child)) dependents.get(child).push(path);
    }
  }

  const queue = [];
  const order = [];
  for (const [path, deg] of outDegree) {
    if (deg === 0) queue.push(path);
  }
  while (queue.length > 0) {
    const p = queue.shift();
    order.push(p);
    for (const parent of dependents.get(p) || []) {
      outDegree.set(parent, outDegree.get(parent) - 1);
      if (outDegree.get(parent) === 0) queue.push(parent);
    }
  }
  return order.map((p) => nodesMap.get(p));
}

/** 按 Part A 流程执行，返回结构化结果 */
function runPartA() {
  console.log('=== Part A: 递归 import 解析 ===\n');

  const entry = resolve(__dirname, 'app.mjs');
  const modulesMap = collectModules(entry);
  const sorted = topoSort(modulesMap);

  console.log(`入口: ${relative(__dirname, entry)}`);
  console.log(`去重后共 ${modulesMap.size} 个模块\n`);

  // 打印依赖图
  console.log('依赖图（箭头表示 import 关系，下游先）:');
  for (const node of sorted) {
    const rel = relative(__dirname, node.path);
    const impRel = node.imports.map((p) => relative(__dirname, p)).join(', ');
    console.log(`  ${rel}  ${impRel ? `<- [${impRel}]` : '(叶子)'}`);
  }

  // 打印源码块（按拓扑序）
  console.log('\n--- 源码块（按拓扑顺序） ---');
  for (const node of sorted) {
    const rel = relative(__dirname, node.path);
    console.log(`\n>>> FILE: ${rel}`);
    console.log(node.source.trim());
    console.log('<<< END');
  }

  // 文本断言演示
  console.log('\n--- 文本断言 ---');
  const allSources = sorted.map((n) => n.source).join('\n');
  const checks = [
    { desc: 'formatActivityName 函数签名存在', pattern: /export function formatActivityName\(/, pass: allSources },
    { desc: 'renderCards 函数签名存在', pattern: /export function renderCards\(/, pass: allSources },
    { desc: 'utils.mjs 中包含 VERSION 常量', pattern: /export const VERSION = '1\.0\.0'/, pass: modulesMap.get(resolve(__dirname, 'utils.mjs')).source },
    { desc: 'app.mjs 顶层有 document.body.innerHTML 赋值', pattern: /document\.body\.innerHTML/, pass: modulesMap.get(resolve(__dirname, 'app.mjs')).source },
    { desc: 'state.mjs 直接 import 了 utils.mjs', pattern: /from '\.\/utils\.mjs'/, pass: modulesMap.get(resolve(__dirname, 'state.mjs')).source },
    { desc: '不存在假字符串 "__NO_SUCH_FUNCTION__"', pattern: /__NO_SUCH_FUNCTION__/, pass: allSources, negate: true },
  ];

  let aPassed = 0, aFailed = 0;
  for (const c of checks) {
    const hit = c.pattern.test(c.pass);
    const ok = c.negate ? !hit : hit;
    const mark = ok ? 'PASS' : 'FAIL';
    console.log(`  [${mark}] ${c.desc}`);
    ok ? aPassed++ : aFailed++;
  }

  console.log(`\nPart A 断言: ${aPassed} 通过 / ${aFailed} 失败`);
  return { moduleCount: modulesMap.size, passed: aPassed, failed: aFailed };
}

// ============================================================
// Part B — 注入极简 DOM mock，动态 import，行为断言
// ============================================================

function buildMinimalDOM() {
  // 极简易 DOM mock，只覆盖 demo 模块需要用到的方法
  const body = {
    _html: '',
    set innerHTML(v) { this._html = v; },
    get innerHTML() { return this._html; },
    appendChild(child) {
      if (!Array.isArray(this._children)) this._children = [];
      this._children.push(child);
    },
    get children() { return this._children || []; },
  };

  function createElement(tag) {
    const el = {
      tagName: tag.toUpperCase(),
      dataset: {},
      _text: '',
      get textContent() { return this._text; },
      set textContent(v) { this._text = v; },
      _html: '',
      get innerHTML() { return this._html; },
      set innerHTML(v) { this._html = v; },
      className: '',
      appendChild(child) {
        if (!Array.isArray(this._children)) this._children = [];
        this._children.push(child);
      },
      get children() { return this._children || []; },
    };
    return el;
  }

  // 从 body.innerHTML 里模拟一个轻量的 DOM 树，以便 getElementById / querySelector 能找到元素
  // 方案：简单的哈希表 id -> element；每次 innerHTML 变化时重建
  const idIndex = new Map();

  function rebuildFromBodyHTML() {
    idIndex.clear();
    // 极简正则：找 id="xxx" 的 HTML 元素
    const idRe = /id=["']([^"']+)["']/g;
    let m;
    while ((m = idRe.exec(body._html)) !== null) {
      const idValue = m[1]; // 立即捕获，避免 global 正则 lastIndex 造成的闭包隐患
      const fakeEl = {
        tagName: 'UNKNOWN',
        dataset: {},
        _text: '',
        get textContent() { return this._text; },
        set textContent(v) { this._text = v; },
        _html: '',
        get innerHTML() { return this._html; },
        set innerHTML(v) { this._html = v; },
        className: '',
        appendChild(child) {
          if (!Array.isArray(this._children)) this._children = [];
          this._children.push(child);
        },
      };
      idIndex.set(idValue, fakeEl);
    }
  }

  // hook body.innerHTML 的 setter
  const origBodySet = Object.getOwnPropertyDescriptor(body, 'innerHTML').set;
  Object.defineProperty(body, 'innerHTML', {
    get() { return body._html; },
    set(v) {
      body._html = v;
      rebuildFromBodyHTML();
    },
    configurable: true,
  });

  const document = {
    body,
    createElement,
    getElementById(id) {
      // 先查动态索引（由 set textContent 等更新）
      if (idIndex.has(id)) return idIndex.get(id);
      // 再从 body HTML 扫一次（捕获新 innerHTML 设置）
      rebuildFromBodyHTML();
      return idIndex.get(id) || null;
    },
    querySelector() { return null; }, // demo 不用
    addEventListener() {},
    removeEventListener() {},
    get title() { return ''; },
    set title(_) {},
    documentElement: {},
    head: { appendChild() {} },
  };

  const windowObj = { document };
  // 互相指向
  document.defaultView = windowObj;
  windowObj.window = windowObj;

  return { document, window: windowObj };
}

async function runPartB() {
  console.log('\n\n=== Part B: 动态 import + 行为断言 ===\n');

  // 注入极简 DOM mock
  const dom = buildMinimalDOM();
  globalThis.document = dom.document;
  globalThis.window = dom.window;
  // 顺手挂几个 demo 可能用到的全局
  globalThis.setTimeout = setTimeout;
  globalThis.clearTimeout = clearTimeout;

  console.log('已注入 mock DOM 到 globalThis');
  console.log(`globalThis.document === globalThis.window.document -> ${globalThis.document === globalThis.window.document}`);
  console.log('尝试动态 import app.mjs ...');

  const appPath = resolve(__dirname, 'app.mjs');
  const appUrl = new URL('file://' + appPath.replace(/\\/g, '/'));

  let mod;
  let importError = null;
  try {
    mod = await import(appUrl);
    console.log('动态 import 成功，导出项:', Object.keys(mod).join(', '));
  } catch (err) {
    importError = err;
    console.error('动态 import 失败:', err?.message || err);
    // 再试 fileURLToPath 形式
    try {
      const altPath = fileURLToPath(new URL('./app.mjs', import.meta.url));
      mod = await import(altPath);
      console.log('fileURLToPath 形式成功，导出项:', Object.keys(mod).join(', '));
      importError = null;
    } catch (err2) {
      console.error('fileURLToPath 形式也失败:', err2?.message || err2);
    }
  }

  if (importError) {
    console.log('\nPart B: 无法 import，跳过行为断言');
    return { imported: false, initResult: null, passed: 0, failed: 0 };
  }

  // 调用 init()
  console.log('\n调用 app.init() ...');
  let initResult = null;
  try {
    initResult = mod.init();
    console.log('init() 返回:', JSON.stringify(initResult, null, 2));
  } catch (err) {
    console.error('init() 抛错:', err?.message || err);
    console.error('stack:', err?.stack || '(无堆栈)');
  }

  // 行为断言
  console.log('\n--- 行为断言 ---');
  let bPassed = 0, bFailed = 0;
  const bodyHTML = globalThis.document.body.innerHTML;

  const checks = [
    {
      desc: 'document.body.innerHTML 包含 <h1 id="app-title">',
      ok: () => bodyHTML.includes('id="app-title"'),
    },
    {
      desc: 'document.body.innerHTML 包含 <div id="card-root">',
      ok: () => bodyHTML.includes('id="card-root"'),
    },
    {
      desc: 'init() 返回 activityCount = 2',
      ok: () => initResult && initResult.activityCount === 2,
    },
    {
      desc: 'init() 返回 titleText 包含 "活动列表 v1.0.0"',
      ok: () => initResult && initResult.titleText.includes('活动列表 v1.0.0'),
    },
    {
      desc: 'getElementById("app-title") 存在并能读到 textContent',
      ok: () => {
        const el = globalThis.document.getElementById('app-title');
        return el && typeof el.textContent === 'string';
      },
    },
    {
      desc: 'getElementById("card-root") 存在',
      ok: () => globalThis.document.getElementById('card-root') !== null,
    },
  ];

  for (const c of checks) {
    let ok = false;
    try { ok = !!c.ok(); } catch { ok = false; }
    const mark = ok ? 'PASS' : 'FAIL';
    console.log(`  [${mark}] ${c.desc}`);
    ok ? bPassed++ : bFailed++;
  }

  console.log(`\nPart B 断言: ${bPassed} 通过 / ${bFailed} 失败`);
  return { imported: true, initResult, passed: bPassed, failed: bFailed };
}

// ============================================================
// 入口
// ============================================================

try {
  const a = runPartA();
  const b = await runPartB();
  console.log('\n\n========== 总结 ==========');
  console.log(`Part A: ${a.passed}/${a.passed + a.failed} 通过，共 ${a.moduleCount} 个模块`);
  console.log(`Part B: ${b.imported ? `import 成功，${b.passed}/${b.passed + b.failed} 通过` : 'import 失败'}`);
} catch (err) {
  console.error('harness 顶层错误:', err);
  process.exitCode = 1;
}
