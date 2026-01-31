# HarborPilot 架构文档

本文档面向工程师与核心开发者，详细说明 HarborPilot 的内部工作流、状态机、事件模型与并发约束。

---

## 1. 核心状态机 (Loop State Machines)

HarborPilot 分为两个独立的循环：**PM Loop** (规划与决策) 和 **Director Loop** (执行与验证)。

### 1.1 PM Loop (规划循环)

PM Loop 负责生成高阶任务并决策是否继续。

**流程：**
1.  **读取上下文**：加载 requirements / plan / gap report / QA history / memory snapshot。
2.  **生成任务 (PM_TASKS)**：产出结构化任务包 `PM_TASKS.json`，这是 PM 与 Director 的唯一“合同”。
3.  **Handoff**：写入对话事件 (handoff)，标志着控制权移交。
4.  **拉起 Director** (可选)：通过子进程调用 Director 执行任务。
5.  **评审与决策**：
    *   读取 Director 返回的 `DIRECTOR_RESULT.json`。
    *   进行追问或评价。
    *   决策下一步：继续 (CONTINUE) / 结束 (FINISH) / 失败 (FAIL)。
6.  **归档**：生成 Memo 并更新索引。

**关键文件：**
*   `PM_TASKS.json`: 任务合同 (输入)
*   `PM_STATE.json`: 内部状态 (连败计数、阻碍计数等)

### 1.2 Director Loop (执行循环)

Director Loop 负责将 PM 的任务转化为具体代码变更，并保证质量。

**流程：**
1.  **初始化**：读取 `PM_TASKS.json`。
2.  **Tool Planner (取证)**：
    *   分析任务，决定需要读取哪些文件或搜索哪些符号。
    *   调用 `repo_*` 工具获取代码切片。
3.  **Patch Planner (计划)**：
    *   基于任务和证据，生成具体的执行计划 (tool_commands)。
4.  **Execution (执行)**：
    *   执行文件修改、命令运行。
    *   实时流式输出日志。
5.  **Reviewer (评审 - 可选)**：
    *   对改动进行自我评审，必要时回修。
6.  **QA (复核)**：
    *   运行测试 (pytest/npm test) 或验证脚本。
    *   生成 `QA_RESPONSE.md`。
7.  **结果汇总**：生成 `DIRECTOR_RESULT.json`，包含执行状态、消耗、风险评分等。

**多角色模拟：**
Director 在单次提示词中模拟多角色视角 (Creative Director, Designer, Engineer)，而非多进程协作。角色配置见 `prompts/*.json`。

---

## 2. 事件流与数据模型 (Event Streams)

HarborPilot 采用“事实源 + 投影层”的设计模式。

### 2.1 事实源 (Truth Sources)

*   **`events.jsonl` (Action/Observation Stream)**
    *   记录机器可读的原子操作：工具调用、文件读写、QA 结果。
    *   用途：回放 (Replay)、评测 (Eval)、轨迹分析 (Trajectory)。
    *   **Schema**:
        *   `kind`: `action` | `observation`
        *   `actor`: `Tooling` | `Director` | `QA` | `Reviewer` | `System`
        *   `name`: 工具名 (e.g., `repo_rg`, `apply_patch`)
        *   `refs`: `{ "run_id": "...", "task_id": "...", "phase": "..." }`
        *   `observation`: 
            *   `ok`: boolean
            *   `output`: 结果数据
            *   `duration_ms`: 执行耗时 (ms)
            *   `truncated`: 是否截断
            *   `artifacts`: 产生的副产物 (如报告文件路径)

*   **`DIRECTOR_RESULT.json`**
    *   单次运行的最终结果摘要。
    *   **关键字段**:
        *   `schema_version`: 版本号 (int)
        *   `status`: `success` | `fail` | `blocked`
        *   `failure_code`: 失败分类码 (e.g., `QA_FAIL`, `RISK_BLOCKED`, `TOOL_TIMEOUT`)
        *   `patch_risk`:
            *   `score`: 总分
            *   `factors`: 风险因子 (files_changed_count, lines_added, touches_auth, etc.)

