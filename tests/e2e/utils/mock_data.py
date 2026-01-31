"""
Mock data generation for HarborPilot E2E tests
"""

import json
import random
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from faker import Faker
from loguru import logger


class MockDataGenerator:
    """Generate mock data for testing"""
    
    def __init__(self, locale: str = 'en_US'):
        self.fake = Faker(locale)
        self.fake.seed_instance(42)  # Ensure reproducible data
    
    # ================================
    # PM Tasks Mock Data
    # ================================
    
    def generate_pm_tasks(self, num_tasks: int = 3, run_id: Optional[str] = None) -> Dict[str, Any]:
        """Generate mock PM tasks"""
        if run_id is None:
            run_id = f"test_run_{self.fake.uuid4()[:8]}"
        
        tasks = []
        for i in range(num_tasks):
            task = {
                "id": f"task_{i + 1}",
                "fingerprint": self.fake.md5(),
                "title": self.generate_task_title(),
                "goal": self.generate_task_goal(),
                "constraints": self.generate_task_constraints(),
                "target_files": self.generate_target_files(),
                "acceptance": self.generate_acceptance_criteria(),
                "required_evidence": self.generate_required_evidence(),
                "policy_overrides": {}
            }
            tasks.append(task)
        
        return {
            "schema_version": 1,
            "run_id": run_id,
            "timestamp": self.fake.iso8601(),
            "pm_iteration": random.randint(1, 5),
            "focus": self.generate_focus_area(),
            "overall_goal": self.generate_overall_goal(),
            "policy_overrides": {},
            "tasks": tasks
        }
    
    def generate_task_title(self) -> str:
        """Generate task title"""
        titles = [
            "Set up project structure",
            "Implement user authentication",
            "Create data models",
            "Build API endpoints",
            "Add unit tests",
            "Implement error handling",
            "Create documentation",
            "Add logging functionality",
            "Optimize performance",
            "Add security features"
        ]
        return random.choice(titles)
    
    def generate_task_goal(self) -> str:
        """Generate task goal"""
        goals = [
            "Create a robust and scalable solution",
            "Ensure code quality and maintainability",
            "Implement best practices and patterns",
            "Provide a seamless user experience",
            "Ensure security and data protection",
            "Optimize for performance and reliability"
        ]
        return random.choice(goals)
    
    def generate_task_constraints(self) -> List[str]:
        """Generate task constraints"""
        all_constraints = [
            "Must follow Python coding standards",
            "Include comprehensive error handling",
            "Maintain backward compatibility",
            "Use existing libraries when possible",
            "Ensure test coverage above 80%",
            "Document all public APIs",
            "Follow security best practices",
            "Consider performance implications"
        ]
        return random.sample(all_constraints, random.randint(2, 4))
    
    def generate_target_files(self) -> List[str]:
        """Generate target file paths"""
        files = [
            "src/main.py",
            "src/auth.py",
            "src/models.py",
            "src/api.py",
            "tests/test_auth.py",
            "tests/test_models.py",
            "docs/api.md",
            "README.md",
            "requirements.txt",
            "setup.py"
        ]
        return random.sample(files, random.randint(1, 3))
    
    def generate_acceptance_criteria(self) -> List[str]:
        """Generate acceptance criteria"""
        criteria = [
            "All tests pass successfully",
            "Code follows style guidelines",
            "Documentation is complete",
            "Performance meets requirements",
            "Security audit passes",
            "Integration tests pass",
            "User acceptance testing approved",
            "Code review completed"
        ]
        return random.sample(criteria, random.randint(2, 4))
    
    def generate_required_evidence(self) -> List[str]:
        """Generate required evidence"""
        evidence = [
            "Unit test results",
            "Code coverage report",
            "Performance benchmarks",
            "Security scan results",
            "Documentation updates",
            "Code review comments",
            "Integration test results",
            "User feedback summary"
        ]
        return random.sample(evidence, random.randint(2, 3))
    
    def generate_focus_area(self) -> str:
        """Generate focus area"""
        areas = [
            "Backend Development",
            "Frontend Integration",
            "Database Design",
            "API Development",
            "Security Implementation",
            "Performance Optimization",
            "Testing Infrastructure",
            "Documentation"
        ]
        return random.choice(areas)
    
    def generate_overall_goal(self) -> str:
        """Generate overall goal"""
        goals = [
            "Build a complete and production-ready application",
            "Implement core functionality with high quality",
            "Create a scalable and maintainable codebase",
            "Deliver a robust user experience",
            "Ensure security and reliability"
        ]
        return random.choice(goals)
    
    # ================================
    # Director Result Mock Data
    # ================================
    
    def generate_director_result(self, run_id: Optional[str] = None, status: str = "success") -> Dict[str, Any]:
        """Generate mock Director result"""
        if run_id is None:
            run_id = f"test_run_{self.fake.uuid4()[:8]}"
        
        return {
            "schema_version": 1,
            "run_id": run_id,
            "timestamp": self.fake.iso8601(),
            "status": status,
            "failure_code": None if status == "success" else self.generate_failure_code(),
            "patch_risk": self.generate_patch_risk(),
            "execution_summary": self.generate_execution_summary(status),
            "artifacts": self.generate_artifacts(),
            "metrics": self.generate_metrics()
        }
    
    def generate_failure_code(self) -> str:
        """Generate failure code"""
        codes = ["QA_FAIL", "RISK_BLOCKED", "POLICY_BLOCKED", "TOOL_BUDGET_EXCEEDED", "PLANNER_FAILURE"]
        return random.choice(codes)
    
    def generate_patch_risk(self) -> Dict[str, Any]:
        """Generate patch risk assessment"""
        return {
            "score": random.randint(0, 100),
            "factors": {
                "files_changed_count": random.randint(1, 10),
                "lines_added": random.randint(10, 500),
                "lines_removed": random.randint(0, 100),
                "touches_build_system": random.choice([True, False]),
                "touches_security_sensitive": random.choice([True, False]),
                "touches_runtime_entry": random.choice([True, False])
            }
        }
    
    def generate_execution_summary(self, status: str) -> Dict[str, Any]:
        """Generate execution summary"""
        return {
            "total_duration_ms": random.randint(5000, 60000),
            "tool_rounds": random.randint(1, 6),
            "files_modified": random.randint(1, 8),
            "tests_run": random.randint(5, 50),
            "tests_passed": random.randint(4, 50) if status == "success" else random.randint(0, 20),
            "errors": [] if status == "success" else [self.generate_error_message()]
        }
    
    def generate_artifacts(self) -> List[str]:
        """Generate artifact paths"""
        artifacts = [
            ".harborpilot/runtime/RUNLOG.md",
            ".harborpilot/runtime/QA_RESPONSE.md",
            ".harborpilot/runtime/REVIEW_RESPONSE.md",
            ".harborpilot/runtime/events.jsonl",
            ".harborpilot/runtime/trajectory.json"
        ]
        return random.sample(artifacts, random.randint(2, 5))
    
    def generate_metrics(self) -> Dict[str, Any]:
        """Generate execution metrics"""
        return {
            "cpu_usage_percent": random.uniform(10, 90),
            "memory_usage_mb": random.randint(100, 1000),
            "disk_io_mb": random.randint(1, 100),
            "network_requests": random.randint(0, 50)
        }
    
    def generate_error_message(self) -> str:
        """Generate error message"""
        errors = [
            "Test suite failed: 3 tests failing",
            "Code quality check failed: ruff issues found",
            "Type checking failed: mypy errors detected",
            "Build failed: compilation errors",
            "Security scan failed: vulnerabilities found"
        ]
        return random.choice(errors)
    
    # ================================
    # Dialogue Mock Data
    # ================================
    
    def generate_dialogue_history(self, num_entries: int = 5) -> List[Dict[str, Any]]:
        """Generate mock dialogue history"""
        dialogue = []
        speakers = ["PM", "Director", "QA", "System"]
        types = ["handoff", "receipt", "say", "done"]
        
        base_time = datetime.now()
        for i in range(num_entries):
            entry = {
                "timestamp": (base_time + timedelta(minutes=i*5)).isoformat(),
                "speaker": random.choice(speakers),
                "type": random.choice(types),
                "content": self.generate_dialogue_content()
            }
            dialogue.append(entry)
        
        return dialogue
    
    def generate_dialogue_content(self) -> str:
        """Generate dialogue content"""
        contents = [
            "Starting task execution",
            "Task completed successfully",
            "Running quality checks",
            "Analyzing requirements",
            "Generating implementation plan",
            "Executing code changes",
            "Running tests",
            "Reviewing results",
            "Preparing final report",
            "Workflow completed"
        ]
        return random.choice(contents)
    
    # ================================
    # Workspace Mock Data
    # ================================
    
    def generate_workspace_info(self, workspace_type: str = "python") -> Dict[str, Any]:
        """Generate mock workspace information"""
        return {
            "name": f"test_project_{self.fake.slug()}",
            "path": f"/tmp/test_workspaces/{self.fake.slug()}",
            "type": workspace_type,
            "size": random.randint(1000, 100000),
            "file_count": random.randint(10, 100),
            "last_modified": self.fake.date_time_this_year().isoformat(),
            "has_docs": random.choice([True, False]),
            "has_requirements": random.choice([True, False]),
            "has_tests": random.choice([True, False])
        }
    
    def generate_file_tree(self, depth: int = 3, files_per_dir: int = 5) -> List[Dict[str, Any]]:
        """Generate mock file tree"""
        def generate_tree(current_depth: int, current_path: str = "") -> List[Dict[str, Any]]:
            if current_depth <= 0:
                return []
            
            tree = []
            
            # Add files
            for i in range(random.randint(1, files_per_dir)):
                file_name = f"{self.fake.word()}.{'py' if random.random() > 0.3 else 'md'}"
                file_path = f"{current_path}/{file_name}" if current_path else file_name
                
                tree.append({
                    "name": file_name,
                    "path": file_path,
                    "type": "file",
                    "size": random.randint(100, 10000),
                    "modified": self.fake.date_time_this_year().isoformat(),
                    "is_directory": False
                })
            
            # Add subdirectories
            if current_depth > 1:
                for i in range(random.randint(0, 2)):
                    dir_name = self.fake.word()
                    dir_path = f"{current_path}/{dir_name}" if current_path else dir_name
                    
                    tree.append({
                        "name": dir_name,
                        "path": dir_path,
                        "type": "directory",
                        "size": 0,
                        "modified": self.fake.date_time_this_year().isoformat(),
                        "is_directory": True,
                        "children": generate_tree(current_depth - 1, dir_path)
                    })
            
            return tree
        
        return generate_tree(depth)
    
    # ================================
    # QA Response Mock Data
    # ================================
    
    def generate_qa_response(self, passed: bool = True) -> Dict[str, Any]:
        """Generate mock QA response"""
        return {
            "timestamp": self.fake.iso8601(),
            "passed": passed,
            "summary": "All tests passed successfully" if passed else "Some tests failed",
            "test_results": self.generate_test_results(passed),
            "coverage": {
                "percentage": random.randint(70, 95) if passed else random.randint(30, 70),
                "lines_covered": random.randint(100, 1000),
                "total_lines": random.randint(200, 1200)
            },
            "issues": [] if passed else [self.generate_issue()],
            "recommendations": self.generate_recommendations(passed)
        }
    
    def generate_test_results(self, passed: bool) -> Dict[str, Any]:
        """Generate test results"""
        total_tests = random.randint(10, 50)
        passed_tests = total_tests if passed else random.randint(0, total_tests - 1)
        failed_tests = total_tests - passed_tests
        
        return {
            "total": total_tests,
            "passed": passed_tests,
            "failed": failed_tests,
            "skipped": random.randint(0, 5),
            "errors": random.randint(0, 2) if not passed else 0
        }
    
    def generate_issue(self) -> Dict[str, Any]:
        """Generate QA issue"""
        severities = ["low", "medium", "high", "critical"]
        types = ["bug", "performance", "security", "style", "documentation"]
        
        return {
            "type": random.choice(types),
            "severity": random.choice(severities),
            "description": self.fake.sentence(),
            "file": f"src/{self.fake.word()}.py",
            "line": random.randint(1, 100),
            "suggestion": self.fake.sentence()
        }
    
    def generate_recommendations(self, passed: bool) -> List[str]:
        """Generate recommendations"""
        if passed:
            return [
                "Code quality is good",
                "Consider adding more edge case tests",
                "Documentation is comprehensive"
            ]
        else:
            return [
                "Fix failing tests before proceeding",
                "Improve code coverage",
                "Address security vulnerabilities",
                "Refactor complex functions"
            ]
    
    # ================================
    # Save and Load Methods
    # ================================
    
    def save_pm_tasks(self, tasks: Dict[str, Any], file_path: str) -> None:
        """Save PM tasks to file"""
        with open(file_path, 'w') as f:
            json.dump(tasks, f, indent=2)
        logger.info(f"Saved PM tasks to {file_path}")
    
    def save_director_result(self, result: Dict[str, Any], file_path: str) -> None:
        """Save Director result to file"""
        with open(file_path, 'w') as f:
            json.dump(result, f, indent=2)
        logger.info(f"Saved Director result to {file_path}")
    
    def save_dialogue_history(self, dialogue: List[Dict[str, Any]], file_path: str) -> None:
        """Save dialogue history to file"""
        with open(file_path, 'w') as f:
            for entry in dialogue:
                f.write(json.dumps(entry) + '\n')
        logger.info(f"Saved dialogue history to {file_path}")
    
    def load_pm_tasks(self, file_path: str) -> Dict[str, Any]:
        """Load PM tasks from file"""
        with open(file_path, 'r') as f:
            return json.load(f)
    
    def load_director_result(self, file_path: str) -> Dict[str, Any]:
        """Load Director result from file"""
        with open(file_path, 'r') as f:
            return json.load(f)


# Global instance
mock_generator = MockDataGenerator()


# Convenience functions
def generate_pm_tasks(num_tasks: int = 3, run_id: Optional[str] = None) -> Dict[str, Any]:
    """Generate mock PM tasks"""
    return mock_generator.generate_pm_tasks(num_tasks, run_id)


def generate_director_result(run_id: Optional[str] = None, status: str = "success") -> Dict[str, Any]:
    """Generate mock Director result"""
    return mock_generator.generate_director_result(run_id, status)


def generate_dialogue_history(num_entries: int = 5) -> List[Dict[str, Any]]:
    """Generate mock dialogue history"""
    return mock_generator.generate_dialogue_history(num_entries)


def generate_workspace_info(workspace_type: str = "python") -> Dict[str, Any]:
    """Generate mock workspace information"""
    return mock_generator.generate_workspace_info(workspace_type)


def generate_qa_response(passed: bool = True) -> Dict[str, Any]:
    """Generate mock QA response"""
    return mock_generator.generate_qa_response(passed)
