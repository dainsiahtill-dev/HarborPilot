## 现状检查
- App.tsx 里现在存在两个 notifications state（重复定义），会导致编译失败或行为异常。
- EnhancedNotificationManager.tsx 实际导出的是 NotificationManager（命名不一致），App.tsx 的 import/JSX 会对不上。
- ErrorBoundary.tsx 使用了 React.Component / React.ReactNode，但没有引入 React，会在 TS/构建阶段报错。

## 修复步骤（代码改动）
1. **清理 App.tsx 的重复状态**
   - 保留一份 notifications state（靠近组件顶部那份），删除另一份重复定义。
   - 确保 addNotification/removeNotification 只依赖这一份 state。
2. **统一通知组件命名与类型**
   - 两种方案二选一（我会选更一致的那种）：
     - A：把 EnhancedNotificationManager.tsx 的导出改为 EnhancedNotificationManager（保持 App.tsx 现有 import 不变）。
     - B：把 App.tsx 改为 import { NotificationManager } 并使用 <NotificationManager />。
   - 同时把 Notification 类型导出（或在 App.tsx 复用该类型），避免 App.tsx 内联重复类型。
3. **修复 ErrorBoundary.tsx 的 React 引用**
   - 显式 `import React from 'react'`（或等价写法），保证 class 版 ErrorBoundary 正常工作。
   - 顺带确认函数版 ErrorBoundary 是否需要保留；如果不捕获错误就移除，避免误导。
4. **确认 Toaster/sonner 的定位**
   - 继续保留 Toaster + toast（现有代码大量使用 toast）。
   - ErrorBoundary 的“查看详情”动作保持打开 LogsModal；通知系统只做补充而不替代 sonner。

## 验证步骤（不改外部系统前提下）
1. 前端 TypeScript 检查/构建，确保无类型错误、无导出/导入错误。
2. 本地启动桌面前端，手动验证：
   - PM/Director/Ollama 按钮 loading 状态是否正确（不会卡死、不会重复点击）。
   - FileViewer/DialoguePanel 的 skeleton 是否在首次加载时出现且消失。
   - 触发一次错误（例如断开后端）看 ErrorBoundary/通知/日志入口是否可用。

## 收尾清理
- 删除未被引用的新组件（若最终决定不用某个系统），避免仓库膨胀。
- 统一命名（NotificationManager vs EnhancedNotificationManager），减少后续维护成本。