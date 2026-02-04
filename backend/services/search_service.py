import logging
from typing import Dict, Any, List, Optional

try:
    import tantivy
    TANTIVY_AVAILABLE = True
except ImportError:
    TANTIVY_AVAILABLE = False

logger = logging.getLogger("app.services.search_service")

class SearchService:
    def __init__(self):
        self.available = TANTIVY_AVAILABLE
        self.index = None
        self.schema = None
        
        if self.available:
            self._init_index()

    def _init_index(self):
        try:
            # Simple schema: title, body, path
            self.schema_builder = tantivy.SchemaBuilder()
            self.schema_builder.add_text_field("body", stored=False)
            self.schema_builder.add_text_field("path", stored=True)
            self.schema = self.schema_builder.build()
            # RAM-based index for now
            self.index = tantivy.Index(self.schema)
            self.writer = self.index.writer()
            logger.info("Tantivy Index initialized in RAM.")
        except Exception as e:
            logger.error(f"Failed to init Tantivy: {e}")
            self.available = False

    def add_documents(self, docs: List[Dict[str, str]]):
        """
        Adds documents to the index.
        Docs list of dicts with 'path', 'body'.
        """
        if not self.available or not self.index:
            return
        
        try:
            for doc in docs:
                self.writer.add_document(tantivy.Document(
                    path=doc.get("path", ""),
                    body=doc.get("body", "")
                ))
            self.writer.commit()
        except Exception as e:
            logger.error(f"Failed to add docs to Tantivy: {e}")

    def search(self, query_str: str, limit: int = 10) -> List[Dict[str, Any]]:
        if not self.available or not self.index:
            return []

        try:
            self.index.reload()
            query = self.index.parse_query(query_str, ["body"])
            searcher = self.index.searcher()
            result = searcher.search(query, limit)
            
            hits = []
            for score, doc_address in result.hits:
                doc = searcher.doc(doc_address)
                hits.append({
                    "score": score,
                    "path": doc["path"][0]
                })
            return hits
        except Exception as e:
            logger.warning(f"Tantivy search error: {e}")
            return []

_service = SearchService()

def get_search_service() -> SearchService:
    return _service
