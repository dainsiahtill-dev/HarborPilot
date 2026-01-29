# HarborPilot

HarborPilot 是一套“**PM 规划 → Director 执行 → QA 校验 → Dashboard 可视化**”的自动化脚本项目。  
默认 **PM 用 Codex（更聪明）**，**Director 用本地 Ollama（更省成本）**，并支持多 profile 的提示词模板化管理。

---

## 1. 总体能力一览

- **PM Loop（任务生成）**
  - 读取 requirements / plan / 记忆快照 / 上轮结果
  - 产出结构化任务包 `PM_TASKS.json`
  - 记录对话事件（handoff）
- **Director Loop（执行与 QA）**
  - 接收 PM 任务 → Planner 计划 → 执行变更 → QA 复核
  - 产出 `DIRECTOR_RESULT.json`、`QA_RESPONSE.md`
  - 可选 “Gap Review” 扫描 `docs/` 与代码库存差距
- **Memory（记忆）**
  - `last_state.json`：工作记忆快照（摘要/下一步）
  - 推荐：memory.store_every = 3 或 memory.store_on_accept = true
  - RAG 建议 topk <= 5，且仅在 UNKNOWN/LOCATED 阶段查询一次
  - 支持 **LanceDB** 持久记忆（默认 `--memory-backend lancedb`）
- **Dialogue（拟人化对话流）**
  - JSONL 事件流（支持顺序/去重/回放）
  - UI 可折叠查看（含 phase / task_id 关联）
- **Dashboard（可视化面板）**
  - 只读展示日志、对话、状态、运行文件
  - 一键启动/停止 PM 或 Director
- **Prompt 模板化**
  - 提示词 JSON 模板 + profile 切换
  - 默认 demo：`demo_ming_armada`

---

## 2. 默认后端与模型

- **PM：Codex CLI**
  - 默认 `--pm-backend codex`
  - 用于高智商任务拆分
- **Director：Ollama CLI**
  - 默认模型：`modelscope.cn/unsloth/Qwen3-Coder-30B-A3B-Instruct-GGUF:latest`
  - 用于执行和 QA

---

## 3. 目录结构

```
harborpilot/
  loops/
    loop-pm.py
    loop-director.py
  modules/harborpilot-loop/
    io_utils.py          # 路径解析 / IO / 记忆 / Dialogue / 工具检查
    prompts.py           # Prompt 组装、文件上下文提取
    prompt_loader.py     # JSON 模板加载与渲染
    decision.py          # PM/Director 任务选择逻辑
    ports.py             # 端口检测与策略
    codex_utils.py       # Codex CLI 调用
    ollama_utils.py      # Ollama CLI 调用
    shared.py            # 公共工具（文本处理等）
  ui/
    pm-dashboard.py
  prompts/
    demo_ming_armada.json
    generic.json
  state/ollama/
    # 默认运行产物（写入 workspace）
```

---

## 4. Workspace 规则

HarborPilot 的 **workspace 必须包含 `docs/`**。

### 默认行为
- **Dashboard**：从当前工作目录向上查找 `docs/`，作为默认 workspace。
- **CLI**：同样会向上查找 `docs/`；找不到会报错退出。

### 为什么必须有 docs/？
PM/Director 的提示词默认引用 `docs/`，Gap Review 也会扫描 `docs/` 生成大纲。

---

## 5. 运行方式（Dashboard + CLI）

### Dashboard（推荐）
```
python ui/pm-dashboard.py
```
可在界面中设置：
- Workspace
- PM Backend（codex/ollama）
- Model（Ollama 用）
- Prompt profile
- 各类超时/刷新间隔

### CLI 示例
```
# PM（默认 Codex）
python loops/loop-pm.py --workspace <REPO>

# PM 改用 Ollama（省成本）
python loops/loop-pm.py --workspace <REPO> --pm-backend ollama

# Director（默认 Ollama）
python loops/loop-director.py --workspace <REPO> --iterations 1
```

---

## 6. 运行产物（默认路径）

都写入 workspace 下的 `state/ollama/`：

- `PLAN.md`：计划草案
- `PM_TASKS.json`：PM 输出的任务合约
- `PM_REPORT.md`：PM 输出日志
- `DIRECTOR_RESULT.json`：Director 结果
- `QA_RESPONSE.md`：QA 复核结果
- `REVIEW_RESPONSE.md`：Reviewer 评审意见
- `DIALOGUE.jsonl`：对话事件流
- `events.jsonl`：Action/Observation 事件流
- `trajectory.json`：每轮轨迹资产（指向 events seq 范围 + 关键产物路径）
- `memory/last_state.json`：工作记忆快照
- `GAP_REPORT.md`：Gap Review 输出

