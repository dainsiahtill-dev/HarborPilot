# HarborPilot Agent 文档中心

此目录面向 **AI Agent / 自动化执行器**，强调可执行约束、证据链与可回放性。

---

## 📚 文档索引

### 🎯 产品与需求

| 文档 | 说明 | 读者 |
| --- | --- | --- |
| [产品说明书](../product/product_spec.md) | 产品定位、优势、适用场景 | Agent / PM |
| [需求文档](../product/requirements.md) | 需求定义与验收基线 | Agent / 开发者 |

### 🏗️ 系统与工程

| 文档 | 说明 | 读者 |
| --- | --- | --- |
| [架构文档](architecture.md) | 状态机、事件模型、数据流、Context Engine | 工程师 |
| [不变量宪法](invariants.md) | 核心 8 条约束（不可破坏） | 工程师 |
| [参考手册](reference.md) | CLI、工具、事件类型、产物索引 | 开发者 |
| [拟人化设计](anthropomorphic_design.md) | Memory/Reflection/Persona/Glass Mind | 工程师 |
| [Context Engine v2 计划](context_engine_v2_plan.md) | 升级路线与落地阶段 | 工程师 |
| [Sniper Mode v2.0 计划](sniper_mode_v2_plan.md) | 上下文工程优化与成本感知路线图 | 工程师 |

---

## AI Agent Quick Context

- `.ai-agent/context.json` (machine-readable core context)
- `.ai-agent/project_context.md` (human-friendly overview)
- `.ai-agent/project_map.xml` (compressed navigation map)
- `.ai-agent/best_practices.md` (AI do/don't)
- `.ai-agent/templates/` (refactor / new_feature / bug_fix templates)

---

## 🔍 快速入口

- 项目总览：[`../../README.md`](../../README.md)
- 文档入口：[`../README.md`](../README.md)
- AI agent context：`.ai-agent/context.json`
- Context Engine v2：[`architecture.md#3-上下文引擎-context-engine-v2`](architecture.md#3-上下文引擎-context-engine-v2)

---

## 🧭 Agent 核心约束速查

- **合同不可变**：`PM_TASKS.json` 的 goal/AC 只能追加证据
- **事实流 Append-Only**：`events.jsonl` 只追加，不回写
- **Run ID 全局唯一**：所有产物/引用必须携带 run_id
- **UI Read-Only**：运行态 UI 不写入任务/代码
- **可回放**：仅依赖 events + trajectory + artifacts paths
- **失败可定位（3 Hops）**：Phase → Evidence → Tool Output
- **原子写入**：关键状态文件 write tmp → fsync → rename
- **记忆必须可溯源**：memory/reflection 必须带 refs

---

## 📝 文档更新日志

| 日期       | 更新内容 |
| ---------- | -------- |
| 2026-02-02 | 重构为人类/Agent 双入口文档结构 |