### 2.2 解释层 (Interpretation Layer)

*   **`DIALOGUE.jsonl` (Narrative Stream)**
    *   记录拟人化的对话过程：PM 分配任务、Director 汇报结果、QA 报告。
    *   用途：Dashboard 展示、人类阅读。
    *   **Fields**: `timestamp`, `speaker`, `type` (handoff/receipt/say/done), `content`.

*   **`RUNLOG.md`**
    *   详细的文本日志流。

### 2.3 轨迹 (Trajectory)

*   **`trajectory.json`**
    *   将 Events、Artifacts 和 Context 串联起来的索引文件。
    *   指向 events.jsonl 中的 seq 范围。

---

## 3. Policy 策略与配置合并

Director 的行为由 Policy 严格控制，支持多层级合并。

**合并优先级 (高 -> 低):**
1.  **CLI 参数**: `--risk-block-threshold 0`
2.  **Task Overrides**: `PM_TASKS.json` 中的 `policy_overrides` 字段
3.  **Policy 文件**: `.harborpilot/runtime/director_policy.json`
4.  **环境变量**: `HARBORPILOT_...`
5.  **代码默认值**

**Policy 示例:**
```json
{
  "repair": { "max_attempts": 2 },
  "risk": { "block_threshold": 6 },
  "memory": {
    "enabled": true,
    "backend": "lancedb",
    "store_every": 1
  }
}
```

**生效记录:**
`DIRECTOR_RESULT.json` 中包含 `policy_effective` (最终生效配置) 和 `policy_sources` (来源追踪)。

---

## 4. 并发与原子性约束

### 4.1 写入约束
*   **Workspace 隔离**: 推荐将 `.harborpilot/` 目录指向 RAMDISK，避免污染项目源码。
*   **原子写入**: 关键状态文件 (如 `PM_TASKS.json`, `last_state.json`) 应尽量采用原子替换 (写临时文件 -> rename) 方式，防止读取到截断内容。
*   **Dashboard 只读**: Dashboard 仅读取 `.harborpilot/` 下的文件进行展示，**绝不** 直接修改任务或代码，确保“展示面”与“控制面”分离。

## 5. Smart 视图解析架构 (Dashboard)

Dashboard 采用 **流式解析器 (Streaming Parser)** 将非结构化日志转化为结构化事件树。

**解析原理:**
*   **哨兵行 (Sentinels)**: 利用 `OpenAI Codex v...`, `user`/`exec`, `mcp:`, `--------` 等固定特征行作为状态切换锚点。
*   **状态机**: 维护 `mode` (idle/user/thinking/exec) 和 `lifecycle` (open/closed)。
*   **增量渲染**:
    *   **Open**: 遇到块开始 (如 `{`), 创建 `status: open` 卡片，UI 显示 loading。
    *   **Update**: 后续行追加到 buffer，实时更新 UI (如表格行增加)。
    *   **Close**: 遇到块结束或新哨兵，标记 `status: closed`。

**处理细节:**
*   **JSON**: 括号计数 (brace counting)，归零后 Parse。
*   **表格**: 识别 PowerShell `Get-ChildItem` 表头，按列宽切分。
*   **ANSI**: 默认 Strip ANSI 以保证结构化展示清晰度。

---

## 6. 设计哲学

*   **Reality-Driven**: 基于真实成本和资源设计，而非理想模型。
*   **Tool-Augmented**: 用工具链 (Lint/Test/RAG) 补足弱模型 (Local LLM) 的短板。
*   **Memory-over-IO**: 优先使用内存缓存 (Repo Index)，减少磁盘 IO。
*   **Control/Execute Separation**: PM 定义合约，Director 执行合约，Dashboard 旁路观测。
