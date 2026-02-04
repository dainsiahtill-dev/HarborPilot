import logging
import subprocess
import shutil
import tempfile
import os
import json
from typing import Dict, Any, List, Optional

logger = logging.getLogger("app.services.quality_service")

class QualityService:
    def __init__(self):
        self.ruff_executable = shutil.which("ruff")
        self.available = self.ruff_executable is not None

    def lint_code(self, code: str, extension: str = ".py", fix: bool = False) -> Dict[str, Any]:
        """
        Runs Ruff on the provided code.
        Returns lint errors or fixed code.
        """
        if not self.available or extension != ".py":
            return {"success": False, "reason": "ruff_missing_or_not_python"}
        
        try:
            with tempfile.NamedTemporaryFile(mode="w", suffix=extension, delete=False, encoding="utf-8") as tmp:
                tmp.write(code)
                tmp_path = tmp.name

            cmd = [self.ruff_executable, "check", tmp_path, "--output-format", "json"]
            if fix:
                cmd.append("--fix")

            # Run Ruff
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            # Read back file if satisfied
            fixed_code = None
            if fix:
                with open(tmp_path, "r", encoding="utf-8") as f:
                    fixed_code = f.read()

            os.unlink(tmp_path)

            lints = []
            if result.stdout:
                try:
                    lints = json.loads(result.stdout)
                except json.JSONDecodeError:
                    pass

            return {
                "success": True,
                "lints": lints,
                "fixed_code": fixed_code if fix else None
            }
        except Exception as e:
            logger.error(f"Ruff execution failed: {e}")
            return {"success": False, "error": str(e)}

    def get_status(self):
        return {
            "available": self.available,
            "path": self.ruff_executable
        }

_service = QualityService()

def get_quality_service() -> QualityService:
    return _service
