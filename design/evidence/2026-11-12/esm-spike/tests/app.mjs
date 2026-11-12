// app.mjs — 入口模块
import { addActivity, listActivities, getStateVersion } from './state.mjs';
import { renderCards, showTitle } from './views.mjs';

export function init() {
  // 构造几块假数据
  addActivity({ name: '  春季运动会 ' });
  addActivity({ name: '  学术讲座  ' });

  // 操作 DOM
  document.body.innerHTML = '<h1 id="app-title"></h1><div id="card-root"></div>';
  showTitle('活动列表 v' + getStateVersion());

  const root = document.getElementById('card-root');
  const count = renderCards(root, listActivities());

  // 返回一个结构化结果供断言
  return {
    activityCount: count,
    titleText: document.getElementById('app-title')?.textContent || '',
    bodyHTML: document.body.innerHTML,
  };
}
