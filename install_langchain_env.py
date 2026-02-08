#!/usr/bin/env python3
"""
HarborPilot LangChain 环境自动安装脚本
运行: python install_langchain_env.py
"""

import subprocess
import sys
import os
from pathlib import Path

def run_command(cmd, description, check=True):
    """执行命令并处理结果"""
    print(f"\n🔧 {description}")
    print(f"   命令: {cmd}")
    
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, check=check)
        if result.stdout.strip():
            print(f"✅ 成功: {result.stdout.strip()}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ 失败: {e.stderr.strip() if e.stderr else str(e)}")
        return False

def check_python_version():
    """检查 Python 版本"""
    version = sys.version_info
    print(f"🐍 Python 版本: {version.major}.{version.minor}.{version.micro}")
    
    if version.major < 3 or (version.major == 3 and version.minor < 8):
        print("❌ 需要 Python 3.8 或更高版本")
        return False
    
    print("✅ Python 版本符合要求")
    return True

def get_pip_command():
    """获取 pip 命令"""
    # 直接使用全局 pip
    if os.name == 'nt':  # Windows
        pip_cmd = "pip"
    else:  # Linux/Mac
        pip_cmd = "pip3"
    
    return pip_cmd

def get_python_command():
    """获取 python 命令"""
    # 直接使用全局 python
    if os.name == 'nt':  # Windows
        python_cmd = "python"
    else:  # Linux/Mac
        python_cmd = "python3"
    
    return python_cmd

def install_core_packages():
    """安装核心包"""
    pip_cmd = get_pip_command()
    
    packages = [
        "langchain>=0.1.0",
        "langchain-core>=0.1.0", 
        "langchain-community>=0.0.10",
        "python-dotenv>=1.0.0"
    ]
    
    print("\n📦 安装 LangChain 核心包...")
    
    for package in packages:
        success = run_command(f"{pip_cmd} install {package}", f"安装 {package}")
        if not success:
            print(f"❌ {package} 安装失败")
            return False
    
    print("✅ 核心包安装完成")
    return True

def install_ai_integrations():
    """安装 AI 模型集成"""
    pip_cmd = get_pip_command()
    
    integrations = [
        "langchain-openai>=0.0.5",
        "langchain-anthropic>=0.0.1",
        "openai>=1.0.0"
    ]
    
    print("\n🤖 安装 AI 模型集成...")
    
    for integration in integrations:
        success = run_command(f"{pip_cmd} install {integration}", f"安装 {integration}")
        # 不强制要求所有集成都成功
    
    print("✅ AI 集成安装完成")
    return True

def install_vector_stores():
    """安装向量存储"""
    pip_cmd = get_pip_command()
    
    vector_stores = [
        "faiss-cpu>=1.7.0",
        "sentence-transformers>=2.2.0"
    ]
    
    print("\n🔍 安装向量存储...")
    
    for store in vector_stores:
        success = run_command(f"{pip_cmd} install {store}", f"安装 {store}")
        if not success:
            print(f"⚠️ {store} 安装失败，可能需要手动安装")
    
    print("✅ 向量存储安装完成")
    return True

def install_tools():
    """安装工具包"""
    pip_cmd = get_pip_command()
    
    tools = [
        "duckduckgo-search>=3.9.0",
        "wikipedia>=1.4.0",
        "requests>=2.28.0",
        "beautifulsoup4>=4.12.0",
        "pandas>=1.5.0",
        "numpy>=1.24.0"
    ]
    
    print("\n🛠️ 安装工具包...")
    
    for tool in tools:
        success = run_command(f"{pip_cmd} install {tool}", f"安装 {tool}")
        if not success:
            print(f"⚠️ {tool} 安装失败")
    
    print("✅ 工具包安装完成")
    return True

def create_requirements_file():
    """创建 requirements 文件"""
    requirements_content = """# LangChain 核心
langchain>=0.1.0
langchain-core>=0.1.0
langchain-community>=0.0.10

# AI 模型集成
langchain-openai>=0.0.5
langchain-anthropic>=0.0.1
openai>=1.0.0

# 向量存储和检索
faiss-cpu>=1.7.0
sentence-transformers>=2.2.0

# 工具和 API
duckduckgo-search>=3.9.0
wikipedia>=1.4.0
requests>=2.28.0
beautifulsoup4>=4.12.0

# 数据处理
pandas>=1.5.0
numpy>=1.24.0

# 环境配置
python-dotenv>=1.0.0
"""
    
    with open("requirements_langchain.txt", "w", encoding="utf-8") as f:
        f.write(requirements_content)
    
    print("✅ 创建 requirements_langchain.txt")