---

## 7. Prompt 模板与 profile 切换

提示词模板在 `prompts/`，默认 profile 为 `demo_ming_armada`。

```
python loops/loop-pm.py --workspace <REPO> --prompt-profile generic
python loops/loop-director.py --workspace <REPO> --prompt-profile generic
```
或：
```
set HARBORPILOT_PROMPT_PROFILE=generic
```

---

## 8. PM Loop 关键流程

1. 读取：requirements / plan / gap / QA / 上轮任务 / memory  
2. 生成任务包：`PM_TASKS.json`  
3. 写入对话事件（handoff）  
4. （可选）拉起 Director 执行  

常用参数：
- `--pm-backend codex|ollama`
- `--requirements-path docs/product/requirements.md`
- `--run-director`（自动调 Director）

补充：
- `PM_TASKS` 可包含 `required_evidence`，用于强制 Director 先读指定文件/范围/符号（适合失败纠偏）。

---

## 9. Director Loop 关键流程

1. 读取任务包 `PM_TASKS.json`
2. Tool Planner 取证（repo_* 定位与切片）
3. Patch Planner 生成执行计划
4. 执行改动 → 写入 `OLLAMA_RESPONSE.md`
5. Reviewer 评审（可选）→ 写入 `REVIEW_RESPONSE.md`
6. QA 复核 → 写入 `QA_RESPONSE.md`
7. 生成 `DIRECTOR_RESULT.json`
8. 更新 `memory/last_state.json`

常用参数：
- `--model <ollama-model>`
- `--memory-backend lancedb|file|none`
- `--gap-review / --no-gap-review`
- `--gap-write-plan / --no-gap-write-plan`

---

## 10. Dialogue 事件结构

事实源/投影层规则：
- 事实源（回放/评测）：events.jsonl + DIRECTOR_RESULT.json
- 解释/叙事（给人看）：DIALOGUE.jsonl + RUNLOG.md
- 证据指针（可复核）：evidence/（默认 summary）

每条事件记录写入 `state/ollama/DIALOGUE.jsonl`，核心字段：
- `timestamp` / `ts_epoch`
- `seq`（单调递增）
- `event_id`（uuid）
- `speaker`（PM / Director / QA / System）
- `type`（handoff / receipt / say / done 等）
- `refs.task_id` / `refs.phase`

Dashboard 读取并排序显示，避免并发乱序。

---

## 11. Events 事件流（新增）

最小字段表（只看这几行就能用）：
- kind：action / observation
- actor：Tooling / Director / QA / Reviewer / System
- name：repo_rg / apply / pytest / rollback ...
- refs：run_id / task_id / phase
- observation：ok / output / truncation / duration_ms

事实流使用指南：
- 想知道这轮发生了什么 → 看 trajectory.json
- 想做统计/评测/回放 → 用 events.jsonl
- 想快速看最终结果 → 看 DIRECTOR_RESULT.json
- 想看拟人化过程 → 看 DIALOGUE.jsonl
- 想查为什么这么判定 → 看 evidence/ + policy_sources
- 想看详细执行细节 → 看 RUNLOG.md

用于“Action/Observation”标准化事件流，记录工具调用、读写、QA/Reviewer 等执行事实：
- 路径：`state/ollama/events.jsonl`
- 每条事件包含 `kind`（action/observation）、`actor`、`name`、`refs`（run/task/phase）
- Observation 会包含 `ok/output/truncation/duration_ms`

用途：回放、评测、上下文压缩、trajectory 打包。

---

## 12. 多角色协作说明（Director 侧）

Director 并不是多进程“真人协作”，而是**单次提示词中模拟多角色视角**。  
角色配置来自 `prompts/*.json` 的模板：
- `demo_ming_armada.json`：Creative Director / Producer、Game Designer、UI Designer、Game Engineer
- `generic.json`：通用角色组合

你可以在模板中替换为自己的团队结构（如产品经理/后端/前端/测试）。

---

## 13. 记忆系统说明

- `memory/last_state.json` 是 **工作记忆快照**，只应包含摘要/下一步  
  **不允许** 覆盖或篡改 PM 合同目标。  
