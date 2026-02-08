import logging
import asyncio
from typing import Optional, Any, Dict
from threading import Lock

# Optional Dask/CUDA imports
try:
    from dask_cuda import LocalCUDACluster
    from distributed import Client
    DASK_AVAILABLE = True
except ImportError:
    DASK_AVAILABLE = False
    LocalCUDACluster = None
    Client = None

logger = logging.getLogger("app.services.turbo_scheduler")

class TurboScheduler:
    _instance = None
    _lock = Lock()

    def __init__(self):
        self.cluster = None
        self.client = None
        self.is_active = False
        self._setup_done = False

    @classmethod
    def get_instance(cls):
        if not cls._instance:
            with cls._lock:
                if not cls._instance:
                    cls._instance = cls()
        return cls._instance

    async def start(self, enable_cuda: bool = True):
        """Starts the Dask scheduler. If CUDA is requested but unavailable, logs warning."""
        if self.is_active:
            return

        if enable_cuda and DASK_AVAILABLE:
            try:
                # Assuming dual 3090 Ti setup or similar, LocalCUDACluster auto-detects
                logger.info("Initializing Dask-CUDA Cluster...")
                self.cluster = LocalCUDACluster(
                    dashboard_address=":8787", # Expose dashboard
                    rmm_pool_size="4GB" # Managed memory pool
                )
                self.client = Client(self.cluster)
                self.is_active = True
                logger.info(f"Dask Cluster started: {self.client.dashboard_link}")
            except Exception as e:
                logger.error(f"Failed to start Dask-CUDA cluster: {e}")
                self.is_active = False
        else:
            if enable_cuda and not DASK_AVAILABLE:
                logger.warning("Dask/CUDA libraries not found. Skipping scheduler start.")
    
    async def stop(self):
        if self.client:
            await self.client.close()
            self.client = None
        if self.cluster:
            try:
                self.cluster.close()
            except OSError:
                pass # Sync close might fail in async context depending on version
            self.cluster = None
        self.is_active = False
        logger.info("Dask Cluster stopped.")

    def get_status(self) -> Dict[str, Any]:
        return {
            "active": self.is_active,
            "dask_available": DASK_AVAILABLE,
            "dashboard_link": self.client.dashboard_link if self.client else None,
            "workers": len(self.client.scheduler_info()['workers']) if self.client else 0
        }

    def submit_job(self, func, *args, **kwargs):
        """Submits a job to the cluster if active, else raises error or falls back."""
        if not self.is_active or not self.client:
            raise RuntimeError("Dask Cluster is not active")
        return self.client.submit(func, *args, **kwargs)

    def map_job(self, func, iterable, **kwargs):
        if not self.is_active or not self.client:
             raise RuntimeError("Dask Cluster is not active")
        return self.client.map(func, iterable, **kwargs)

def get_scheduler() -> TurboScheduler:
    return TurboScheduler.get_instance()
