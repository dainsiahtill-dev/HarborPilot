import re
import time
from typing import List, Dict, Any, Optional, Pattern
from app.config import Settings

# Try to import cudf/cuml if available
try:
    import cudf # type: ignore
    import cuml # type: ignore
    RAPIDS_AVAILABLE = True
except ImportError:
    RAPIDS_AVAILABLE = False

try:
    import numpy as np
except ImportError:
    np = None

try:
    from sklearn.feature_extraction.text import TfidfVectorizer as SkTfidf
    from sklearn.manifold import TSNE
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False

class TurboEngine:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._regex_cache: Dict[str, Any] = {}

    @property
    def is_active(self) -> bool:
        """
        Check if Turbo Mode is enabled and dependencies are available.
        """
        return self.settings.gpu_turbo_mode and RAPIDS_AVAILABLE

    def find_all(self, pattern: str, text: str) -> List[str]:
        """
        Find all matches of a regex pattern in text.
        Falls back to CPU if Turbo unavailable or pattern not supported.
        """
        if not self.is_active:
            return re.findall(pattern, text)

        try:
            # GPU Acceleration using cuDF
            # Implementation: creating a Series and using str.findall
            # Note: This is efficient for LARGE texts or BATCHES.
            # For header matching single file, CPU might be faster due to overhead.
            # But we implement it for "Turbo" demonstration.
            
            # Optimization: Only use GPU for large texts (> 1MB)
            if len(text) < 1024 * 1024:
                return re.findall(pattern, text)

            s = cudf.Series([text])
            matches = s.str.findall(pattern)
            # Convert back to host list
            # matches is a Series of lists
            result = matches.to_pandas().tolist()[0]
            return result
        except Exception as e:
            # Fallback on error
            print(f"TurboEngine Error: {e}")
            return re.findall(pattern, text)

    def find_pattern_lines(self, lines: List[str], pattern: str) -> List[Tuple[int, str]]:
        """
        Find matches in lines using GPU. Returns list of (line_index_0_based, captured_group_str).
        Assumes pattern has exactly one capturing group.
        """
        if not self.is_active:
             # CPU Fallback
            results = []
            pat = re.compile(pattern)
            for i, line in enumerate(lines):
                 m = pat.search(line)
                 if m:
                     results.append((i, m.group(1)))
            return results

        try:
            # GPU Acceleration
            # Create Series from lines
            s = cudf.Series(lines)
            # Extract the group
            # str.extract returns a DataFrame where columns are groups
            extracted = s.str.extract(pattern)
            # We assume group 1 is column 0
            if extracted.shape[1] < 1:
                return []
            
            # Filter non-nulls (matches)
            # extracted[0] is the Series of the first group
            matches = extracted[0]
            valid_mask = matches.notnull()
            
            # Get indices and values
            valid_indices = valid_mask[valid_mask].index.to_pandas().tolist()
            valid_values = matches[valid_mask].to_pandas().tolist()
            
            return list(zip(valid_indices, valid_values))
        except Exception as e:
            print(f"TurboEngine find_pattern_lines error: {e}")
            # CPU Fallback
            results = []
            pat = re.compile(pattern)
            for i, line in enumerate(lines):
                 m = pat.search(line)
                 if m:
                     results.append((i, m.group(1)))
            return results

    def generate_project_map(self, file_contents: Dict[str, str]) -> List[Dict[str, Any]]:
        """
        Generate 3D coordinates for a set of files based on their content.
        Uses cuML UMAP if available, otherwise sklearn TSNE/PCA.
        """
        paths = list(file_contents.keys())
        texts = list(file_contents.values())
        
        if not texts:
            return []

        # GPU Path
        if self.is_active and RAPIDS_AVAILABLE:
            try:
                # 1. TF-IDF on GPU
                # cuML's TfidfVectorizer expects a cudf Series or list of strings
                tfidf = cuml.feature_extraction.text.TfidfVectorizer(max_features=1024)
                # Text usually needs to be on GPU for cuML? 
                # Actually cuML Tfidf accepts python list of strings too.
                matrix = tfidf.fit_transform(texts)
                
                # 2. UMAP Projection to 3D
                umap = cuml.manifold.UMAP(n_components=3, n_neighbors=15, min_dist=0.1)
                embedding = umap.fit_transform(matrix)
                
                # embedding is a cudf DataFrame or numpy array depending on input?
                # It returns a cupy array or cudf DataFrame.
                
                if hasattr(embedding, "to_pandas"):
                    points = embedding.to_pandas().values.tolist()
                elif hasattr(embedding, "get"): # cupy
                    points = embedding.get().tolist()
                else:
                    points = embedding.tolist() # fallback

                # 3. Clustering (HDBSCAN) for labels
                hdb = cuml.cluster.HDBSCAN(min_cluster_size=5)
                clusters = hdb.fit_predict(embedding)
                
                if hasattr(clusters, "to_pandas"):
                    labels = clusters.to_pandas().values.tolist()
                elif hasattr(clusters, "get"):
                    labels = clusters.get().tolist()
                else:
                    labels = clusters.tolist()

                results = []
                for i, path in enumerate(paths):
                    results.append({
                        "path": path,
                        "x": float(points[i][0]),
                        "y": float(points[i][1]),
                        "z": float(points[i][2]),
                        "cluster": int(labels[i])
                    })
                return results

            except Exception as e:
                print(f"TurboEngine GPU Visualization Error: {e}")
                # Fall through to CPU
        
        # CPU Fallback
        if SKLEARN_AVAILABLE and np:
             try:
                tfidf = SkTfidf(max_features=512, stop_words='english')
                matrix = tfidf.fit_transform(texts)
                
                # Use TSNE for 3D layout (or PCA for speed)
                reducer = TSNE(n_components=3, learning_rate='auto', init='random', perplexity=min(30, len(texts)-1))
                points = reducer.fit_transform(matrix)
                
                results = []
                for i, path in enumerate(paths):
                    results.append({
                        "path": path,
                        "x": float(points[i, 0]),
                        "y": float(points[i, 1]),
                        "z": float(points[i, 2]),
                        "cluster": 0 # HDBSCAN on CPU is extra dep, skip for fallback
                    })
                return results
             except Exception as e:
                 print(f"TurboEngine CPU Visualization Error: {e}")
        
        # Mock Fallback (if no sklearn)
        return self._mock_visualization(paths)

    def _mock_visualization(self, paths: List[str]) -> List[Dict[str, Any]]:
        import random
        results = []
        for path in paths:
            # Deterministic pseudo-random based on path
            seed = sum(ord(c) for c in path)
            random.seed(seed)
            results.append({
                "path": path,
                "x": random.uniform(-10, 10),
                "y": random.uniform(-10, 10),
                "z": random.uniform(-10, 10),
                "cluster": random.randint(0, 5)
            })
        return results

_engine: Optional[TurboEngine] = None

def get_turbo_engine(settings: Settings = None) -> Optional[TurboEngine]:
    global _engine
    if settings:
        if _engine is None:
            _engine = TurboEngine(settings)
        else:
            _engine.settings = settings
    return _engine

