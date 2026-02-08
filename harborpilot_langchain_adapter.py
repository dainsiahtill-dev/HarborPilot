"""
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
