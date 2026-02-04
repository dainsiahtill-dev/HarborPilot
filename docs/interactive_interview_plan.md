# HarborPilot 交互式面试流程重新设计

本方案将 HarborPilot 的自动化面试改为用户主导的交互式面试：用户手动选择问题、发送给模型、实时审核回答并手动通过/失败，以解决模型角色认知错误、评分不准确与思考格式失败等问题。

---

## 🎯 核心目标

- **用户主导**：问题由用户选择或自定义，评估由用户裁决
- **可控可靠**：弱化自动评分，减少误判
- **过程可追溯**：全过程记录可回放
- **本地优先**：记录与配置保持本地存储

---

## 📌 现状问题与痛点

### 问题根因

- **角色认知错误**：模型将自己视为“面试助手”而非“候选人”
- **回避式回答**：频繁反问“需要评估什么”，未直接作答
- **评分机制失效**：关键词匹配无法体现真实能力
- **thinking 失败**：输出格式不稳定导致评估误判

### 用户核心诉求

- 自动化不可靠，需要**人工干预**
- 评分死板，无法体现真实表现
- 希望**手动控制**问答流程

---

## 🔄 新的交互式流程

### 传统流程

- 自动发送问题 → 自动评分 → 通过/失败

### 新流程

- 用户选择问题 → 发送给模型 → 用户审核 → 手动通过/失败

---

## 🧭 交互式面试大厅设计

### 三栏布局

```
┌─────────────────────────────────────────────────────────┐
│                    交互式面试大厅                        │
├─────────────────┬─────────────────┬─────────────────────┤
│   岗位选择       │   问题模板库     │   实时对话区         │
│                │                │                     │
│ ○ PM 项目经理    │ 📋 项目规划类   │ 👤 模型: gpt-5.1    │
│ ○ Director 导演  │ 🤝 冲突协调类   │                     │
│ ○ QA 质量保证    │ 🔧 技术决策类   │ Q: 请分析项目需求... │
│ ○ Docs 文档     │ 📊 需求分析类   │                     │
│                │ ➕ 自定义问题   │                     │
│                │                │ A: ...               │
├─────────────────┴─────────────────┴─────────────────────┤
│              [发送问题] [通过] [失败] [重新提问]          │
└─────────────────────────────────────────────────────────┘
```

### 问题模板库

- 按岗位与难度分类
- 支持预置问题 + 自定义问题
- 每个问题带 **期望评估指标**

```ts
interface QuestionTemplate {
  id: string;
  category: string;
  title: string;
  question: string;
  expectedCriteria: string[];
  difficulty: 'basic' | 'intermediate' | 'advanced';
  role: 'pm' | 'director' | 'qa' | 'docs';
}
```

---

## 💬 实时对话与人工评估

```ts
interface InterviewMessage {
  id: string;
  type: 'question' | 'answer' | 'system';
  content: string;
  timestamp: string;
  sender: 'user' | 'model';
  questionId?: string;
  evaluation?: {
    userRating: 'pass' | 'fail' | 'pending';
    notes?: string;
    criteriaAssessment?: Record<string, boolean>;
  };
}
```

关键能力：

- **逐题评价**：每条回答可标记通过/失败并附注
- **实时显示**：用户即时审阅回答内容
- **自由掌控**：支持继续追问或重试

---

## 🧠 智能提示（非强制评分）

- **回答质量提示**：检测思考标签、覆盖标准
- **问题推荐**：基于岗位/难度/薄弱项推荐问题
- **辅助建议**：提示缺失点，帮助人工判断

---

## 📑 面试报告与历史

- 自动生成面试报告
- 保存至本地运行时目录
- 支持历史对比与回放

```ts
interface InterviewReport {
  id: string;
  role: RoleId;
  provider: ProviderInfo;
  startTime: string;
  endTime: string;
  overallStatus: 'passed' | 'failed';
  questions: InterviewQuestion[];
  summary: {
    totalQuestions: number;
    passedQuestions: number;
    averageRating: number;
    strengths: string[];
    weaknesses: string[];
    recommendation: string;
  };
  userNotes: string;
}
```

---

## 🛠️ 技术实现方案（概览）

### 前端

- `InterviewHall` 拆分为 **选择 / 交互 / 报告** 三个视图
- 新增 **QuestionTemplateLibrary / InterviewChat / ReportPanel**
- 交互式状态机：`selection → interview → report`

### 后端

新增交互式面试 API：

- `POST /llm/interview/ask`：发送单题
- `POST /llm/interview/save`：保存报告与状态

改进 Prompt：明确“应聘者角色”，要求直接作答，避免反问。

### 数据持久化

- `.harborpilot/runtime/interviews/`
- 统一历史索引 `interview_history.json`

---

## 🔒 安全与一致性

- 面试记录可回放与审计
- 用户操作写入 `events.jsonl`
- 与“本地优先、可回放”不变量保持一致

---

## 🚀 实施计划

### Phase 1（2 周）
- 交互式面试 UI 基础框架
- 问题模板库与对话组件

### Phase 2（1 周）
- 后端单题 API
- Prompt 强化与角色约束

### Phase 3（1-2 周）
- 面试报告与历史管理
- 智能提示与辅助功能

---

## ✅ 预期效果

- **角色认知问题显著降低**
- **评估准确性提升**（人工裁决）
- **流程更可控**、可复查、可追溯

---

## 📌 备注

本方案以“用户主导 + 人工评估”为核心，短期内优先解决可靠性问题；自动评分和智能分析作为辅助能力逐步引入，不再作为最终通过/失败的唯一依据。
