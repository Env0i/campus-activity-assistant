export function tourVisible() {
  const box = $("#tour");
  return !!(S.tour.open && !S.tour.paused && box && !box.hidden);
}

/* 「勾选」那一步的目标：时刻表里第一行可以勾选的活动（不代替用户勾） */
function tourRowTarget() {
  const check = document.querySelector("#rows .row-check:not([disabled])");
  return check && check.closest ? check.closest(".row") : null;
}

export function paintTour() {
  if (!S.tour.open || S.tour.paused) return;
  const box = $("#tour");
  const step = TOUR_STEPS[S.tour.step];
  const total = TOUR_STEPS.length;
  $("#tour-step").textContent = "第 " + (S.tour.step + 1) + "/" + total + " 步";
  $("#tour-prev").disabled = S.tour.step === 0;
  $("#tour-next").textContent = S.tour.step === total - 1 ? "完成" : "下一步";
  $("#tour-dots").innerHTML = TOUR_STEPS.map((s, i) =>
    '<i class="' + (i === S.tour.step ? "on" : "") + '"></i>').join("");
  const target = step.target === "row" ? tourRowTarget()
    : document.querySelector('[data-tour-target="' + step.target + '"]');
  S.tour.rowEl = step.target === "row" ? target : null;
  /* TR05（原型 Main:1302）：第 2 步用户勾选高亮行后卡片换文案，再点一次取消勾选换回。
   * 勾选经 toggleSelection → render → 这里重画，不用另挂 change 监听；
   * 只认 interactive 那一步与高亮行自己的复选框，其余步骤文案不变。 */
  const rowCheck = (step.interactive && target && target.querySelector)
    ? target.querySelector(".row-check") : null;
  const picked = !!(rowCheck && rowCheck.checked);
  $("#tour-title").textContent = picked ? "加入计划了" : step.title;
  $("#tour-text").textContent = picked
    ? "右边的清单多了一场，报名还没有开始。想取消，再点一次这一行。" : step.text;
  /* 可操作那一步：遮罩不挡点击，改由 tourGuardClick 只放行那一行 */
  if (box.classList) box.classList.toggle("is-interactive", !!step.interactive);
  /* 目标缺失/隐藏/窄窗（≤980）时不做高亮，退回底部静态说明条——
   * 不伪造定位，也不挡运行中的操作 */
  const usable = !!target && window.innerWidth > 980 &&
                 target.offsetWidth > 0 && target.getClientRects().length > 0;
  /* 两个类各管一件事：is-bottom 只管卡片落到页面底部（目标不可用或卡片放不下），
   * no-target 只在根本没有可高亮目标时用。原来把「隐藏高亮框」挂在 is-bottom 上，
   * 卡片一放到底部就把目标框也藏了，目标明明在也看不见（R1）。 */
  box.classList.toggle("is-bottom", !usable);
  box.classList.toggle("no-target", !usable);
  const spot = $("#tour-spot");
  const card = $("#tour-card");
  card.style.top = "";
  card.style.left = "";
  if (!usable) {
    spot.style.top = spot.style.left = spot.style.width = spot.style.height = "";
    return;
  }
  const rect = target.getBoundingClientRect();
  const pad = 6;
  spot.style.top = Math.round(rect.top - pad) + "px";
  spot.style.left = Math.round(rect.left - pad) + "px";
  spot.style.width = Math.round(rect.width + pad * 2) + "px";
  spot.style.height = Math.round(rect.height + pad * 2) + "px";
  /* 卡片优先贴目标下方，放不下换上方，再放不下交回底部说明条 */
  const cw = card.offsetWidth || 340;
  const ch = card.offsetHeight || 200;
  const gap = 12;
  let top = rect.bottom + gap;
  if (top + ch > window.innerHeight - 12) top = Math.max(12, rect.top - ch - gap);
  if (top <= 12 && rect.top < ch + 12) {
    box.classList.add("is-bottom");
    return;
  }
  card.style.top = Math.round(top) + "px";
  card.style.left = Math.round(Math.min(Math.max(12, rect.left), window.innerWidth - cw - 12)) + "px";
}