def create_env_template():
    """创建环境变量模板"""
    env_template = """# LangChain 环境配置
# 复制此文件为 .env 并填入你的 API 密钥

# OpenAI API 密钥 (可选)
OPENAI_API_KEY=your_openai_key_here

# Anthropic API 密钥 (可选)
ANTHROPIC_API_KEY=your_anthropic_key_here

# LangSmith 调试 (可选)
LANGCHAIN_TRACING_V2=false
LANGCHAIN_API_KEY=your_langsmith_key_here
"""
    
    with open(".env.template", "w", encoding="utf-8") as f:
        f.write(env_template)
    
    print("✅ 创建 .env.template")

def create_harborpilot_adapter():
    """创建 HarborPilot LangChain 适配器"""
    adapter_code = '''"""
HarborPilot LangChain 适配器
符合 AGENTS_V22.md 规范的 LangChain 集成
"""

import os
from typing import Dict, Any, Optional, List
from datetime import datetime

class HarborPilotLangChainAdapter:
    """HarborPilot 专用的 LangChain 适配器"""
    
    def __init__(self):
        self.env_status = self._check_environment()
        self.usage_monitor = UsageMonitor()
        
    def _check_environment(self) -> Dict[str, bool]:
        """检查 LangChain 环境是否就绪"""
        status = {}
        
        # 检查核心包
        try:
            import langchain
            status["langchain"] = True
        except ImportError:
            status["langchain"] = False
        
        # 检查工具
        try:
            from langchain.tools import DuckDuckGoSearchRun
            status["search_tool"] = True
        except ImportError:
            status["search_tool"] = False
        
        # 检查向量存储
        try:
            import faiss
            status["faiss"] = True
        except ImportError:
            status["faiss"] = False
        
        # 检查 API 密钥
        status["openai_key"] = bool(os.getenv("OPENAI_API_KEY"))
        status["anthropic_key"] = bool(os.getenv("ANTHROPIC_API_KEY"))
        
        return status
    
    def can_handle_task(self, task_analysis: Dict[str, Any]) -> bool:
        """判断是否可以使用 LangChain 处理任务"""
        if not self.env_status["langchain"]:
            return False
        
        # 根据任务类型判断
        if task_analysis.get("requires_multi_step_reasoning"):
            return True
        if task_analysis.get("involves_external_apis"):
            return True
        if task_analysis.get("needs_vector_search"):
            return True
        
        return False
    
    def execute_with_evidence(self, operation: str, inputs: Any) -> Dict[str, Any]:
        """执行操作并生成证据"""
        start_time = datetime.utcnow()
        
        try:
            # 执行 LangChain 操作
            result = self._execute_operation(operation, inputs)
            
            # 生成证据
            evidence = {
                "framework": "langchain",
                "operation": operation,
                "success": True,
                "execution_time_ms": (datetime.utcnow() - start_time).total_seconds() * 1000,
                "result_summary": str(result)[:200],  # 前200字符摘要
                "evidence_type": "external_framework_call"
            }
            
            # 记录使用情况
            self.usage_monitor.track_usage(operation, evidence["execution_time_ms"], True)
            
            return {
                "result": result,
                "evidence": evidence
            }
            
        except Exception as e:
            # 失败证据
            evidence = {
                "framework": "langchain",
                "operation": operation,
                "success": False,
                "error": str(e),
                "execution_time_ms": (datetime.utcnow() - start_time).total_seconds() * 1000,
                "evidence_type": "framework_failure"
            }
            
            self.usage_monitor.track_usage(operation, evidence["execution_time_ms"], False)
            
            return {
                "result": None,
                "evidence": evidence,
                "error": e
            }
    
    def _execute_operation(self, operation: str, inputs: Any) -> Any:
        """执行具体的 LangChain 操作"""
        if operation == "search":
            return self._search_operation(inputs)
        elif operation == "reasoning":
            return self._reasoning_operation(inputs)
        else:
            raise ValueError(f"Unsupported operation: {operation}")
    
    def _search_operation(self, query: str) -> str:
        """搜索操作"""
        from langchain.tools import DuckDuckGoSearchRun
        search = DuckDuckGoSearchRun()
        return search.run(query)
    
    def _reasoning_operation(self, prompt: str) -> str:
        """推理操作"""
        if not self.env_status["openai_key"]:
            raise RuntimeError("OpenAI API key required for reasoning")
        
        from langchain.llms import OpenAI
        llm = OpenAI(temperature=0)
        return llm(prompt)


class UsageMonitor:
    """LangChain 使用监控"""
    
    def __init__(self):
        self.usage_log = []
    
    def track_usage(self, operation: str, duration_ms: float, success: bool):
        """记录使用情况"""
        log_entry = {
            "operation": operation,
            "duration_ms": duration_ms,
            "success": success,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        self.usage_log.append(log_entry)
        
        # 检查是否过度使用
        if len(self.usage_log) > 10:  # 最近10次调用
            recent_failures = sum(1 for entry in self.usage_log[-10:] if not entry["success"])
            if recent_failures > 5:  # 失败率过高
                print("⚠️ 警告: LangChain 失败率过高，建议回退到原生工具")


def test_installation():
    """测试安装"""
    print("🧪 测试 LangChain 安装...")
    
    try:
        adapter = HarborPilotLangChainAdapter()
        print(f"📊 环境状态: {adapter.env_status}")
        
        # 测试搜索功能
        if adapter.env_status["search_tool"]:
            result = adapter.execute_with_evidence("search", "Python programming")
            if result["evidence"]["success"]:
                print("✅ 搜索功能测试通过")
            else:
                print("❌ 搜索功能测试失败")
        
        return True
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        return False


if __name__ == "__main__":
    test_installation()
'''
    
    with open("harborpilot_langchain_adapter.py", "w", encoding="utf-8") as f:
        f.write(adapter_code)
    
    print("✅ 创建 harborpilot_langchain_adapter.py")

