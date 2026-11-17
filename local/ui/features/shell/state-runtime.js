/* 组件错误文案表与展示口径（纯状态推导，供视图层与普通脚本共用）。 */

/* 组件错误 → 一句话标题 + 恢复动作说明（后端 runtime_error 的唯一展示口径） */
export const RUNTIME_ERRORS = {
  worker_missing: { title: "程序组件缺失", hint: "无法找到所需程序组件。请重新下载完整版本，再选择「重新检查」。" },
  worker_permission: { title: "程序组件无法读取", hint: "组件文件在，但被系统拦住或没有权限（刚下载的文件常见）。右键程序 → 属性 → 勾「解除锁定」，或重新解压后再点「重新检查」。" },
  spawn_failed: { title: "程序组件启动失败", hint: "组件在但没能启动。点「重新检查」再试一次；反复出现请重新下载完整版本。" },
};

export function runtimeErrorCopy() {
  return RUNTIME_ERRORS[S.runtime.error] || RUNTIME_ERRORS.spawn_failed;
}
