# HarborPilot E2E 测试框架

## 概述

这是 HarborPilot 项目的端到端测试框架，使用 Playwright 进行 Web 应用测试，支持完整的工作流验证。

## 目录结构

```
e2e/
├── README.md                 # 本文档
├── requirements.txt          # E2E 测试依赖
├── conftest.py              # pytest 配置和 fixtures
├── pytest.ini              # pytest 配置文件
├── playwright.config.ts     # Playwright 配置
├── pages/                   # 页面对象模型
│   ├── __init__.py
│   ├── base_page.py         # 基础页面类
│   ├── dashboard_page.py    # Dashboard 页面
│   └── workspace_page.py    # 工作区页面
├── utils/                   # 工具函数
│   ├── __init__.py
│   ├── test_helpers.py      # 测试辅助函数
│   ├── mock_data.py         # 模拟数据
│   └── file_utils.py        # 文件操作工具
├── tests/                   # 测试用例
│   ├── __init__.py
│   ├── test_dashboard.py    # Dashboard 功能测试
│   ├── test_workflow.py     # 完整工作流测试
│   └── test_integration.py  # 集成测试
├── fixtures/                # 测试数据
│   ├── workspaces/          # 测试工作区
│   └── responses/           # 模拟响应
└── reports/                 # 测试报告
    └── .gitkeep
```

## 快速开始

### 1. 安装依赖

```bash
cd tests/e2e
pip install -r requirements.txt
playwright install
```

### 2. 运行测试

```bash
# 运行所有测试
pytest

# 运行特定测试文件
pytest tests/test_dashboard.py

# 运行带 UI 的测试
pytest --headed

# 生成测试报告
pytest --html=reports/report.html
```

### 3. 调试测试

```bash
# 调试模式
pytest --pdb

# 慢速模式（便于观察）
pytest --slowmo 1000

# 保留浏览器窗口
pytest --headed --browser-channel chrome
```

## 测试策略

### 1. 分层测试
- **单元层**: 页面对象方法的单元测试
- **集成层**: 多页面交互测试
- **端到端层**: 完整业务流程测试

### 2. 测试分类
- **冒烟测试**: 核心功能快速验证
- **回归测试**: 防止功能倒退
- **性能测试**: 响应时间和资源使用

### 3. 数据管理
- 使用临时工作区
- 模拟 AI 响应
- 测试后自动清理

## 配置说明

### 环境变量

```bash
# 测试环境
export HARBORPILOT_TEST_ENV=development
export HARBORPILOT_TEST_BASE_URL=http://localhost:5173
export HARBORPILOT_TEST_WORKSPACE_ROOT=/tmp/harborpilot-test

# AI 服务模拟
export HARBORPILOT_MOCK_AI=true
export HARBORPILOT_MOCK_RESPONSES_PATH=./fixtures/responses

# 测试配置
export HARBORPILOT_TEST_TIMEOUT=30000
export HARBORPILOT_TEST_RETRIES=3
```

### 配置文件

- `pytest.ini`: pytest 配置
- `playwright.config.ts`: Playwright 配置
- `conftest.py`: 测试前置后置

## 编写测试

### 1. 页面对象模式

```python
from pages.dashboard_page import DashboardPage

def test_dashboard_basic_functionality(page):
    dashboard = DashboardPage(page)
    dashboard.navigate()
    dashboard.select_workspace("/path/to/workspace")
    dashboard.start_pm_loop()
    assert dashboard.is_pm_running()
```

### 2. 数据驱动测试

```python
import pytest

@pytest.mark.parametrize("workspace_type", ["python", "javascript", "typescript"])
def test_different_workspace_types(page, workspace_type):
    # 测试不同类型的工作区
    pass
```

### 3. 异步测试

```python
import pytest
from playwright.async_api import async_playwright

@pytest.mark.asyncio
async def test_async_workflow():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        # 测试逻辑
        await browser.close()
```

## 最佳实践

1. **使用页面对象模型**: 封装页面交互逻辑
2. **保持测试独立**: 每个测试用例应该独立运行
3. **合理使用等待**: 避免硬编码等待时间
4. **错误处理**: 添加适当的错误检查和恢复
5. **测试数据管理**: 使用工厂模式创建测试数据
6. **定期维护**: 及时更新测试用例和页面对象

## 故障排除

### 常见问题

1. **元素定位失败**: 检查选择器和等待策略
2. **超时错误**: 增加超时时间或优化等待逻辑
3. **测试不稳定**: 使用重试机制和稳定性改进
4. **环境问题**: 确保测试环境配置正确

### 调试技巧

1. 使用 `page.pause()` 暂停执行
2. 启用调试模式查看浏览器状态
3. 检查网络请求和响应
4. 使用截图和视频记录

## 扩展指南

### 添加新的页面对象

1. 在 `pages/` 目录创建新文件
2. 继承 `BasePage` 类
3. 实现页面特有的方法
4. 添加相应的测试用例

### 集成 CI/CD

```yaml
# .github/workflows/e2e.yml
name: E2E Tests
on: [push, pull_request]
jobs:
  e2e:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.10'
      - name: Install dependencies
        run: |
          cd tests/e2e
          pip install -r requirements.txt
          playwright install
      - name: Run tests
        run: pytest --html=reports/report.html
```

## 贡献指南

1. 遵循现有的代码风格
2. 添加适当的测试文档
3. 确保测试覆盖率
4. 提交前运行所有测试