- `--memory-backend lancedb` 会将长期记忆写入 LanceDB。

---

## 14. 依赖

必需：
- Python 3.10+
- **Codex CLI**（PM 默认）
- **Ollama CLI**（Director 默认）

可选：
- `flet`（Dashboard）
- `psutil`（端口检测更准确）
- `lancedb`（长期记忆）

---

## 15. 常见问题

**Q: 找不到 docs/？**  
A: CLI 会直接报错退出。请确认 workspace 根目录包含 `docs/`。

**Q: PM 太贵，能全部用 Ollama 吗？**  
A: 可以，直接加 `--pm-backend ollama`。

**Q: Director 要换模型？**  
A: `--model <ollama-model>` 即可覆盖默认模型。

---

## 16. 设计边界（重要）

- **控制面**：PM 定义任务合约（PM_TASKS）
- **执行面**：Director 严格执行合约
- **展示面**：Dashboard 只读，不参与决策

该边界确保系统稳定可维护。

---

## 17. PM 运行控制与状态文件（补充）

- **循环控制**：`--loop`、`--interval`、`--max-iterations`
- **错误/停止策略**：`--stop-on-failure`、`--max-failures`、`--max-blocked`、`--max-same-task`
- **停止旗标**：PM 监听 `state/ollama/PM_STOP.flag`，可由 Dashboard 按钮或手动创建停止循环
- **状态记录**：`PM_STATE.json` 里包含 `consecutive_failures` / `consecutive_blocked` / `same_task_count` / `force_switch`
- **日志**：`PM_LOG.jsonl`、`PM_TASK_HISTORY.jsonl`、`PM_LAST_RESPONSE.md`（Codex）
- **PM 拉起 Director**：`--run-director` + `--director-*` + `--director-result-timeout`

---

## 18. Director 高级能力（补充）

- **迭代控制**：`--iterations` / `--forever` / `--delay-seconds`
- **Auto Repair**：`--auto-repair` + `--repair-rounds`，QA 失败会按反馈自动重试
  - `--max-repair-attempts` 可作为 `--repair-rounds` 的别名
- **容错**：`--continue-on-error`（缺 brief / file list 时不中断主循环）
- **NPM 命令执行**：`--run-npm` / `--npm-timeout`
  - 只允许执行 `npm ...` 命令（其余会被过滤）
- **默认 QA 工具链**：`--default-tools` / `--no-default-tools`
  - 默认启用：ruff → mypy → pytest（当 Patch Planner 未给出 tool_commands 时）
- **Reviewer 评审（可选）**：`--reviewer` / `--no-reviewer`
  - `--reviewer-rounds` 控制评审反馈回修次数
  - `--reviewer-response-path` 指定评审输出文件
- **回滚策略**：`--rollback-on-fail` / `--no-rollback-on-fail`
  - QA 失败或重试前自动回滚到本轮基线，避免“越修越烂”
- **变更风险评分**：自动记录到 `DIRECTOR_RESULT.json` 的 `patch_risk`
- **风险门控**：`--risk-block-threshold`
  - 当 `patch_risk.score >= threshold` 时直接阻止执行（0 表示关闭）
- **取证包粒度**：`--evidence-verbosity summary|full`
  - RAG 建议 topk <= 5，且仅在 UNKNOWN/LOCATED 阶段查询一次
- **无 PM 任务时自动选目标**：`--auto-pick-target`
  - 从 `PLAN.md` 的 `Backlog A/B` 轮询选取
- **Gap Review 扩展**：
  - `--gap-review` / `--gap-max-headings` / `--gap-max-files`
    - 默认仅在 docs 变化或首次接入新 repo 时跑
- 成功率提升 ≥ 5%
  - 可将摘要写回 `PLAN.md`（标记在 `<!-- GAP_REPORT:BEGIN -->` 内）
- **路径自定义**：`--pm-task-path` / `--dialogue-path` / `--planner-response-path` 等
  - 事件流：`--events-path`（默认 `state/ollama/events.jsonl`）

---

## 18.1 Director Policy（新增）

默认 policy 文件路径：
`state/ollama/director_policy.json`

可用 CLI 覆盖：
`--policy-path <path>`

仓库内已提供一份起始模板（同路径，可直接修改）。

