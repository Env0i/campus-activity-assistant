## review2 表 B 独立复算

| 序 | 文件 | 归属 | 行数 | 顶层函数数 | 全局名字数 | S 写入处数 |
|---|---|---|---|---|---|---|
| 1 | `local/ui/led.js` | 未排进 | 118 | 0 | 0 | 0 |
| 2 | `local/ui/state/store.js` | 1共用 | 199 | 2 | 12 | 0 |
| 3 | `local/ui/state/terms.js` | 未排进 | 19 | 2 | 2 | 0 |
| 4 | `local/ui/state/rounds.js` | 未排进 | 85 | 7 | 9 | 8 |
| 5 | `local/ui/controllers/bridge.js` | 未排进 | 35 | 3 | 3 | 0 |
| 6 | `local/ui/controllers/refresh.js` | 1共用 | 614 | 23 | 32 | 73 |
| 7 | `local/ui/views/list.js` | 未排进 | 449 | 18 | 18 | 7 |
| 8 | `local/ui/state/task-display.js` | 1C | 248 | 11 | 12 | 0 |
| 9 | `local/ui/views/plan-panel.js` | 1C | 1367 | 56 | 58 | 6 |
| 10 | `local/ui/controllers/plan.js` | 1C | 532 | 20 | 21 | 54 |
| 11 | `local/ui/state/clock.js` | 未排进 | 314 | 18 | 29 | 0 |
| 12 | `local/ui/views/clock.js` | 未排进 | 32 | 1 | 1 | 0 |
| 13 | `local/ui/controllers/clock.js` | 未排进 | 61 | 3 | 3 | 5 |
| 14 | `local/ui/state/plan.js` | 1C | 175 | 14 | 16 | 16 |
| 15 | `local/ui/controllers/plan-events.js` | 1C | 134 | 5 | 5 | 16 |
| 16 | `local/ui/state/login.js` | 1B | 141 | 9 | 9 | 22 |
| 17 | `local/ui/views/login.js` | 1B | 173 | 4 | 5 | 4 |
| 18 | `local/ui/views/relogin.js` | 1B | 555 | 34 | 43 | 20 |
| 19 | `local/ui/views/clock-pop.js` | 未排进 | 152 | 8 | 8 | 3 |
| 20 | `local/ui/views/status-cards.js` | 1B | 204 | 14 | 17 | 3 |
| 21 | `local/ui/views/log.js` | 未排进 | 29 | 2 | 2 | 1 |
| 22 | `local/ui/views/terms.js` | 未排进 | 507 | 35 | 37 | 0 |
| 23 | `local/ui/controllers/terms.js` | 未排进 | 477 | 17 | 18 | 85 |
| 24 | `local/ui/views/update.js` | 未排进 | 187 | 6 | 8 | 3 |
| 25 | `local/ui/views/help.js` | 未排进 | 67 | 6 | 6 | 0 |
| 26 | `local/ui/views/settings.js` | 1A | 397 | 19 | 21 | 2 |
| 27 | `local/ui/views/phone.js` | 1A | 1252 | 10 | 14 | 0 |
| 28 | `local/ui/controllers/update.js` | 未排进 | 148 | 8 | 8 | 15 |
| 29 | `local/ui/controllers/prefs.js` | 未排进 | 41 | 3 | 3 | 16 |
| 30 | `local/ui/state/filters.js` | 未排进 | 393 | 25 | 25 | 10 |
| 31 | `local/ui/state/conflict.js` | 未排进 | 176 | 17 | 19 | 0 |
| 32 | `local/ui/views/selection.js` | 未排进 | 90 | 6 | 8 | 3 |
| 33 | `local/ui/views/conflict-tip.js` | 未排进 | 147 | 11 | 11 | 9 |
| 34 | `local/ui/controllers/cancel.js` | 未排进 | 94 | 6 | 6 | 13 |
| 35 | `local/ui/state/labels.js` | 未排进 | 107 | 10 | 10 | 0 |
| 36 | `local/ui/controllers/tick.js` | 未排进 | 165 | 10 | 11 | 4 |
| 37 | `local/ui/state/time.js` | 未排进 | 154 | 15 | 18 | 0 |
| 38 | `local/ui/views/tour.js` | 未排进 | 174 | 13 | 13 | 12 |
| 39 | `local/ui/controllers/window.js` | 未排进 | 276 | 14 | 15 | 1 |
| 40 | `local/ui/app.js` | 1共用 | 655 | 2 | 7 | 33 |

文件总数 40（index.html 40 + 额外 0）；同一名字跨文件顶层定义 0 处核对值：0；同文件同名 1 处：PhonePanel: views/phone.js:154 与 :1252；唯一名 562 / 逐文件合计 563。

### 未排进脚本与步骤 1 文件的相互引用