def create_activation_script():
    """创建使用说明脚本"""
    readme_content = '''# HarborPilot LangChain 全局环境使用说明

## 安装状态
✅ LangChain 已安装到全局 Python 环境
✅ AI Agent 可以直接使用 LangChain 功能

## 快速测试
```bash
python harborpilot_langchain_adapter.py
```

## 配置 API 密钥 (可选)
如果需要使用 OpenAI 或 Anthropic 模型:

1. 复制环境变量模板:
   ```bash
   copy .env.template .env
   ```

2. 编辑 .env 文件，填入你的 API 密钥

## AI Agent 使用
AI Agent 现在可以根据 AGENTS_V22.md 规范直接使用 LangChain:

- 复杂推理任务
- 外部 API 调用  
- 向量检索
- 多步骤处理

## 卸载 (如需要)
```bash
pip uninstall langchain langchain-core langchain-community
```
'''
    
    with open("LANGCHAIN_SETUP_README.md", "w", encoding="utf-8") as f:
        f.write(readme_content)
    
    print("✅ 创建 LANGCHAIN_SETUP_README.md")

def run_final_test():
    """运行最终测试"""
    python_cmd = get_python_command()
    
    print("\n🧪 运行最终测试...")
    success = run_command(f"{python_cmd} harborpilot_langchain_adapter.py", "测试安装", check=False)
    
    return success

def main():
    """主安装流程"""
    print("🚀 HarborPilot LangChain 环境安装 (全局环境)")
    print("=" * 50)
    print("⚠️  注意: 将直接安装到全局 Python 环境")
    print("   这样 AI Agent 可以直接使用 LangChain 功能")
    print("=" * 50)
    
    # 1. 检查 Python 版本
    if not check_python_version():
        return False
    
    # 2. 安装核心包
    if not install_core_packages():
        return False
    
    # 3. 安装 AI 集成
    install_ai_integrations()
    
    # 4. 安装向量存储
    install_vector_stores()
    
    # 5. 安装工具
    install_tools()
    
    # 6. 创建配置文件
    create_requirements_file()
    create_env_template()
    create_harborpilot_adapter()
    
    # 7. 运行测试
    run_final_test()
    
    print("\n" + "=" * 50)
    print("✅ 全局环境安装完成！")
    print("\n📋 后续步骤:")
    print("1. 复制 .env.template 为 .env 并填入 API 密钥 (可选)")
    print("2. 运行 python harborpilot_langchain_adapter.py 测试功能")
    print("3. AI Agent 现在可以直接使用 LangChain 功能")
    print("\n📖 更多信息请查看 AGENTS_V22.md")
    
    return True

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n❌ 安装被用户中断")
    except Exception as e:
        print(f"\n❌ 安装过程中出现错误: {e}")
        sys.exit(1)
