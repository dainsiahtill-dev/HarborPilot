# Codex CLI 环境变量管理系统设计

本计划设计一套完整的环境变量管理系统，解决 Codex CLI 在运行前需要设置环境变量（如 MINIMAX_API_KEY）的问题。

## 问题分析

当前遇到的问题是：
1. Codex CLI 执行 MiniMax 模型时需要 `MINIMAX_API_KEY` 环境变量
2. 错误信息：`Missing environment variable: MINIMAX_API_KEY`
3. 需要在运行 Codex CLI 前动态设置环境变量

## 现有架构分析

### Keychain 系统
- 前端有 `window.harborpilot.secrets.get/set` API
- 后端配置使用 `api_key_ref: "keychain:maxmini"` 格式
- 支持安全的密钥存储和检索

### 环境变量处理
- Codex CLI provider 已有 `env` 配置字段
- 使用 `build_utf8_env()` 函数构建环境变量
- 前端 CodexCLIProviderSettings 已有环境变量 JSON 编辑器

### 模型特定需求
- 不同模型需要不同的环境变量
- MiniMax 需要 `MINIMAX_API_KEY`
- Gemini 需要 `GOOGLE_API_KEY`
- OpenAI 需要 `OPENAI_API_KEY`

## 设计方案

### 1. 模型-环境变量映射表
创建模型到所需环境变量的映射关系：
```python
MODEL_ENV_REQUIREMENTS = {
    "minimax": ["MINIMAX_API_KEY"],
    "gemini": ["GOOGLE_API_KEY"],
    "openai": ["OPENAI_API_KEY"],
    "anthropic": ["ANTHROPIC_API_KEY"],
}
```

### 2. 自动环境变量解析
在 Codex CLI provider 的 `invoke` 方法中：
- 检测模型类型（从模型名称推断）
- 从 keychain 自动获取对应的 API key
- 动态注入到环境变量中

### 3. 前端配置增强
- 在 CodexCLIProviderSettings 中添加模型特定的环境变量提示
- 提供一键配置按钮，自动从 keychain 获取密钥
- 显示缺失的环境变量警告

### 4. Keychain 集成
- 扩展 keychain 支持更多模型类型
- 提供统一的密钥管理接口
- 支持密钥验证和测试

## 实现步骤

### 步骤 1: 后端环境变量自动解析
修改 `codex_cli_provider.py`：
- 添加模型检测函数
- 添加 keychain 集成
- 在 `invoke` 方法中自动设置环境变量

### 步骤 2: 前端配置界面优化
修改 `CodexCLIProviderSettings.tsx`：
- 添加模型特定的环境变量提示
- 提供自动配置按钮
- 显示环境变量状态

### 步骤 3: Keychain 扩展
扩展 keychain 支持：
- 添加 MiniMax 密钥支持
- 提供密钥验证功能
- 统一密钥管理接口

### 步骤 4: 测试和验证
- 测试 MiniMax 模型连接
- 验证环境变量自动设置
- 确保向后兼容性

## 技术细节

### 环境变量优先级
1. 用户显式配置的 `env` 字段（最高优先级）
2. 自动从 keychain 解析的环境变量
3. 系统默认环境变量（最低优先级）

### 模型检测逻辑
```python
def detect_model_type(model_name: str) -> str:
    model_lower = model_name.lower()
    if 'minimax' in model_lower or 'm2.' in model_lower:
        return 'minimax'
    elif 'gemini' in model_lower:
        return 'gemini'
    elif 'gpt' in model_lower:
        return 'openai'
    elif 'claude' in model_lower:
        return 'anthropic'
    return 'unknown'
```

### Keychain 集成
```python
def get_keychain_key(key_ref: str) -> Optional[str]:
    # 解析 keychain:maxmini -> maxmini
    # 调用 keychain API 获取密钥
    # 返回密钥或 None
```

## 预期效果

1. **自动配置**：用户选择模型后，系统自动获取对应的环境变量
2. **错误减少**：避免因环境变量缺失导致的连接失败
3. **用户体验**：提供清晰的配置指导和状态提示
4. **安全性**：使用 keychain 安全存储密钥，避免明文配置

## 兼容性考虑

- 保持现有 `env` 配置的向后兼容
- 支持手动覆盖自动配置
- 提供详细的错误信息和修复建议
