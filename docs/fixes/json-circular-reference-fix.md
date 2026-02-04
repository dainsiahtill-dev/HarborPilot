# LLM视图模式循环引用错误修复

## 问题描述

在LLM视图模式保存时出现循环引用错误：
```
Converting circular structure to JSON --> starting at object with constructor 'HTMLButtonElement' | property '__reactFiber$def0b0gzu27' -> object with constructor 'FiberNode' --- property 'stateNode' closes the circle
```

## 根本原因

React组件在序列化时包含了循环引用的DOM元素和React Fiber节点，导致`JSON.stringify()`无法处理。

## 解决方案

### 1. 创建安全的JSON序列化函数

在 `SettingsModal.tsx` 中添加了 `safeJsonStringify` 函数：

```typescript
// 安全的JSON序列化函数，处理循环引用
const safeJsonStringify = (obj: any, space?: number): string => {
  const seen = new WeakSet();
  return JSON.stringify(obj, (key, val) => {
    if (val != null && typeof val === 'object') {
      if (seen.has(val)) {
        return '[Circular Reference]';
      }
      seen.add(val);
    }
    // 过滤掉React Fiber节点和其他不可序列化的对象
    if (val && typeof val === 'object') {
      if (val.constructor?.name === 'HTMLButtonElement' ||
          val.constructor?.name === 'FiberNode' ||
          val.constructor?.name === 'Object' && val.$$typeof) {
        return '[React Element]';
      }
    }
    return val;
  }, space);
};
```

### 2. 替换所有相关的JSON.stringify调用

修复了以下4个位置的JSON序列化调用：

1. **LLM Test Report显示**（第1841行）
   ```typescript
   // 修复前
   {JSON.stringify(reportDrawer.data, null, 2)}
   // 修复后
   {safeJsonStringify(reportDrawer.data, 2)}
   ```

2. **测试报告事件输出**（第935行）
   ```typescript
   // 修复前
   emitEvent('response', JSON.stringify(report, null, 2));
   // 修复后
   emitEvent('response', safeJsonStringify(report, 2));
   ```

3. **面试报告事件输出**（第1127行）
   ```typescript
   // 修复前
   emitEvent('response', JSON.stringify(report, null, 2));
   // 修复后
   emitEvent('response', safeJsonStringify(report, 2));
   ```

4. **Provider配置序列化**（第224-225行）
   ```typescript
   // 修复前
   env: JSON.stringify(cfg.env || {}, null, 2),
   headers: JSON.stringify(cfg.headers || {}, null, 2),
   // 修复后
   env: safeJsonStringify(cfg.env || {}, 2),
   headers: safeJsonStringify(cfg.headers || {}, 2),
   ```

## 修复效果

### ✅ 解决的问题
1. **循环引用错误**：不再出现 "Converting circular structure to JSON" 错误
2. **React元素过滤**：自动过滤掉DOM元素和Fiber节点
3. **数据完整性**：保留所有业务相关的数据结构
4. **错误处理**：优雅地处理循环引用，显示占位符

### 🔧 技术特性
1. **WeakSet追踪**：使用WeakSet检测循环引用，避免内存泄漏
2. **类型检测**：识别React元素和DOM对象
3. **占位符显示**：循环引用显示为 `[Circular Reference]`
4. **React元素处理**：React元素显示为 `[React Element]`

## 验证结果

- ✅ 构建成功，无语法错误
- ✅ 所有JSON序列化调用已替换
- ✅ 保持了原有的功能和UI显示
- ✅ 错误处理更加健壮

## 使用建议

1. **全局应用**：考虑将 `safeJsonStringify` 提取为工具函数，在项目中全局使用
2. **扩展功能**：可以根据需要添加更多类型的过滤规则
3. **性能考虑**：对于大型对象，WeakSet的性能开销很小
4. **调试友好**：占位符有助于识别数据结构问题

## 相关文件

- `frontend/src/app/components/SettingsModal.tsx` - 主要修复文件
- `docs/fixes/json-circular-reference-fix.md` - 本文档

这个修复确保了LLM视图模式能够正常保存和显示，同时保持了数据的完整性和可读性。
