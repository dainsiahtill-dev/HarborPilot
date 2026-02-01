# HarborPilot 参考手册

本文档提供 HarborPilot 的目录结构、CLI 参数、工具清单及产物索引的详细参考。

---

## 1. 目录结构

```text
harborpilot/
  backend/                       # Python 后端
    app/                         # FastAPI 应用
      routers/                   # API 路由
      services/                  # 业务逻辑服务
      config.py                  # 配置管理
      main.py                    # FastAPI 入口
    core/harborpilot_loop/       # 核心循环模块
      io_utils.py                # IO / 记忆 / Dialogue
      prompts.py                 # Prompt 组装
      prompt_loader.py           # 模板加载
      decision.py                # 任务决策逻辑
      codex_utils.py             # Codex 后端适配
      ollama_utils.py            # Ollama 后端适配
      director_exec.py           # Director 执行引擎
      director_tooling.py        # 工具调用层
      director_memory.py         # 记忆管理
      policy.py                  # 策略配置
      shared.py                  # 公共工具
    server.py                    # 后端服务器入口
  frontend/                      # React 前端 (Vite + TailwindCSS)
    src/app/                     # 应用代码
      components/                # UI 组件
      App.tsx                    # 主应用组件
    src/styles/                  # 样式文件
  electron/                      # Electron 桌面应用
    main.cjs                     # 主进程入口
    preload.cjs                  # 预加载脚本
  tools/                         # 代码分析工具
    files.py                     # 文件操作工具
    search.py                    # 搜索工具 (ripgrep)
    linters.py                   # Lint 工具
    treesitter.py                # Tree-sitter AST 操作
  prompts/                       # 提示词模板
    demo_ming_armada.json        # 默认角色模板
    generic.json                 # 通用模板
  schema/                        # JSON Schema 定义
  tests/                         # 测试套件
    e2e/                         # 端到端测试
  .harborpilot/runtime/          # 默认产物目录 (推荐指向 RAMDISK)
    memos/                       # 备忘录归档
    evidence/                    # 取证数据
    runs/                        # 历史运行归档
```

---

## 2. 运行产物索引

所有产物默认位于 `workspace/.harborpilot/runtime/` 下：

| 文件名 | 说明 | 消费者 |
| :--- | :--- | :--- |
| `PM_TASKS.json` | 任务合约，PM 生成的任务包 | Director |
| `PM_STATE.json` | PM 内部状态 (连败/阻碍计数) | PM Loop |
| `PM_REPORT.md` | PM 的思考与输出日志 | Dashboard |
| `PLAN.md` | 总体计划草案 | PM / Humans |
| `DIRECTOR_RESULT.json` | Director 执行结果摘要 | PM / Dashboard |
| `RUNLOG.md` | Director 详细执行日志 | Dashboard |
| `QA_RESPONSE.md` | QA 测试结果 | Director / PM |
| `REVIEW_RESPONSE.md` | Reviewer 评审意见 | Director |
| `DIALOGUE.jsonl` | 对话事件流 (Narrative) | Dashboard |
| `events.jsonl` | 原子事件流 (Action/Observation) | Replay / Eval |
| `trajectory.json` | 轨迹索引 | Analysis |
| `memory/last_state.json` | 工作记忆快照 | PM / Director |
| `GAP_REPORT.md` | Gap Review 差异分析报告 | PM |
| `memos/PM_MEMO-*.md` | 任务备忘录 | Humans / Search |

### 2.0 存储位置规则（Workspace vs RAMDISK）

