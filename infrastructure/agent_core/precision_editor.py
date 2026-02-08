#!/usr/bin/env python3
"""
精确编辑器 - AST 与字符串替换的平衡实现
符合 AGENTS.md v2.2 规范的 S1 Patch 精确替换
"""

import os
import re
import ast
import subprocess
from pathlib import Path
from typing import Optional, Tuple, List

class PrecisionEditor:
    """精确编辑器 - 在安全性和实用性之间平衡"""
    
    def __init__(self):
        self.context_lines = 3  # 上下文行数
        self.backup_dir = Path("docs/temp/rollback")
        self.backup_dir.mkdir(parents=True, exist_ok=True)
    
    def should_use_string_replacement(self, file_path: str, change_type: str) -> bool:
        """判断是否应该使用字符串替换"""
        
        # S1 Patch 下的允许场景
        allowed_scenarios = [
            "simple_variable_rename",
            "import_statement_add", 
            "single_line_comment",
            "config_value_change",
            "function_signature_docstring"
        ]
        
        if change_type not in allowed_scenarios:
            return False
        
        # 检查文件复杂度
        if self._is_complex_file(file_path):
            return False
        
        return True
    
    def _is_complex_file(self, file_path: str) -> bool:
        """检查文件是否过于复杂"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 复杂度指标
            lines = content.split('\n')
            if len(lines) > 500:  # 文件过长
                return True
            
            # 检查嵌套深度
            try:
                tree = ast.parse(content)
                max_depth = self._calculate_ast_depth(tree)
                if max_depth > 10:  # 嵌套过深
                    return True
            except:
                # AST 解析失败，说明文件复杂
                return True
            
            return False
            
        except Exception:
            return True  # 保守策略：复杂时返回 True
    
    def _calculate_ast_depth(self, node, depth=0):
        """计算 AST 深度"""
        if not hasattr(node, 'body'):
            return depth
        
        max_child_depth = depth
        for child in ast.iter_child_nodes(node):
            child_depth = self._calculate_ast_depth(child, depth + 1)
            max_child_depth = max(max_child_depth, child_depth)
        
        return max_child_depth
    
    def precision_replace(self, file_path: str, old_pattern: str, new_text: str, 
                         context_validation: bool = True) -> Tuple[bool, str]:
        """精确替换 - 带上下文验证"""
        
        try:
            # 1. 创建备份
            backup_path = self._create_backup(file_path)
            
            # 2. 读取文件
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                lines = content.split('\n')
            
            # 3. 查找匹配位置
            matches = self._find_matches(lines, old_pattern)
            
            if len(matches) == 0:
                return False, "Pattern not found"
            if len(matches) > 1:
                return False, f"Multiple matches found ({len(matches)}), ambiguous"
            
            # 4. 上下文验证
            match_line = matches[0]
            if context_validation:
                if not self._validate_context(lines, match_line, old_pattern):
                    return False, "Context validation failed"
            
            # 5. 执行替换
            new_lines = lines.copy()
            new_lines[match_line] = new_lines[match_line].replace(old_pattern, new_text)
            
            # 6. 写入文件
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(new_lines))
            
            # 7. 后置质量门禁
            if not self._run_quality_gates(file_path):
                # 回滚
                self._restore_backup(file_path, backup_path)
                return False, "Quality gates failed, rolled back"
            
            return True, f"Replaced line {match_line + 1}"
            
        except Exception as e:
            return False, f"Error: {str(e)}"
    
    def _find_matches(self, lines: List[str], pattern: str) -> List[int]:
        """查找匹配的行"""
        matches = []
        
        for i, line in enumerate(lines):
            if pattern in line:
                # 更精确的匹配：确保不是注释或字符串中的内容
                if self._is_code_line(line, pattern):
                    matches.append(i)
        
        return matches
    
    def _is_code_line(self, line: str, pattern: str) -> bool:
        """检查是否是代码行（非注释）"""
        stripped = line.strip()
        
        # 跳过注释行
        if stripped.startswith('#') or stripped.startswith('//'):
            return False
        
        # 跳过字符串中的内容（简化检查）
        if '"' in line or "'" in line:
            # 更复杂的字符串检测可以在这里实现
            pass
        
        return True
    
    def _validate_context(self, lines: List[str], match_line: int, pattern: str) -> bool:
        """验证上下文"""
        start = max(0, match_line - self.context_lines)
        end = min(len(lines), match_line + self.context_lines + 1)
        
        context = lines[start:end]
        context_str = '\n'.join(context)
        
        # 检查上下文中是否有冲突的代码
        conflict_patterns = [
            r'def\s+\w+',  # 函数定义
            r'class\s+\w+',  # 类定义
            r'import\s+\w+',  # 导入语句
        ]
        
        for conflict_pattern in conflict_patterns:
            # 确保冲突模式不在同一上下文中
            if re.search(conflict_pattern, context_str) and pattern not in conflict_pattern:
                return False
        
        return True
    
    def _run_quality_gates(self, file_path: str) -> bool:
        """运行后置质量门禁"""
        
        # 根据文件类型选择检查工具
        if file_path.endswith('.py'):
            return self._run_python_quality_gates(file_path)
        elif file_path.endswith(('.ts', '.tsx', '.js', '.jsx')):
            return self._run_js_quality_gates(file_path)
        
        return True  # 其他文件类型跳过
    
    def _run_python_quality_gates(self, file_path: str) -> bool:
        """Python 质量门禁"""
        try:
            # ruff 检查
            result = subprocess.run(['ruff', 'check', file_path], 
                                  capture_output=True, text=True)
            if result.returncode != 0:
                print(f"Ruff check failed: {result.stderr}")
                return False
            
            # ruff 格式化
            result = subprocess.run(['ruff', 'format', file_path], 
                                  capture_output=True, text=True)
            if result.returncode != 0:
                print(f"Ruff format failed: {result.stderr}")
                return False
            
            return True
            
        except FileNotFoundError:
            print("Ruff not installed, skipping quality gates")
            return True  # 工具不存在时跳过
        except Exception as e:
            print(f"Quality gate error: {e}")
            return False
    
    def _run_js_quality_gates(self, file_path: str) -> bool:
        """JavaScript/TypeScript 质量门禁"""
        try:
            # eslint 检查
            result = subprocess.run(['npx', 'eslint', file_path], 
                                  capture_output=True, text=True)
            if result.returncode != 0:
                print(f"ESLint check failed: {result.stderr}")
                return False
            
            # prettier 格式化
            result = subprocess.run(['npx', 'prettier', '--write', file_path], 
                                  capture_output=True, text=True)
            if result.returncode != 0:
                print(f"Prettier format failed: {result.stderr}")
                return False
            
            return True
            
        except FileNotFoundError:
            print("ESLint/Prettier not installed, skipping quality gates")
            return True
        except Exception as e:
            print(f"Quality gate error: {e}")
            return False
    
    def _create_backup(self, file_path: str) -> Path:
        """创建备份"""
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        filename = Path(file_path).name
        backup_path = self.backup_dir / f"{timestamp}_{filename}"
        
        with open(file_path, 'r', encoding='utf-8') as src:
            with open(backup_path, 'w', encoding='utf-8') as dst:
                dst.write(src.read())
        
        return backup_path
    
    def _restore_backup(self, file_path: str, backup_path: Path):
        """恢复备份"""
        with open(backup_path, 'r', encoding='utf-8') as src:
            with open(file_path, 'w', encoding='utf-8') as dst:
                dst.write(src.read())


# 全局精确编辑器实例
precision_editor = PrecisionEditor()

# 导出的安全接口
def safe_precision_replace(file_path: str, old_pattern: str, new_text: str, 
                         change_type: str = "general") -> Tuple[bool, str]:
    """安全精确替换的统一接口"""
    
    # 检查是否应该使用字符串替换
    if not precision_editor.should_use_string_replacement(file_path, change_type):
        return False, "Change type not allowed for string replacement, use AST instead"
    
    return precision_editor.precision_replace(file_path, old_pattern, new_text)

if __name__ == "__main__":
    # 测试精确编辑器
    print("🔧 Testing precision editor...")
    
    # 创建测试文件
    test_file = "test_precision.py"
    with open(test_file, 'w') as f:
        f.write("""
# Test file for precision editing
import os

def hello_world():
    print("Hello, World!")
    return True

x = 42
""")
    
    # 测试替换
    success, message = safe_precision_replace(
        test_file, 
        'x = 42', 
        'x = 100',
        'simple_variable_rename'
    )
    
    print(f"Result: {success}, Message: {message}")
    
    # 清理
    if os.path.exists(test_file):
        os.remove(test_file)