支持任务级覆盖（PM_TASKS.json）：
```
{
  "policy_overrides": {
    "repair": {"max_attempts": 2},
    "risk": {"block_threshold": 6}
  }
}
```
也可以放在具体 task 内：
  ```
  {"tasks":[{"policy_overrides": {...}}]}
  ```

  memory 相关配置（policy 内 `memory`）示例：
  ```
  {
    "memory": {
      "enabled": true,
      "backend": "lancedb",
      "store_enabled": true,
      "store_every": 1,
      "store_on_accept": false
    }
  }
  ```
  - `backend`: `lancedb|file|both|none`
  - `store_every`: N 轮写一次（用于降频写入）
  - `store_on_accept`: 仅在 QA 通过时写入

覆盖优先级（从高到低）：
1) CLI 参数  
2) PM_TASKS.json.policy_overrides  
3) policy 文件  
4) 环境变量  
5) 代码默认值

DIRECTOR_RESULT.json 会记录：
- `policy_effective`（合并后的最终 policy）
- `policy_sources`（每个字段的来源）

---

## 19. 端口策略与安全（补充）

- 监控端口：`3180/3181/3182/3183/6379`
- `--port-policy auto|switch|none`：
  - auto/switch 会尝试建议替代端口
  - 对 Physics 端口会输出 `PHYSICS_PORT` / `VITE_PHYSICS_WS` 建议
- `--kill-on-port-conflict`：必要时自动清理占用端口进程
- 提示词中会注入端口状态摘要，避免重复启动服务

---

## 20. 日志与归档（补充）

- Director 侧文件：
  - `PLANNER_RESPONSE.md` / `OLLAMA_RESPONSE.md` / `REVIEW_RESPONSE.md` / `RUNLOG.md`
- PM 每轮归档：
  - `state/ollama/runs/pm-00001/` 内自动归档本轮输出
- 取证包：
  - `state/ollama/evidence/EVIDENCE_<task_id>_<iter>.json`（ToolPlanner 取证摘要）
- Dashboard 支持对话流增量读取，并能在日志轮转时自动从头恢复

---

## 21. Prompt 渲染细节（补充）

- JSON 模板支持 `{{placeholder}}` 替换
- `plan_template` 会在 `PLAN.md` 不存在时自动生成

---

## 22. 工具清单（已安装）

详见 `工具清单.rm`，其中包含 ruff/pytest/coverage/mypy/pydantic/jsonschema/tree_sitter/tree_sitter_languages/rich 的用途与建议。

## 23. Tools CLI（新增）

已内置 `tools.py`，提供统一命令行入口，便于 Director/人类调用：
```
python tools.py list
python tools.py ruff_check -- .
python tools.py ruff_format -- .
python tools.py pytest -- -q
python tools.py coverage_run
python tools.py coverage_report
python tools.py mypy -- .
python tools.py jsonschema_validate -- schema.json data.json
python tools.py pydantic_validate -- module:ModelClass data.json
python tools.py treesitter_outline -- typescript path/to/file.ts
python tools.py treesitter_find_symbol -- python path/to/file.py MyClass
python tools.py treesitter_replace_node -- python path/to/file.py MyClass.my_method "..."
python tools.py pytest_target -- tests/test_api.py::test_case
python tools.py python_run -- scripts/repro.py --arg value
python tools.py node_run -- scripts/repro.mjs --arg value
python tools.py repo_symbols_index -- . --max-files 200
python tools.py repo_import_graph -- . --max-files 200
python tools.py repo_api_surface -- . --max-files 200
python tools.py lancedb_index_code -- . --max-files 200
python tools.py lancedb_query_code -- "query text"
python tools.py policy_validate -- state/ollama/director_policy.json
```
说明：`tools.py --json` 会把结构化 JSON 输出到 stdout（机器用），默认模式输出人类可读文本。
Director 自动化只消费 `--json` 输出，避免人类日志污染解析。

说明：该入口不会自动执行非注册工具；仅提供这些工具函数的统一调用包装。
此外，Director 的 Planner / QA 提示词中已包含 `tools.py` 的调用格式说明（见 prompts 模板）。
工具调用分两类：
- Tool Planner 阶段会自动调用 repo_* 工具用于定位与切片读取。
- 其他工具只有在 Planner/ Patch Planner 明确给出 `tool_commands` 时才会执行。
  - 若 Patch Planner 未给出 `tool_commands`，会自动执行默认 QA 工具链（可用 `--no-default-tools` 关闭）。

