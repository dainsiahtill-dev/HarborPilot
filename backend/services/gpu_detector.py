import shutil
import sys
import subprocess
from typing import Dict, Any, List

def detect_gpus() -> Dict[str, Any]:
    """
    Detect NVIDIA GPUs and RAPIDS stack availability.
    Returns a capability report.
    """
    report = {
        "available": False,
        "count": 0,
        "devices": [],
        "driver_version": "unknown",
        "cuda_version": "unknown",
        "rapids_available": False,
        "error": None
    }

    # 1. Check for NVIDIA Driver via nvidia-smi
    smi_path = shutil.which("nvidia-smi")
    if not smi_path:
        report["error"] = "nvidia-smi not found"
        return report

    try:
        # Get driver version and CUDA version
        cmd = ["nvidia-smi", "--query-gpu=driver_version,name,memory.total,compute_cap", "--format=csv,noheader,nounits"]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        lines = result.stdout.strip().split("\n")
        
        devices = []
        for i, line in enumerate(lines):
            parts = [p.strip() for p in line.split(",")]
            if len(parts) >= 3:
                devices.append({
                    "index": i,
                    "name": parts[1],
                    "memory_total_mb": int(parts[2]),
                    "driver_version": parts[0],
                    "compute_cap": parts[3] if len(parts) > 3 else "unknown"
                })
        
        report["count"] = len(devices)
        report["devices"] = devices
        report["available"] = len(devices) > 0
        if devices:
            report["driver_version"] = devices[0]["driver_version"]

    except Exception as e:
        report["error"] = f"Failed to query nvidia-smi: {str(e)}"
        return report

    # 2. Check for RAPIDS (cudf)
    try:
        import cudf # type: ignore
        report["rapids_available"] = True
    except ImportError:
        report["rapids_available"] = False
        report["rapids_error"] = "cudf module not found"
    except Exception as e:
        report["rapids_available"] = False
        report["rapids_error"] = str(e)

    return report

if __name__ == "__main__":
    import json
    print(json.dumps(detect_gpus(), indent=2))
