// state.mjs — 模拟产品 state 模块，管理活动列表
import { formatActivityName, VERSION } from './utils.mjs';

const activities = [];

export function addActivity(raw) {
  const name = formatActivityName(raw?.name);
  if (!name) return null;
  const item = { id: activities.length + 1, name, signed: false };
  activities.push(item);
  return item;
}

export function listActivities() {
  return activities.slice();
}

export function getStateVersion() {
  return VERSION;
}
