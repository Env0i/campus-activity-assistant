// leaf.mjs —— import 链末端模块
// 在顶层代码里留痕迹，验证"最深的模块也能被加载执行"

window.runOrder = window.runOrder || [];
window.runOrder.push('leaf-top');

window.apiBridgeLeaf = {
  name: 'leaf-mjs'
};
