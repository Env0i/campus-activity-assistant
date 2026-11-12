// =====================================================================
// leaf.mjs —— 末端模块，import chain 最深处
//
// 作用：在 runOrder 里留下 leaf-top 痕迹，暴露 window.apiBridgeLeaf
// 只用来证明 import 链能完整走通。
// =====================================================================

// 模块顶层立即执行，比普通脚本延后
window.runOrder = window.runOrder || [];
window.runOrder.push('leaf-top');

// 挂到 window 上，让 Python 侧的 evaluate_js 能调到
window.apiBridgeLeaf = {
  hello: () => 'leaf-hello'
};
