# HarborPilot 3-Hops 失败定位实现说明（本次改动）

> 更新时间：2026-02-07
> 目标：把“失败 3 跳定位（Phase → Evidence → Tool Output）”从理念落地为可验证、可回放、可查询的工程能力。

---

## 1. 设计目标

- **可定位**：失败时必须给出 Hop1/2/3 的结构化链路。
- **可回放**：链路依赖 `run_id + events + artifacts`，无需隐式内存。
- **可审计**：失败链路落盘为独立产物，支持 API 读取与哨兵校验。
- **低侵入**：尽量复用现有 `events.jsonl`、`DIRECTOR_RESULT.json`、`trajectory.json`。

---

## 2. 本次代码改动总览

### 2.1 新增模块

1) `backend/core/harborpilot_loop/failure_hops.py`

- 新增 `build_failure_hops(...)`：
  - 在 `event_seq_start~event_seq_end` 区间内，按 `run_id` 收集事件。
  - 自动识别失败观察事件（`ok=false` / `error` / `output.ok=false`）。
  - 构建 3 hops 结构：
    - **Hop1（Phase）**：失败阶段、事件序号、actor/name/summary
    - **Hop2（Evidence）**：`task_id/task_fingerprint/run_id/phase/files/related_action_seq`
    - **Hop3（Tool Output）**：优先原始输出文件路径，否则回退到事件中的错误输出
- 新增 `write_failure_index(run_dir, payload)`：
  - 把结果写入 `failure_hops.json`（原子写）。

### 2.2 Tool 输出持久化增强（Hop3 数据源）

2) `backend/core/harborpilot_loop/director_tooling.py`

- 新增 `_persist_tool_raw_output(...)`：
  - 将工具执行 stdout/stderr/error 写入：
    - `.harborpilot/runtime/artifacts/runs/<run_id>/tool_output/*.stdout.log`
    - `.harborpilot/runtime/artifacts/runs/<run_id>/tool_output/*.stderr.log`
    - `.harborpilot/runtime/artifacts/runs/<run_id>/tool_output/*.error.log`
- 在工具正常返回、超时、异常分支中都记录路径。
- 将路径写入 `output` 与 `meta.raw_output_paths`，供 Hop3 优先引用。

### 2.3 Director 结果与轨迹接入

3) `backend/scripts/loop-director.py`

- `write_director_result(...)` 增强：若未提供 `failure_hops`，自动基于当前 run 计算并补齐。
- `build_result(...)` 增加 `event_seq_start/event_seq_end` 字段，保证计算边界稳定。
- 主流程在最终汇总阶段显式生成并落盘：
  - `failure_hops`
  - `failure_hops_path`
  - `failure_hops_ready`

4) `backend/core/harborpilot_loop/director_trajectory.py`

- 在 `artifacts` 中新增 `failure_hops_path`，形成从 trajectory 到失败索引的跳转能力。

### 2.4 Sentinel 约束增强

5) `backend/core/harborpilot_loop/invariant_sentinel.py`

- 新增 `_check_failure_hops_ready(director_result_path)`：
  - 当 `DIRECTOR_RESULT` 为 fail/blocked（或 `acceptance=false`）时，要求 `failure_hops_ready=true`。
  - 缺失时产出 violation code：`FAILURE_3HOPS_MISSING`。
- `run_invariant_sentinel(...)` 新增参数 `director_result_path` 并接入检查。

6) `backend/scripts/loop-director.py` 与 `backend/scripts/loop-pm.py`

- 调用哨兵时新增传参 `director_result_path=...`，确保运行期生效。

### 2.5 API 查询能力

7) `backend/app/routers/director.py`

- 新增接口：`GET /director/failure/{run_id}`
  - 校验 `run_id` 格式。
  - 读取 `.harborpilot/runtime/artifacts/runs/{run_id}/failure_hops.json`。
  - 返回 `failure_hops` 内容（附 `failure_hops_path`）。

---

## 3. 产物与数据流（统一真相源）

### 3.1 关键产物

- `events.jsonl`：事实流（Action/Observation）
- `DIRECTOR_RESULT.json`：执行结论与摘要
- `trajectory.json`：索引与回放入口
- `failure_hops.json`：失败 3-hop 专用结构化索引
- `tool_output/*.log`：Hop3 原始输出证据

### 3.2 失败定位闭环

1. 工具执行产生 observation 事件（失败标记 + 输出路径）
2. Director 汇总时构建 `failure_hops`
3. `failure_hops.json` 落盘并写入 `DIRECTOR_RESULT/trajectory`
4. Sentinel 对失败结果强制校验 `failure_hops_ready`
5. API 提供按 `run_id` 查询

---

## 4. 测试与验证

### 4.1 新增测试

- `backend/tests/test_failure_hops.py`
  - 覆盖：
    1. 有原始输出路径时，Hop3 使用 artifact paths
    2. 无原始文件时，Hop3 回退事件错误输出
    3. 成功 run 不应产生失败 hops

### 4.2 扩展测试

- `backend/tests/test_invariant_sentinel.py`
  - 增加失败结果缺少 `failure_hops_ready` 的违规检测用例。
  - 兼容新增参数 `director_result_path`。

### 4.3 已执行验证命令

- `pytest backend/tests/test_failure_hops.py backend/tests/test_invariant_sentinel.py -q`
- `pytest backend/tests/test_director_logic.py backend/tests/test_context_engine.py -q`
- 合并回归：
  - `pytest backend/tests/test_failure_hops.py backend/tests/test_invariant_sentinel.py backend/tests/test_director_logic.py backend/tests/test_context_engine.py -q`

结果：**18 passed**。

---

## 5. 兼容性与注意事项

- 已遵循 UTF-8 显式读写（文本 I/O 全部使用 `encoding="utf-8"`）。
- 旧 run 无 `failure_hops.json` 时，`/director/failure/{run_id}` 将返回 404。
- 本次改动不改变现有事件 schema 主结构，仅新增结果字段与附加产物。

---

## 6. 下一步建议（可选）

- 前端新增 Failure Explorer 面板：按 run_id 展示 Hop1/2/3。
- 将 `failure_hops` 纳入 dashboard snapshot 聚合字段。
- 为 `failure_hops.json` 补充 JSON Schema，接入自动校验。
- 为 tool_output 加大小上限与归档策略，控制长跑磁盘增长。

