<div align="center">

# 🚢 HarborPilot

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Status](https://img.shields.io/badge/Status-Active-brightgreen.svg)]()

**单人 · 本地优先 · 固定成本优先 · 无人值守自动化编程指挥台**

PM 规划 → Director 执行 → QA 校验 → Dashboard 可视化（Mission Control）

---

HarborPilot 的核心不是"更花哨的 Agent"，而是**面向现实**：

以 **本地推理（电费）** + **包月/订阅 CLI（固定成本）** 为主，

构建一个**可控、可追溯、可回放、可长期长跑**的个人软件工厂。

</div>

---

## 📌 目录

- [🎯 项目定位](#-项目定位)
- [✨ 独特优势与特色](#-独特优势与特色)
- [✅ 已有功能一览](#-已有功能一览)
- [🚀 快速开始](#-快速开始)
- [🏗️ 系统架构](#️-系统架构)
- [📁 产物与目录结构](#-产物与目录结构)
- [⚖️ 六条系统不变量](#️-六条系统不变量)
- [🧠 拟人化核心与 Glass Mind](#-拟人化核心与-glass-mind)
- [🎛️ 模型路由与接入验证](#️-模型路由与接入验证)
- [📊 用量与成本观测](#-用量与成本观测)
- [🗣️ Inner Voice（自言自语）](#️-inner-voice自言自语)
- [🆚 与行业工具的差异](#-与行业工具的差异)
- [🗺️ Roadmap：工具 × 游戏](#️-roadmap工具--游戏)
- [📚 文档](#-文档)
- [🤝 贡献与许可](#-贡献与许可)

---

## 🎯 项目定位

HarborPilot 是一款**单人工具**：

- 既是 **无人值守自动化编程工具**（可长期跑、可回放、可定位）
- 也将演进为一款 **"经营 + 叙事"的游戏化指挥台**（基于拟人化核心延展）

### 成本哲学（Reality-first）

| 通道           | 说明                      | 边际成本                       |
| -------------- | ------------------------- | ------------------------------ |
| 🖥️ **LOCAL**   | 本地模型（Ollama 等）     | ≈ 电费                         |
| 📦 **FIXED**   | 订阅/包月 CLI（Codex 等） | 固定成本，适合长跑             |
| 💳 **METERED** | 标准化 HTTPS API          | 受控"紧急通道"，**默认强门禁** |

---

## ✨ 独特优势与特色

### 1️⃣ 双循环 + 合同机制：把 Agent 变成"可管理的工程协作"

| 循环              | 职责                                          |
| ----------------- | --------------------------------------------- |
| **PM Loop**       | 高阶规划、拆解、写验收（Acceptance Criteria） |
| **Director Loop** | 取证 → 计划 → 执行 → 复核 → QA                |

**合同**：通过 `PM_TASKS.json` 严格通信，配合"合同不可变"约束，避免目标漂移与越权改动。

### 2️⃣ 事实流 Append-Only + 可回放：长期无人值守的底座

- `events.jsonl` 记录所有关键原子事件（工具调用、文件读写、QA 输出…），**只追加不覆盖**
- `run_id` 串联所有产物与引用，支持**回放、对比、复盘与归因**
- 失败要求在 **3 hops** 内定位到 Phase → Evidence → Tool Output

### 3️⃣ Mission Control Dashboard：以"观测与追踪"为核心

- UI 强调 **Read-Only 观测优先**（不在 UI 里直接做决策/改代码）
- **Process Monitor / Smart View / 虚拟滚动**：百万行日志仍可流畅查看
- **Glass Mind**：透明显示记忆检索、反思触发、上下文构建过程

### 4️⃣ 拟人化核心：Memory / Reflection / Persona（不是噱头，是稳定性）

| 模块                   | 能力                                    |
| ---------------------- | --------------------------------------- |
| **Memory（记忆）**     | 长期记忆（默认基于 LanceDB）            |
| **Reflection（反思）** | 从历史 run 抽象启发式规则，减少重复踩坑 |
| **Persona（人设）**    | 约束风格与禁忌，强化"职责边界"          |
| **Glass Mind**         | 把"内在过程"投影成可读的观测面板        |

---

## ✅ 已有功能一览

> 本节按"当前已具备/已在工程化落地"的能力列举；后续增强见 [Roadmap](#️-roadmap工具--游戏)。

### 工作流闭环

- PM 规划 → Director 执行 → QA 校验 → Dashboard 可视化
- 结构化任务合约：`PM_TASKS.json`
- Director 执行产物：`DIRECTOR_RESULT.json`、`QA_RESPONSE.md`、`RUNLOG.md`

### 可观测性与高性能 UI

- Mission Control 暗色系作战台 UI
- **Process Monitor** 侧边栏：状态/日志/变更追踪
- **Smart View**：将终端输出结构化渲染（增量解析、JSON 块、cmd/exit 等卡片化）
- **虚拟滚动**（Virtual Scrolling）：面向超长日志与密集事件

### 工具链与工程化

- **repo 工具**：tree / rg / slice read / diff
- **Tree-sitter**：符号定位、结构化替换/插入
- **QA**：ruff / mypy / pytest / jsonschema / pydantic 校验
- 端口策略、风险门禁、（可选）回滚与自动修复策略

### 拟人化核心

- Memory / Reflection / Persona
- Glass Mind 透明思维侧栏（记忆/反思/上下文构建可视化）
- Inner Voice（内心独白 / Thinking 投影）

---

## 🚀 快速开始

### 0️⃣ Python 虚拟环境（推荐）

```bash
# Windows
setup_venv.bat

# macOS / Linux
bash setup_venv.sh
```

> 如果启动时提示缺少 .venv，请先执行上述脚本。

### 1️⃣ 启动 Dashboard（推荐）

```bash
# 安装依赖
npm install

# 开发模式（Vite + Electron）
npm run dev

# 测试
npm run test

# 构建
npm run build
```

在界面中：

1. 选择 **Workspace**（缺少 `docs/` 会触发初始化引导）
2. 设置 **PM / Director / QA** 模型
3. 点击 **Start PM** → 进入闭环

### 2️⃣ CLI 运行

```bash
# PM：生成任务合约
.venv/bin/python backend/scripts/loop-pm.py --workspace /path/to/repo

# Director：执行任务
.venv/bin/python backend/scripts/loop-director.py --workspace /path/to/repo --iterations 1
```

> Windows 请使用 `.venv\\Scripts\\python.exe`。

### 🧰 故障排除（虚拟环境）

- 启动时提示缺少 `.venv`：先运行 `setup_venv.bat` / `setup_venv.sh`
- 依赖不完整警告：重新执行脚本以补装依赖
- 想使用系统 Python：设置 `HARBORPILOT_PYTHON` 指向自定义解释器

---

## 🏗️ 系统架构

```mermaid
graph LR
    PM[🧠 PM Loop] -->|📋 PM_TASKS.json| Dir[⚡ Director Loop]
    Dir -->|💻 Patch/Commands| Repo[📁 Workspace]
    Repo -->|✅ Test Logs| QA[🔍 QA System]
    QA -->|🧾 QA_RESPONSE.md| Dir
    Dir -->|🎯 DIRECTOR_RESULT.json| PM

    UI[🖥️ Dashboard Read-Only] -.->|👀 Observe| PM
    UI -.->|👀 Observe| Dir

    style PM fill:#e1f5fe
    style Dir fill:#f3e5f5
    style QA fill:#e8f5e8
    style UI fill:#fff3e0
```

### 关键设计点

| 设计                           | 说明                                                         |
| ------------------------------ | ------------------------------------------------------------ |
| **Control/Execute Separation** | PM 定义合约，Director 执行合约                               |
| **Event Sourcing**             | 事实流（events.jsonl）+ 投影层（DIALOGUE/RUNLOG/Smart View） |
| **Policy 合并**                | CLI > Task Overrides > Policy File > Env Vars > Defaults     |
| **成本模型**                   | LOCAL/FIXED/METERED 三类通道治理                             |

---

## 📁 产物与目录结构

默认运行产物输出到（建议可指向 RAMDISK）：`.harborpilot/runtime/`

| 文件/目录              | 说明                                           |
| ---------------------- | ---------------------------------------------- |
| `PM_TASKS.json`        | PM 任务合约（目标、AC、证据需求、策略覆盖）    |
| `PLAN.md`              | 规划与拆解（人类可读）                         |
| `DIRECTOR_RESULT.json` | 执行结果摘要（状态、失败码、风险等）           |
| `RUNLOG.md`            | 详细运行日志                                   |
| `QA_RESPONSE.md`       | QA 报告                                        |
| `DIALOGUE.jsonl`       | 拟人化叙事流（Dashboard 展示，含 Inner Voice） |
| `events.jsonl`         | 事实流（append-only，回放/评测/归因）          |
| `trajectory.json`      | 轨迹索引（串联事件与产物）                     |
| `memos/`               | 备忘录归档（任务完成后的总结）                 |

> 💡 **RAMDISK**：推荐配置 `HARBORPILOT_STATE_TO_RAMDISK=1` 将 runtime 指向内存盘（更快、更干净）。

---

## ⚖️ 系统不变量（v2：核心 6 + 修正案 2）

> 这组不变量是 HarborPilot 的"**系统宪法**"。详见 [完整文档](docs/agent/invariants.md)。

| #   | 不变量                       | 一句话说明                                                  |
| --- | ---------------------------- | ----------------------------------------------------------- |
| 1️⃣  | **合同不可变**               | `PM_TASKS.json` 的 goal/AC 不可被执行侧改写，只能追加证据   |
| 2️⃣  | **事实流 Append-Only**       | `events.jsonl` 只能追加，修正/回滚必须新增事件              |
| 3️⃣  | **Run ID 全局唯一**          | 产物/引用/轨迹必须以 `run_id` 串联，孤儿数据无效            |
| 4️⃣  | **观测优先（UI Read-Only）** | 运行态 UI 不修改任务/代码/状态；控制面只在 Loop             |
| 5️⃣  | **可回放**                   | 仅依赖 events + trajectory + artifacts paths 能重建关键过程 |
| 6️⃣  | **失败可定位**               | 失败必须在 3 hops 内定位到 Phase → Evidence → Tool Output   |
| 7️⃣  | **原子写入与一致性读取**     | 关键状态文件写入必须原子化，读取永不读到半截                |
| 8️⃣  | **记忆必须可溯源**           | memory/reflection 不能当事实，只能当建议，且必须带 refs     |

> 💡 **例外**：Setup/Onboarding 模式允许"受限写入"（仅写 `docs/` 与 `config`），且同样写入事件流以审计。

---

## 🧠 拟人化核心与 Glass Mind

### Memory（记忆）

- 默认采用 **LanceDB** 作为长期记忆后端（面向单人长期项目的经验积累）
- **混合检索**：相关性 / 时效性 / 重要性

### Reflection（反思）

- 从历史 run/memos 抽象启发式规则
- 目的不是"更像人"，而是**减少重复踩坑、提高稳定性**

### Persona（人设）

- 为 PM/Director/QA/Docs 等角色定义**风格与禁忌**
- 强化"职责边界"，减少漂移

### Glass Mind（透明思维）

UI 侧边栏展示：

- 检索到了哪些记忆？
- 触发了哪些反思？
- 上下文如何构建？

> 强化"**可解释性**"与"**可控性**"

---

## 🎛️ 模型路由与接入验证

> 目标：无论接入命令行 LLM、本地运行时、还是第三方 HTTPS API，都必须能在 UI 中完成**接入验证与胜任性测试**，确保"可用且胜任"。

### 角色路由（Role Routing）

HarborPilot 支持为不同角色选择不同模型：

- **PM** / **Director** / **QA** / **Docs Generator**

### Provider 类型（统一抽象）

| 类型                        | 示例                              | 成本通道          |
| --------------------------- | --------------------------------- | ----------------- |
| **CLI Provider**            | Codex CLI、Gemini CLI             | FIXED             |
| **Local HTTP Runtime**      | Ollama、LM Studio、Jan、llama.cpp | LOCAL             |
| **Standard HTTPS Provider** | OpenAI-compatible API             | METERED（强门禁） |

### 接入验证（必做）

每个 Provider/Role 都必须支持 **"Test"**：

#### Layer 1：可用性测试（Connectivity & Capability）

- ✅ 能启动/连通（health）
- ✅ model id 可用
- ✅ 能回答一个最小问题（response 非空）
- ✅ 超时/错误处理可控
- ✅ usage/tokens：能取则取，不能取则标估算

#### Layer 2：胜任性测试（Role Qualification）

| 角色         | 胜任标准                         |
| ------------ | -------------------------------- |
| **PM**       | 能输出结构化任务与 AC            |
| **Director** | 证据优先、计划可执行、不臆造文件 |
| **QA**       | 严格 PASS/FAIL + 原因与证据引用  |
| **Docs**     | 按模板生成，不编造事实           |

- ✅ 通过 → role **READY**
- ❌ 未通过 → role **BLOCKED**（对应运行按钮置灰，跳转到 Test Center）

---

## 📊 用量与成本观测

> HarborPilot 不崇拜 token，但必须"**可观测**"。
>
> 对单人长跑而言，真正重要的是：**成本通道（LOCAL/FIXED/METERED）+ 调用次数 + 延迟 +（能拿到则记录 tokens）**。

### 计划中的用量观测（与 Mission Control 融合）

| 组件                          | 功能                                  |
| ----------------------------- | ------------------------------------- |
| **Header Usage HUD**          | TOKENS / CALLS / LATENCY / BUDGET     |
| **Process Monitor Usage Tab** | 按角色/模式/模型分解 + 时间轴         |
| **Budget Gate**               | 对 METERED 通道默认强门禁，避免误烧钱 |

---

## 🗣️ Inner Voice（自言自语）

> 可选增强：从模型输出中提取 "thinking / reasoning summary / `<think>…</think>`" 等内容，作为角色的"内心独白"展示在对话流中。

### 设计原则

| 原则                 | 说明                         |
| -------------------- | ---------------------------- |
| **只展示已输出内容** | 不试图还原隐藏推理链         |
| **强制脱敏/裁剪**    | 防泄露 prompt/密钥/隐私      |
| **默认折叠显示**     | 作为 Glass Mind 的"旁路投影" |

### 用途

- 🎭 更沉浸的拟人化体验（像"自言自语"）
- 🔍 更强的可解释性：你能看到它"为什么这样想"（摘要级）

> 💡 示例独白："我需要先读哪些文件…我怀疑类型定义重复…我打算先跑 type-check…"

---

## 🆚 与行业工具的差异

> HarborPilot 的差异化不是"更炫更全"，而是更像 **"可运营的个人软件工厂"**。

### 与 IDE 一体化助手/代理对比

**代表产品**：Cursor、Windsurf、Cline、Continue、GitHub Copilot、Codex (IDE)

| 维度         | 他们通常强在哪里        | HarborPilot 的核心区别               |
| ------------ | ----------------------- | ------------------------------------ |
| **定位**     | 编辑器内的智能助手/插件 | **指挥台/流水线**，不是插件          |
| **交互模式** | 对话式辅助、Tab 补全    | **合同闭环 + 事实流可回放**          |
| **成本模型** | 通常按 token 计费       | **LOCAL/FIXED 优先**，METERED 强门禁 |
| **可追溯性** | 有限的历史记录          | **失败 3 hops 可定位**，全量事件流   |
| **无人值守** | 需要人工交互            | 支持**长期无人值守运行**             |

### 与终端/CLI 编码代理对比

**代表产品**：Claude Code、Aider

| 维度         | 他们通常强在哪里   | HarborPilot 的核心区别                 |
| ------------ | ------------------ | -------------------------------------- |
| **使用方式** | 终端交互、轻量灵活 | **Dashboard 可视化** + CLI 双模        |
| **状态管理** | 会话级别           | **run_id 全局串联**，跨会话追踪        |
| **可观测性** | 终端输出           | **Smart View + Glass Mind** 结构化展示 |
| **经验积累** | 有限               | **Memory/Reflection** 长期记忆         |

### 与云端交付型工程代理对比

**代表产品**：Devin、各类云沙箱 coding agent

| 维度         | 他们通常强在哪里   | HarborPilot 的核心区别          |
| ------------ | ------------------ | ------------------------------- |
| **执行环境** | 云端沙箱、并行执行 | **本地优先**，数据不出本机      |
| **成本结构** | 按使用量/订阅计费  | **电费 + 包月 CLI**，边际成本低 |
| **透明度**   | 云端黑箱           | **Glass Mind** 透明观测         |
| **控制力**   | 有限干预           | **合同不可变 + 6 条不变量**     |

### 与开源框架/平台对比

**代表产品**：OpenHands

| 维度         | 他们通常强在哪里          | HarborPilot 的核心区别            |
| ------------ | ------------------------- | --------------------------------- |
| **设计目标** | 通用 Agent 框架、生态扩展 | **软件开发闭环专精**              |
| **约束程度** | 灵活可配置                | **强约束 + 不变量**，减少失控     |
| **可复盘性** | 依赖日志                  | **事实流 + 轨迹索引**，完全可重建 |

### 与通用型自动化 Agent 对比

**代表产品**：Manus

| 维度         | 他们通常强在哪里       | HarborPilot 的核心区别            |
| ------------ | ---------------------- | --------------------------------- |
| **覆盖范围** | 多种任务类型、覆盖面广 | **更克制**，只做开发流水线        |
| **稳定性**   | 通用带来不确定性       | **强边界**，减少失控面            |
| **成本控制** | 通用成本模型           | **三分法**（LOCAL/FIXED/METERED） |

### 与新型管制塔/平台工具对比

**代表产品**：Antigravity、TRAE

| 维度         | 他们通常强在哪里 | HarborPilot 的核心区别                 |
| ------------ | ---------------- | -------------------------------------- |
| **定位**     | 企业级/团队协作  | **单人优先**，面向个人开发者           |
| **成本模型** | 企业订阅         | **电费/包月**，适合长期长跑            |
| **拟人化**   | 功能性设计       | **Memory/Reflection/Persona** 认知架构 |

### 差异总结

| 对比维度        | HarborPilot 的做法                    |
| --------------- | ------------------------------------- |
| 🎯 **成本模型** | LOCAL/FIXED 为主，METERED 强门禁      |
| 📜 **行为约束** | 合同 + 6 条不变量，边界写死           |
| 🔄 **可追溯性** | 事实流可回放，3 hops 可定位           |
| 🧠 **可解释性** | 拟人化核心 + Glass Mind + Inner Voice |
| 🖥️ **UI 体验**  | Mission Control 作战指挥台            |

> 💡 **一句话总结**：很多工具是"更聪明的助手/插件"，HarborPilot 是 **"更工程化的个人软件工厂"**。

---

## 🗺️ Roadmap：工具 × 游戏

> HarborPilot 将演进为 **"无人值守软件工厂 + 游戏化拟人世界"**
>
> 参考：[Game Dev Story](https://kairosoft.net/game/appli/gamedev.html)（公司经营）+ [AI Town](https://github.com/a16z-infra/ai-town)（角色叙事）

### 三视图形态（规划）

| 视图           | 定位       | 说明                       |
| -------------- | ---------- | -------------------------- |
| 🛰️ **Mission** | 生产指挥台 | 默认主视图，工具优先       |
| 🏢 **Studio**  | 办公室经营 | 工位、项目看板、成长与解锁 |
| 🏙️ **Town**    | 拟人化小镇 | 事实驱动的叙事与陪伴       |

### 核心规则（永不妥协）

- **Tool-first**：游戏层永远不干扰真实工程执行
- **事实驱动剧情**：剧情卡必须绑定 `run_id` / 事件引用，禁止"编造成功"
- **成长解锁带来现实收益**：更稳的 QA、更好的取证、更可控的流程

### 分阶段路线

| Phase       | 内容                                            |
| ----------- | ----------------------------------------------- |
| **Phase 0** | Story Cards、成就系统、角色名片（零侵入游戏化） |
| **Phase 1** | Studio 工位布局、项目进度可视化、成长系统       |
| **Phase 2** | Town 角色日常、城市事件系统                     |

---

## 📚 文档

| 文档                                            | 说明                                       | 读者   |
| ----------------------------------------------- | ------------------------------------------ | ------ |
| [👀 人类文档入口](docs/human/README.md)         | 面向产品/业务/首次使用的阅读顺序           | 所有人 |
| [🤖 Agent 文档入口](docs/agent/README.md)       | 约束/证据链/工程细节（可执行）             | 工程师 |
| [🏗️ 架构文档](docs/agent/architecture.md)       | 状态机、事件模型、Context Engine           | 工程师 |
| [🧠 拟人化设计](docs/agent/anthropomorphic_design.md) | Memory/Reflection/Persona/Glass Mind  | 工程师 |
| [📖 参考手册](docs/agent/reference.md)          | CLI 参数、工具清单、环境变量、产物索引     | 开发者 |
| [📄 产品说明书](docs/product/product_spec.md)   | 产品定位、核心优势、行业对比               | 所有人 |
| [🧪 测试指南](TESTING.md)                       | 测试环境搭建、运行命令                     | 测试   |

---

## 🤝 贡献与许可

欢迎提交 Issue / PR！

> 建议优先从：Docs、UI 投影、工具适配、测试用例、Doctor/Setup 规则开始

**License**：MIT

---

<div align="center">

## 🔖 现实主义三件套（优先落地建议）

如果你想把系统从"能跑"推进到"**可长期运营**"，优先级建议：

| #   | 模块                            | 说明                                     |
| --- | ------------------------------- | ---------------------------------------- |
| 1️⃣  | **Provider 接入 + Test Center** | 强门禁，确保模型可用且胜任               |
| 2️⃣  | **Usage/Cost-class 观测**       | LOCAL/FIXED/METERED 可见可控             |
| 3️⃣  | **Eval/回归对比**               | 升级不退化（成功率/耗时/调用次数可量化） |

---

**⭐ 如果这个项目对你有帮助，请给个 Star！**

Made with ❤️ by HarborPilot Team

</div>