当启用 `HARBORPILOT_STATE_TO_RAMDISK=1` 时，系统会把**高频/热数据**写入 RAMDISK 缓存目录
`X:\.harborpilot\cache\<hash>\`，而**长期/冷数据**仍写在 workspace 下的 `.harborpilot/`。

**写入 workspace/.harborpilot/**（长期保存）

| 目录/文件 | 说明 |
| :--- | :--- |
| `.harborpilot/WORKSPACE_STATUS.json` | 工作区状态（如需要初始化 docs） |
| `.harborpilot/runtime/PLAN.md` | 规划草案 |
| `.harborpilot/runtime/PM_TASKS.json` | PM 任务合同 |
| `.harborpilot/runtime/PM_REPORT.md` | PM 报告 |
| `.harborpilot/runtime/PM_STATE.json` | PM 内部状态 |
| `.harborpilot/runtime/PM_TASK_HISTORY.jsonl` | 任务历史 |
| `.harborpilot/runtime/PLANNER_RESPONSE.md` | Planner 输出 |
| `.harborpilot/runtime/OLLAMA_RESPONSE.md` | LLM 输出 |
| `.harborpilot/runtime/QA_RESPONSE.md` | QA 输出 |
| `.harborpilot/runtime/DIRECTOR_RESULT.json` | Director 结果摘要（也会被当作热数据缓存） |
| `.harborpilot/runtime/DIRECTOR_STATUS.json` | Director 状态（也会被当作热数据缓存） |
| `.harborpilot/runtime/DIALOGUE.jsonl` | 对话记录（也会被当作热数据缓存） |
| `.harborpilot/runtime/PM_SUBPROCESS.log` | PM 子进程日志（也会被当作热数据缓存） |
| `.harborpilot/runtime/DIRECTOR_SUBPROCESS.log` | Director 子进程日志（也会被当作热数据缓存） |
| `.harborpilot/runtime/memos/**` | 备忘录与索引 |

**优先写入 RAMDISK**（启用后走 `X:\.harborpilot\cache\<hash>\`）

| 目录/文件 | 说明 |
| :--- | :--- |
| `.harborpilot/runtime/runs/**` | 每次运行的归档产物 |
| `.harborpilot/runtime/memory/**` | 记忆快照 |
| `.harborpilot/runtime/evidence/**` | 证据包 |
| `.harborpilot/runtime/trajectory.json` | 轨迹索引 |
| `*.jsonl` / `*.log` | 高速追加日志 |
| `RUNLOG.md` | Director 运行日志 |

### 2.1 结果文件详解 (DIRECTOR_RESULT.json)

`DIRECTOR_RESULT.json` 是 Director 执行完毕后的核心产物，供 PM 和 Dashboard 消费。

**主要字段:**

*   `schema_version`: 数据结构版本 (e.g., 1)。
*   `status`: 执行状态 (`success`, `fail`, `blocked`)。
*   `failure_code`: 失败原因分类码。
    *   `QA_FAIL`: 所有的测试或验证未通过。
    *   `RISK_BLOCKED`: 风险评分过高，触发阻断阈值。
*   `POLICY_BLOCKED`: 违反了安全策略。
    *   `TOOL_BUDGET_EXCEEDED`: 工具调用次数或行数超出预算。
    *   `PLANNER_FAILURE`: 无法生成有效计划。
*   `patch_risk`: 代码变更风险评估。
    *   `score`: 风险总分。
    *   `factors`: 
        *   `files_changed_count`: 变更文件数。
        *   `lines_added` / `lines_removed`: 代码行增删数。
        *   `touches_build_system`: 是否修改构建配置 (package.json 等)。
        *   `touches_security_sensitive`: 是否修改敏感模块 (auth/crypto)。
        *   `touches_runtime_entry`: 是否修改入口文件 (main.py 等)。

---

## 3. CLI 参数详解

### 3.1 PM Loop (`backend/scripts/loop-pm.py`)

| 参数 | 说明 | 默认值 |
| :--- | :--- | :--- |
| `--workspace` | **[必填]** 目标仓库路径 (缺少 `docs/` 会进入初始化流程) | - |
| `--pm-backend` | 后端选择: `codex` \| `ollama` | `codex` |
| `--requirements-path` | 需求文档路径 | `docs/product/requirements.md` |
| `--run-director` | 是否自动拉起 Director | `False` |
| `--director-iterations` | 自动拉起 Director 的尝试次数 | `1` |
| `--director-match-mode` | 结果匹配模式: `latest`\|`run_id`\|`any`\|`strict` | `latest` |
| `--loop` | 启用循环模式 | `False` |
| `--interval` | 循环间隔 (秒) | `0` |
| `--stop-on-failure` | 遇到失败是否停止 | `False` |

### 3.2 Director Loop (`backend/scripts/loop-director.py`)

| 参数 | 说明 | 默认值 |
| :--- | :--- | :--- |
| `--workspace` | **[必填]** 目标仓库路径 | - |
| `--model` | Ollama 模型名称 | (内置默认) |
| `--iterations` | 运行轮数 | `1` |
| `--memory-backend` | 记忆后端: `lancedb`\|`file`\|`none` | `lancedb` |
| `--auto-repair` | 启用 QA 失败自动修复 | `False` |
| `--repair-rounds` | 自动修复尝试次数 | `3` |
| `--rollback-on-fail` | 失败是否回滚代码 | `False` |
| `--reviewer` | 启用代码评审 | `False` |
| `--gap-review` | 启用 Gap Review (差异扫描) | `False` |
| `--risk-block-threshold` | 风险阻断阈值 (0为关闭) | `0` |
| `--run-npm` | 允许运行 npm 命令 | `False` |
| `--npm-timeout` | npm/tool 子进程超时 (秒；0 为不设超时) | `600` |
| `--default-tools` | 启用默认 QA 工具链 (ruff/mypy/pytest) | `True` |

---

## 4. 工具清单 (Tools)

HarborPilot 内置了 `tools.py` 统一入口。

### 4.1 代码分析与操作 (Repo-IO)

*   `repo_tree`: 生成目录树 (支持 depth)
*   `repo_rg`: 代码搜索 (ripgrep 封装)
*   `repo_read_around`: 读取指定行周围代码
*   `repo_read_slice`: 读取指定范围代码
*   `repo_diff`: 查看 git diff

### 4.2 结构化编辑 (Tree-sitter)

*   `treesitter_find_symbol`: 定位符号 (Class/Function)
*   `treesitter_replace_node`: 替换 AST 节点
*   `treesitter_insert_method`: 插入方法
*   `treesitter_rename_symbol`: 符号重命名

### 4.3 质量与测试

*   `ruff_check` / `ruff_format`: Python Lint & Format
*   `mypy`: Python 类型检查
*   `pytest`: 运行测试
*   `coverage_run` / `coverage_report`: 覆盖率分析
*   `jsonschema_validate`: JSON 校验
*   `pydantic_validate`: Pydantic 模型校验

### 4.4 索引与 RAG

*   `repo_symbols_index`: 生成符号索引
*   `repo_import_graph`: 生成依赖图
*   `lancedb_index_code`: 向量化代码索引
*   `lancedb_query_code`: 语义搜索代码

---

## 5. 环境变量 (Env Vars)

| 变量 | 说明 |
| :--- | :--- |
| `HARBORPILOT_STATE_TO_RAMDISK` | 设为 `1` 强制将 `.harborpilot/` 指向内存盘 (X:\) |
| `HARBORPILOT_PM_BACKEND` | 默认 PM 后端 (`codex`\|`ollama`) |
| `HARBORPILOT_DIRECTOR_MODEL` | 默认 Director 模型 |

---

## 6. RAMDISK 机制 (FAQ)

### 为什么 RAMDISK 不回落 (Fallback)？
HarborPilot 强制要求配置了 `HARBORPILOT_STATE_TO_RAMDISK` 的环境必须存在有效的 RAMDISK 路径。如果路径不存在，系统会直接报错退出，而不是回落到磁盘。
原因：
1.  **避免路径污染**：混合使用内存盘和机械盘会导致状态文件分散，增加调试和日志收集的难度。
2.  **性能一致性**：回落到磁盘会显著降低高频 I/O 的性能，导致 Director 运行节奏不可预测。
3.  **明确预期**：强约束迫使开发者在启动前配置好环境，避免隐性配置错误。

**检测命令：**
```bash
python -c "import os; print('OK' if os.path.exists('X:\\') else 'MISSING')"
```

---

## 7. 匹配模式 (Match Mode)

PM Loop 通过 `--director-match-mode` 参数控制如何寻找 Director 的产物：

*   **`latest` (默认)**: 读取 `.harborpilot/runtime/runs/latest` 软链或指针，始终获取最近一次运行的结果。适合单机串行模式。
*   **`run_id`**: 必须匹配当前 PM 分配的 `run_id`。适合严格的流水线集成。
*   **`any`**: 只要有任何 `DIRECTOR_RESULT.json` 就读取。适合调试或松散耦合。
*   **`strict`**: 类似 `run_id`，但如果未找到会抛出错误而不是等待。

---

## 8. Policy 来源示例

Director 运行时会合并多层配置（Default < Config File < Task Override < CLI）。`policy_sources` 字段记录了每个配置项的最终来源，便于追踪：

```json
{
  "repair.auto_repair": "cli",           // 命令行覆盖
  "risk.block_threshold": "file",        // 配置文件定义
  "evidence.verbosity": "default",       // 系统默认值
  "qa.enabled": "task"                   // PM 任务特定覆盖
}
```
