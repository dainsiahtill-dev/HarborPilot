# HarborPilot E2E 测试框架设置指南

## 快速开始

### 1. 环境准备

确保你已经安装了以下依赖：
- Python 3.10+
- Node.js 16+
- HarborPilot 应用程序运行在 http://localhost:5173

### 2. 安装依赖

```bash
# 进入 E2E 测试目录
cd tests/e2e

# 方式一：使用 Python 脚本安装
python run_tests.py install

# 方式二：手动安装
pip install -r requirements.txt
python -m playwright install

# 方式三：使用 npm（如果需要）
npm install
```

### 3. 配置环境

```bash
# 复制环境配置文件
cp .env.example .env

# 编辑配置文件（可选）
nano .env
```

### 4. 运行测试

```bash
# 运行所有测试
python run_tests.py test

# 运行特定类型的测试
python run_tests.py test --type smoke
python run_tests.py test --type dashboard
python run_tests.py test --type workflow
python run_tests.py test --type integration

# 运行带界面的测试（用于调试）
python run_tests.py test --headed

# 使用不同浏览器
python run_tests.py test --browser firefox
python run_tests.py test --browser webkit

# 详细输出
python run_tests.py test --verbose
```

## 测试分类

### 1. 冒烟测试 (Smoke Tests)
快速验证核心功能是否正常工作
```bash
python run_tests.py test --type smoke
```

### 2. Dashboard 功能测试
测试 Dashboard 界面的各种功能
```bash
python run_tests.py test --type dashboard
```

### 3. 工作流测试
测试完整的 PM → Director → QA 工作流
```bash
python run_tests.py test --type workflow
```

### 4. 集成测试
测试各组件之间的集成
```bash
python run_tests.py test --type integration
```

## 调试技巧

### 1. 使用 Playwright Inspector
```bash
# 启用调试模式
PWDEBUG=1 python run_tests.py test --headed
```

### 2. 慢速模式
```bash
# 慢速执行，便于观察
python run_tests.py test --headed --slowmo 1000
```

### 3. 生成测试报告
```bash
# 生成 HTML 报告
python run_tests.py test --verbose
# 报告位置：reports/report.html
```

### 4. 截图和视频
测试失败时会自动截图，存储在 `reports/screenshots/` 目录

## 项目结构

```
e2e/
├── pages/                   # 页面对象模型
│   ├── base_page.py        # 基础页面类
│   ├── dashboard_page.py   # Dashboard 页面
│   └── workspace_page.py   # 工作区页面
├── utils/                   # 工具函数
│   ├── test_helpers.py     # 测试辅助函数
│   ├── mock_data.py        # 模拟数据生成
│   └── file_utils.py       # 文件操作工具
├── tests/                   # 测试用例
│   ├── test_dashboard.py    # Dashboard 测试
│   ├── test_workflow.py     # 工作流测试
│   └── test_integration.py  # 集成测试
├── fixtures/                # 测试数据
│   ├── workspaces/         # 测试工作区
│   └── responses/          # 模拟响应
├── conftest.py             # pytest 配置
├── pytest.ini             # pytest 设置
├── playwright.config.ts    # Playwright 配置
└── run_tests.py            # 测试运行脚本
```

## 编写新测试

### 1. 创建页面对象方法

在相应的页面类中添加新方法：

```python
# 在 dashboard_page.py 中
def new_feature_method(self):
    """新功能测试方法"""
    self.click("[data-testid='new-feature-button']")
    self.wait_for_element("[data-testid='new-feature-dialog']")
```

### 2. 编写测试用例

```python
def test_new_feature(self, page: Page, sample_workspace):
    """测试新功能"""
    dashboard = DashboardPage(page)
    dashboard.navigate_to_dashboard()
    
    # 设置测试环境
    dashboard.select_workspace(sample_workspace["path"])
    
    # 测试新功能
    dashboard.new_feature_method()
    
    # 验证结果
    dashboard.assert_element_visible("[data-testid='new-feature-result']")
```

### 3. 使用标记

```python
@pytest.mark.smoke
@pytest.mark.dashboard
def test_important_feature(self):
    """重要的冒烟测试"""
    pass
```

## 模拟数据

### 1. AI 响应模拟

测试框架使用模拟的 AI 响应，避免依赖真实的 AI 服务：

```python
# 在 fixtures/responses/ 目录下
pm_response.json      # PM 响应模拟
director_response.json # Director 响应模拟
```

### 2. 工作区数据

```python
# 使用 fixture 创建测试工作区
@pytest.fixture
def sample_workspace():
    # 创建临时工作区
    # 返回工作区信息
    pass
```

## 持续集成

### GitHub Actions 配置示例

```yaml
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
      - name: Setup Node.js
        uses: actions/setup-node@v3
        with:
          node-version: '18'
      - name: Install dependencies
        run: |
          cd tests/e2e
          python run_tests.py install
      - name: Run tests
        run: |
          cd tests/e2e
          python run_tests.py test --type smoke
```

## 故障排除

### 常见问题

1. **浏览器安装失败**
   ```bash
   # 手动安装浏览器
   python -m playwright install chromium
   ```

2. **连接超时**
   ```bash
   # 确保 HarborPilot 应用正在运行
   # 检查环境变量 HARBORPILOT_TEST_BASE_URL
   ```

3. **元素定位失败**
   ```bash
   # 使用 --headed 模式调试
   python run_tests.py test --headed --type smoke
   ```

4. **权限问题**
   ```bash
   # 确保有写入权限
   chmod +x run_tests.py
   ```

### 获取帮助

1. 查看测试日志：`reports/report.html`
2. 检查截图：`reports/screenshots/`
3. 查看测试视频：`test-results/`
4. 启用详细日志：设置 `HARBORPILOT_LOG_LEVEL=DEBUG`

## 最佳实践

1. **使用页面对象模式**：封装页面交互逻辑
2. **保持测试独立**：每个测试用例应该独立运行
3. **合理使用等待**：避免硬编码等待时间
4. **添加适当的断言**：验证预期结果
5. **使用描述性名称**：让测试用例名称清晰明了
6. **定期维护**：及时更新测试用例和页面对象

## 扩展指南

1. **添加新的页面对象**：在 `pages/` 目录创建新文件
2. **集成新的测试工具**：在 `utils/` 目录添加工具函数
3. **添加新的测试类型**：在 `conftest.py` 中添加新的标记
4. **自定义报告**：修改 pytest 配置添加自定义报告器
