# HarborPilot 实时通知集成展望计划

本计划旨在为 HarborPilot 集成 WhatsApp、Telegram 等实时通知工具，实现任务阶段完成情况的实时报告，增强系统的可观测性和用户参与度，同时保持“本地优先、可回放、成本可控”的核心原则。

---

## 🎯 核心目标

- 为“无人值守自动化编程指挥台”提供实时通知能力
- 在不打断主流程的前提下，及时同步任务阶段、关键事件和异常
- 支持多渠道、可配置、可过滤的通知策略
- 保持事件可追溯与本地优先：通知仅作为“事实流的外延”

---

## 📊 现状与约束

### 现状特点

- **本地优先**：主要运行在用户本地环境
- **事实流驱动**：核心事件记录在 `events.jsonl`
- **双循环架构**：PM Loop → Director Loop → QA
- **可回放性**：基于事件与产物可完整重放
- **拟人化系统**：Memory / Reflection / Persona / Inner Voice

### 已有可视化机制

- Mission Control Dashboard
- 本地日志：`RUNLOG.md`、`events.jsonl`
- 状态文件：`PM_TASKS.json`、`DIRECTOR_RESULT.json`

---

## 🧭 设计原则

1. **Local-first**：通知配置和敏感信息本地存储，默认关闭
2. **可追溯**：所有通知发送与失败写入 `events.jsonl`
3. **可回放**：通知历史可审计、可重放
4. **成本可控**：速率限制、聚合与静默时段
5. **安全优先**：加密存储、内容脱敏、权限控制

---

## 🏗️ 通知事件模型

```ts
interface NotificationEvent {
  id: string; // run_id + timestamp
  type: 'phase_start' | 'phase_complete' | 'task_complete' | 'error' | 'milestone';
  source: 'pm' | 'director' | 'qa' | 'system';
  severity: 'info' | 'success' | 'warning' | 'error';
  title: string;
  message: string;
  details?: {
    phase: string;
    progress: number;
    duration?: number;
    artifacts?: string[];
    error_code?: string;
  };
  timestamp: string;
  run_id: string;
}
```

### 关键触发点

- **PM Loop**：任务合约完成 / 规划完成 / Handoff
- **Director Loop**：取证结束 / 计划完成 / 修改完成 / 结果汇总
- **QA**：测试完成 / 失败报告
- **System**：超时警告 / 成本阈值 / 异常

---

## 🔌 通知渠道抽象层

```py
class NotificationChannel:
    async def send(self, event: NotificationEvent) -> bool: ...
    async def is_available(self) -> bool: ...
    def get_config_schema(self) -> dict: ...
```

### 推荐支持渠道（可扩展）

- Telegram Bot API
- WhatsApp Business API
- 企业微信机器人
- 钉钉机器人
- 邮件（SMTP）
- Webhook（自定义）

---

## ⚙️ 配置与过滤

```json
{
  "notifications": {
    "enabled": true,
    "channels": {
      "telegram": {
        "enabled": true,
        "bot_token": "encrypted_token",
        "chat_id": "encrypted_chat_id",
        "filters": {
          "min_severity": "info",
          "event_types": ["phase_complete", "error", "milestone"]
        }
      }
    },
    "global_settings": {
      "rate_limit": {"max_per_hour": 10, "cooldown_minutes": 5},
      "quiet_hours": {"enabled": true, "start": "22:00", "end": "08:00"}
    }
  }
}
```

- 频道可单独开启/禁用
- 过滤支持事件类型、严重等级
- 支持“勿扰时段”“速率限制”

---

## 🚀 实施阶段规划

### Phase 1：基础架构（2-3 周）

- 事件系统扩展：从 `events.jsonl` 生成通知事件
- 通知抽象层：`NotificationManager` + `NotificationChannel`
- 本地测试渠道与可视化查看

### Phase 2：渠道实现（3-4 周）

- Telegram Bot
- WhatsApp Business
- 其他渠道（邮件 / Webhook）

### Phase 3：UI 集成（2 周）

- 设置页通知面板
- Dashboard 通知历史
- 过滤 / 重发 / 事件查看

### Phase 4：高级能力（2-3 周）

- 智能聚合、批量摘要
- 交互式通知（按钮 / 快速操作）
- 多语言与时区适配

---

## 🔒 安全与隐私

- **本地加密**：token/phone/secret 仅本地保存
- **内容脱敏**：避免泄露代码、密钥、客户信息
- **权限控制**：配置修改需管理员权限
- **审计追踪**：发送、失败、重试均写入 `events.jsonl`

---

## 📊 成本与性能影响

- **成本控制**：WhatsApp 计费、Telegram 免费但限速
- **性能影响**：异步发送、不阻塞主流程
- **资源消耗**：小型队列与本地缓存

---

## 🎨 用户体验设计

- 通知内容**简洁结构化**：图标 + 关键字段
- 允许**静默时间**与**个性化偏好**
- 支持**不同事件使用不同渠道**
- 逐步启用：默认关闭 + 引导配置

---

## 🧩 与现有系统融合

- **事实流**：通知事件作为事实流派生产物
- **可回放**：通知历史回放与审计
- **拟人化**：通知措辞可随角色风格变化
- **游戏化**：里程碑 / 成就提示

---

## ✅ 成功指标（建议）

- 关键阶段通知成功率 ≥ 99%
- 端到端通知延迟 ≤ 3 秒（本地网络）
- 用户可配置覆盖率（启用率 / 渠道选择）
- 通知噪声控制（≤ 10 次/小时默认）

---

## 📌 备注

本计划为展望与架构草案，不改变当前默认行为。所有通知功能应在“默认关闭”的前提下迭代，确保本地优先、可回放和成本可控的系统原则不被破坏。