| 文件 | 引用步骤1定义名数 | 名字 | 被步骤1引用名数 | 名字 |
|---|---|---|---|---|
| `local/ui/led.js` | 0 | — | 0 | — |
| `local/ui/state/terms.js` | 1 | S | 2 | termsAccepted、termsLocked |
| `local/ui/state/rounds.js` | 1 | S | 7 | bumpRoundGeneration、cacheRoundPayload、firstNotice、loginPresent、markRoundApplied、newRoundId、takeRoundPayload |
| `local/ui/controllers/bridge.js` | 0 | — | 3 | api、hasBridge、waitForBridge |
| `local/ui/views/list.js` | 14 | $、S、executionView、paintBanners、paintBoardState、paintChecks、paintLed、paintPlan、paintRoute、paintSelected、planOutcome、taskDisplayLabel、unknownLabel、updateControls | 3 | paintRail、refreshLoginEmptyState、render |
| `local/ui/state/clock.js` | 2 | S、updateControls | 11 | TASK_RUNTIME_FIELDS、_monoMs、bnLeftSec、bnowS、businessNowMs、clockParts、clockPopOpenNow、clockReading、clockUiState、clockUncertaintyText、ingestBusinessClock |
| `local/ui/views/clock.js` | 1 | $ | 1 | paintClockStatus |
| `local/ui/controllers/clock.js` | 2 | S、msg | 3 | pollClockNow、resyncClock、startClockPolling |
| `local/ui/views/clock-pop.js` | 3 | $、S、numOrNull | 3 | applyClock、closeClockPop、toggleClockPop |
| `local/ui/views/log.js` | 3 | $、S、addLog | 2 | copyLog、setLogOpen |
| `local/ui/views/terms.js` | 3 | $、FIRST_USE_POINTS、S | 7 | applyTermsFooter、closeTermsIntroBox、closeTermsUpdateBox、reopenTermsBox、switchTermsDoc、termsCloseIntent、termsUpdateMode |
| `local/ui/controllers/terms.js` | 6 | S、addLog、msg、paintBanners、refresh、updateControls | 11 | acceptTerms、declineTerms、ensureLicenseText、ingestTerms、markTermsUnknown、noteTermsRequired、openTerms、openTermsReader、recheckTerms、restoreTermsFocus、resumeTermsTour |
| `local/ui/views/update.js` | 2 | $、S | 0 | — |
| `local/ui/views/help.js` | 5 | $、DEFAULT_HELP、PhonePanel、S、addLog | 5 | fillHelp、helpStatus、paintReplayButtons、replayTourFrom、showHelp |
| `local/ui/controllers/update.js` | 2 | S、msg | 7 | cancelDownload、checkUpdate、confirmDownload、launchInstaller、receiveUpdate、restoreUpdate、startDownload |
| `local/ui/controllers/prefs.js` | 2 | S、addLog | 1 | savePrefs |
| `local/ui/state/filters.js` | 3 | S、setResult、verifiedSigned | 13 | clearSelection、findItem、groupSelected、isEligibleForPlan、nextOpen、normalize、selectedItems、signStartPending、signedClash、sleepMissedNames、taskMissedBySleep、toggleSelection、validateSelection |
| `local/ui/state/conflict.js` | 1 | S | 1 | cancelBlock |
| `local/ui/views/selection.js` | 3 | $、S、setResult | 4 | paintChips、setFilter、setFilterOpen、showPlanError |
| `local/ui/views/conflict-tip.js` | 2 | $、S | 8 | placeTip、tipClose、tipGoSigned、tipKey、tipLater、tipOpen、tipSoon、tipStay |
| `local/ui/controllers/cancel.js` | 3 | S、addLog、refresh | 3 | cancelAsk、cancelAskDismiss、cancelConfirm |
| `local/ui/state/labels.js` | 1 | verifiedSigned | 8 | activityTimeText、leftOf、modeOf、modeText、signStartKnown、stateOf、taskClass、taskLabel |
| `local/ui/controllers/tick.js` | 20 | $、RUNNING_STATUSES、S、SLEEP_GAP_MS、addLog、addLogFresh、msg、paintBanners、paintCountdown、paintEditNote、paintLed、paintLogin、paintRoute、paintRunPanel、paintSelected、runHeadKey、runtimeErrorCopy、taskDisplayDetail、taskDisplayLabel、taskModePrefix | 7 | cleanReason、doCheck、grabHint、listErrorCopy、receiveSecondOpen、stripLabel、tick |
| `local/ui/state/time.js` | 1 | WEEK | 11 | durText、esc、fmt、fmtClock、hm、hmsDay、schoolParts、shortTime、startOfDay、toTs、whenText |
| `local/ui/views/tour.js` | 4 | $、S、TOUR_STEPS、TOUR_VERSION | 11 | maybeStartTour、paintTour、requestAutoTour、tourClose、tourGuardClick、tourPauseNow、tourResumeNow、tourShouldAutoStart、tourSkip、tourTrapTab、tourVisible |
| `local/ui/controllers/window.js` | 3 | S、addLog、msg | 1 | openWindowCloseDialog |

未排进脚本共 26 个。

## 复核说明（后端架构师）

- 行数独立核 3 个文件一致（refresh 614、state/plan 175、phone 1252）；顶层函数与全局名独立核 2 个文件一致；phone.js 全局名独立计 13（唯一名口径）vs 表 14（逐文件定义口径，同文件同名 PhonePanel 两处），口径差可对上；S 写入 refresh.js grep 粗核 71 vs 表 73，量级一致（grep 按行漏续行 2 处）。
- 口径注：本轮独立实现的 S 写入判定含赋值/自增/delete/容器变异/Object.assign，与第一轮口径声明一致。
