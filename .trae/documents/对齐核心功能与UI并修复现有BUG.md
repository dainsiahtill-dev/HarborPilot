## 现状结论（已确认的“未对接”）
- PM 单次运行接口已实现但 UI 没入口：后端有 [/pm/run_once](file:///c:/Users/dains/Documents/Git/Harborpilot/desktop/backend/server.py#L604-L627)，前端只切换 start_loop/stop（[App.tsx](file:///c:/Users/dains/Documents/Git/Harborpilot/desktop/frontend/src/app/App.tsx#L386-L432)）。
- 后端提供 pm_report/pm_log 的 WS 通道，但新 UI 未订阅：后端 channel 映射见 [server.py](file:///c:/Users/dains/Documents/Git/Harborpilot/desktop/backend/server.py#L38-L48)，现 UI 只订阅 dialogue 与少量 subprocess 日志（[App.tsx](file:///c:/Users/dains/Documents/Git/Harborpilot/desktop/frontend/src/app/App.tsx#L511-L526)，[LogsModal.tsx](file:///c:/Users/dains/Documents/Git/Harborpilot/desktop/frontend/src/app/components/LogsModal.tsx#L11-L124)）。
- /state/snapshot 返回 focus/notes/tasks/file_status 等大量信息，但 UI 基本没展示（[server.py](file:///c:/Users/dains/Documents/Git/Harborpilot/desktop/backend/server.py#L513-L523)）。
- ArtifactsSidebar 标注“Live”但并未真正实现 live（events/trajectory 甚至没后端 channel 映射）：[ArtifactsSidebar.tsx](file:///c:/Users/dains/Documents/Git/Harborpilot/desktop/frontend/src/app/components/ArtifactsSidebar.tsx#L44-L50)。
- 前端遗留占位入口仍在仓库，容易误改错文件：真实入口渲染 [./app/App](file:///c:/Users/dains/Documents/Git/Harborpilot/desktop/frontend/src/main.tsx#L1-L10)，旧占位在 [src/App.tsx](file:///c:/Users/dains/Documents/Git/Harborpilot/desktop/frontend/src/App.tsx)。

## 已定位的高优先级 BUG（可直接修）
- Director start/stop 不校验 res.ok，失败静默（[App.tsx](file:///c:/Users/dains/Documents/Git/Harborpilot/desktop/frontend/src/app/App.tsx#L421-L432)）。
- 后端 read_file_tail() 读全文件再截断，日志变大后会卡死/爆内存（[server.py](file:///c:/Users/dains/Documents/Git/Harborpilot/desktop/backend/server.py#L279-L292)）；WS snapshot 与 /files/read 都会触发（[server.py](file:///c:/Users/dains/Documents/Git/Harborpilot/desktop/backend/server.py#L704-L740)）。
- 前端 apiFetch/connectWebSocket 把后端连接信息永久缓存，后端重启/端口变化后会“永久坏掉直到重启前端”（[api.ts](file:///c:/Users/dains/Documents/Git/Harborpilot/desktop/frontend/src/api.ts#L8-L55)）。
- DialoguePanel 成功率逻辑与真实事件类型不匹配：loop-pm 发的是 type=handoff/say/warning/result（[loop-pm.py](file:///c:/Users/dains/Documents/Git/Harborpilot/loops/loop-pm.py#L448-L537)），但 UI 统计用 event.type==='done'（[DialoguePanel.tsx](file:///c:/Users/dains/Documents/Git/Harborpilot/desktop/frontend/src/app/components/DialoguePanel.tsx#L66-L80)），导致成功率长期为 0。
- FileViewer “✓ PASSED” 纯靠文件名包含 QA（[FileViewer.tsx](file:///c:/Users/dains/Documents/Git/Harborpilot/desktop/frontend/src/app/components/FileViewer.tsx#L44-L49)），属于错误展示。

## 实施方案（按最小风险、最大收益排序）
### 1) 把后端能力接到 UI（功能缺口修复）
- 在顶部控制区增加“PM 运行一次”入口：调用 /pm/run_once，并在 UI 状态上区分 once/loop（后端已返回 mode）。
- 扩展 LogsModal 的日志源：新增 PM_REPORT / PM_LOG（以及可选 planner/ollama/qa/runlog），并支持 WS 订阅对应 channel，做到实时滚动。
- 将 /state/snapshot 的 focus/notes/tasks/file_status 在 UI 中展示：
  - 最小实现：在主界面增加一个只读“快照卡片”（focus、notes、task 数量、file_status 列表）。
  - 进阶：把 file_status 用在左侧列表里（例如缺失/过期提示）。
- 对“Live”标记做一致性：
  - 方案 A：后端补齐 events/trajectory 的 channel 映射 + UI 订阅；
  - 方案 B：若暂不支持 live，则移除对应 badge，避免误导。

### 2) 修复已存在的 BUG（稳定性）
- 前端：统一 start/stop 的错误处理（复用 togglePm 的 res.ok + 解析 detail 逻辑），并在 UI 里展示错误提示（而不是仅 console）。
- 前端：在 apiFetch/connectWebSocket 遇到网络错误/401 时，清空 cachedInfo 并重试一次；同时为 WS 增加自动重连或显式“重新连接”按钮。
- 后端：把 read_file_tail() 改成“从文件尾部读取”的流式 tail（按字节倒读或逐块 seek），避免全量读入内存；WS snapshot 与 /files/read 都走新实现。
- 前端：修正 DialoguePanel 成功率口径：
  - 以 event.type==='result' 且包含 task_id 为完成事件；
  - 从内容/（或更推荐）给 loop-pm 的 emit_dialogue 增加 meta.status 字段来计算 success/fail/unknown。
- 前端：移除 FileViewer 的假 PASSED；改为：
  - 如果当前查看的是 QA_RESPONSE.md，则尝试从 DIRECTOR_RESULT.json 的 status/acceptance 推导徽章；
  - 若无数据则不显示。
- 代码维护性：处理遗留占位 src/App.tsx（重命名为 PlaceholderApp 或删除不用入口），避免后续改错文件。

### 3) 验证与回归
- 运行已有 Python 测试（tests/ 与 tests/functional/）覆盖 PM/Director/IO 行为。
- 前端构建/类型检查，确保 TS/ESLint 不引入新问题。
- 手动验证桌面 UI：
  - PM run once / start loop / stop；
  - LogsModal 切换不同 source 的实时与历史加载；
  - 后端重启后前端可恢复（fetch + WS）；
  - 大日志文件下打开日志不卡顿。

## 交付物
- 一组前后端改动：新增 UI 入口、补齐 WS/日志展示、修复稳定性与统计/徽章等展示 bug。
- 对应的测试通过与最小手工验证步骤说明。