## 24. Repo-IO 工具（新增）

用于“先定位 → 再切片阅读”的高效信息获取：
```
python tools.py repo_tree -- . --depth 3
python tools.py repo_rg -- "pattern" -- path1 path2 --max 50
python tools.py repo_read_around -- path/to/file.py 120 80
python tools.py repo_read_slice -- path/to/file.py 980 1080
python tools.py repo_read_head -- path/to/file.py 60
python tools.py repo_read_tail -- path/to/file.py 60
python tools.py repo_diff -- --stat
```
说明：输出带行号，支持截断与路径限制，适合弱模型“先搜再读”。
Director 会在 Tool Planner 阶段自动运行 repo_* 工具，结果回喂 Patch Planner 再决定是否动手。
推荐流程：repo_tree → repo_rg → repo_read_around → (repo_read_head/tail) → 再动手。

## 25. Tree-sitter 结构化改写工具（新增）

用于“语法级别”修改，避免字符串误改：
```
python tools.py treesitter_find_symbol -- python path/to/file.py ClassName
python tools.py treesitter_replace_node -- python path/to/file.py ClassName.method "new body..."
python tools.py treesitter_insert_method -- python path/to/file.py ClassName "def new_method(...): ..."
python tools.py treesitter_rename_symbol -- python path/to/file.py OldName NewName
```
说明：先用 `treesitter_find_symbol` 定位范围，再进行替换/插入/重命名，稳定性明显高于纯字符串编辑。

## 26. Repo 索引 / 本地 RAG（新增）

用于更快定位入口、建立“代码知识库”：
```
python tools.py repo_symbols_index -- . --max-files 200
python tools.py repo_import_graph -- . --max-files 200
python tools.py repo_api_surface -- . --max-files 200
python tools.py lancedb_index_code -- . --max-files 200
python tools.py lancedb_query_code -- "where is parse_planner_payload?"
```
说明：
- `repo_*` 工具快速生成符号/依赖/公开 API 索引，适合弱模型“先收敛再阅读”。
- `lancedb_*` 是可选的本地 RAG 能力（依赖 `lancedb`），用于长期记忆或代码向量检索。


---


## 27. 设计哲学：面向现实架构（Reality-Driven Architecture）

本项目的架构决策由“真实资源 / 真实成本 / 真实约束”驱动，而不是由理想模型或未来假设驱动。

- 只在“高智商价值最高”的环节使用 Codex（PM 规划与决策），在“高频执行”环节使用本地 Ollama
- 用工具链 / 取证 / 回滚 / policy 去补足弱模型，而不是把执行也交给昂贵模型
- 用内存换 IO（repo 缓存、JSONL 批量 flush、增量 tail），因为内存充裕、磁盘 IO 成本更高
- 直接操作 workspace，而不是 Docker 隔离，因为可见性与迭代速度更重要
- 任何功能都必须能解释“为什么现在值得”，否则宁可不加

If a feature is rarely used, hard to reason about, or adds complexity without daily value, it does not belong here.

---

## 28. 现实约束清单（环境变化时可推翻的前提）

以下前提一旦变化，相关设计允许推翻并重构：

- **模型成本变化**：若 Codex 成本显著下降，可上调 PM/Director 的智能比例
- **硬件变化**：若内存受限（<16GB），内存换 IO 的策略需收缩
- **工作流变化**：若进入严格隔离/可重建环境（如 CI 沙盒），可考虑容器化运行时
- **团队变化**：若多人维护，需强化契约与测试，减少“个人可理解”的隐式规则
- **任务类型变化**：若不再是游戏/资产管线场景，需重估 gap review 与 prompt 模板结构

---

## 29. 停止加功能边界（避免系统失控）

当出现以下情况之一，新增功能应被拒绝或推迟：

- 该功能无法明确降低成本 / 提升成功率 / 降低返工
- 只能在“未来可能有用”，无法在当下被日常使用
- 引入后需要频繁手动维护或增加认知负担
- 无法通过事件流 / 轨迹 / policy 进行可观测或可回放
- 会破坏现有合同边界（PM_TASKS / DIRECTOR_RESULT / workspace）

新增功能至少满足一条定量门槛（建议）：
- 成功率提升 ≥ 5%
- 或平均修复轮数下降 ≥ 1
- 或 Codex token 消耗下降 ≥ 10%

这套边界的目的是保证系统长期可维护、可解释、可迭代。
