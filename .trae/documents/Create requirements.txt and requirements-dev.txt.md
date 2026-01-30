# HarborPilot 增强计划：迈向无人值守与可观测性

本计划基于用户反馈，优先补全 HarborPilot 在**人工介入管理**、**历史回溯**、**自动恢复**与**检索能力**上的短板，旨在显著提升“无人值守”的鲁棒性与排查效率。

---

## 第一阶段：统一介入中心与状态管理 (Intervention Hub & Recovery)
**目标**：解决“流程卡住不知情”与“崩溃后难以恢复”的痛点，打造一个集中的控制台。

### 1.1 人工介入统一中心 (Intervention Hub)
*   **功能描述**：
    *   在 Dashboard 侧边栏或顶栏增加“待处理事项 (Action Required)”入口，徽章显示待办数量。
    *   **聚合内容**：
        *   **AGENTS 生成确认**：当 PM 生成新的 Agent 角色时。
        *   **PLAN 变更确认**：当 PM 修改了关键计划时。
        *   **依赖缺失警告**：requirements.txt 变动或环境检查失败。
        *   **权限/风险阻断**：Director 触发了 Policy Block (如修改敏感文件)。
    *   **操作**：列表展示每项摘要，提供 [批准] / [拒绝] / [忽略] / [跳转详情] 按钮。
*   **技术实现**：
    *   前端：新增 `InterventionCenter.tsx` 组件与 Context 状态。
    *   后端/文件：PM/Director 在 `state/` 下生成 `INTERVENTIONS.json` (或复用 events stream)，前端轮询或监听变更。

### 1.2 运行状态快照与恢复 (Resume Run)
*   **功能描述**：
    *   在 Dashboard 首页检测是否存在“非正常结束”的 Run (无最终 Result 或状态为 Running 但进程已消失)。
    *   提供“**恢复上次运行 (Resume Last Run)**”按钮。
    *   点击后，CLI 带上 `--resume` 或特定 `run_id` 参数重新拉起，自动加载 `memory/last_state.json` 继续执行。
*   **技术实现**：
    *   后端：完善 `loop-pm.py` / `loop-director.py` 的断点续传逻辑（利用 existing events/memory）。
    *   前端：在 ControlPanel 增加 Resume 逻辑分支。

---

## 第二阶段：全链路可观测性增强 (Observability++)
**目标**：让排查问题从“翻日志”变成“搜日志”，并提供跨运行的宏观视角。

### 2.1 日志/对话全文检索 (Global Search)
*   **功能描述**：
    *   LogsModal 与 DialoguePanel 增加全局搜索框。
    *   支持语法：`error:QA_FAIL` (按错误码), `task:123` (按任务ID), `run:latest` (按运行), `text:关键词`。
    *   搜索结果高亮，并支持点击跳转到对应 Event 卡片。
*   **技术实现**：
    *   前端：基于内存中的 `events` 数组实现高效过滤与索引。
    *   UI：搜索栏组件与高亮渲染逻辑。

### 2.2 运行历史与对比 (Run History & Diff)
*   **功能描述**：
    *   新增“History”页面，展示历史 Run 列表卡片（时间、Task数、成功率、耗时）。
    *   **Diff 视图**：选择两个 Run，对比其：
        *   任务列表差异 (PM_TASKS diff)。
        *   计划差异 (PLAN.md diff)。
        *   关键产物差异 (Result 状态)。
*   **技术实现**：
    *   后端：确保 `state/runs/` 下归档结构清晰。
    *   前端：读取 `state/runs/` 目录列表，解析各次 `DIRECTOR_RESULT.json` 生成摘要。

---

## 第三阶段：无人值守的韧性 (Robustness)
**目标**：减少人工干预频率，让系统学会自己“爬起来”。

### 3.1 失败自动恢复策略 (Auto-Recovery)
*   **功能描述**：
    *   **自动重试**：PM/Director 内部增加 Retry 装饰器，对网络抖动/临时 API 错误自动重试 N 次。
    *   **自动降级**：
        *   若 Director 连续 QA 失败 > 3 次，自动降级为“仅输出建议 (Plan Only)”模式，不修改代码。
        *   若 Codex 后端连续超时，自动切换为 Ollama (需配置备用模型)。
*   **技术实现**：
    *   后端：在 `director_exec.py` 和 `codex_utils.py` 中植入熔断与降级逻辑。
    *   配置：在 `policy.json` 中增加 `recovery` 字段配置策略。

### 3.2 任务审批/冻结机制 (Safety Freeze) - 可选
*   **功能描述**：
    *   全局“只读模式 (Read-Only Mode)”开关。开启后，所有写操作（文件修改、命令执行）自动被拦截并转入“人工介入中心”待批。
*   **技术实现**：
    *   后端：`io_utils.py` 写操作前检查 Global Lock 状态。

---

## 实施路线图 (Roadmap)

1.  **立即执行 (Now)**:
    *   设计 `INTERVENTIONS.json` 数据结构。
    *   实现 Dashboard 的“人工介入中心”UI 原型。
    *   完善依赖管理 (`requirements.txt`)，作为“介入中心”的第一个监控项。

2.  **近期 (Next)**:
    *   实现日志全文检索功能。
    *   开发“恢复上次运行”的 CLI 参数与前端对接。

3.  **后续 (Later)**:
    *   运行历史对比视图。
    *   自动降级与熔断策略的后端实现。

请确认此计划，我们将从 **第一阶段：统一介入中心与依赖管理** 开始落地。
