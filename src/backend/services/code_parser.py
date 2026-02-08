import logging
from typing import Dict, Any, List, Optional
import os

try:
    from tree_sitter import Language, Parser
    # Note: Modern tree-sitter setups might require building languages or using bindings
    # asking user to install `tree-sitter` and `tree-sitter-languages` simplifies this
    import tree_sitter_languages
    TREE_SITTER_AVAILABLE = True
except ImportError:
    TREE_SITTER_AVAILABLE = False

logger = logging.getLogger("app.services.code_parser")

class CodeParser:
    def __init__(self):
        self.available = TREE_SITTER_AVAILABLE
        self.parsers = {}

    def get_parser(self, lang_name: str) -> Optional[Any]:
        if not self.available:
            return None
        
        if lang_name not in self.parsers:
            try:
                parser = Parser()
                language = tree_sitter_languages.get_language(lang_name)
                parser.set_language(language)
                self.parsers[lang_name] = parser
            except Exception as e:
                logger.warning(f"Failed to load tree-sitter language {lang_name}: {e}")
                return None
        return self.parsers.get(lang_name)

    def parse_file(self, content: str, extension: str) -> Dict[str, Any]:
        """
        Parses code content and returns AST-based metadata.
        Falls back to basic stats if tree-sitter missing.
        """
        lang_map = {
            ".py": "python",
            ".ts": "typescript",
            ".tsx": "tsx",
            ".js": "javascript",
            ".rs": "rust",
            ".go": "go",
            ".cpp": "cpp",
            ".c": "c"
        }
        
        lang = lang_map.get(extension)
        if not lang or not self.available:
            return {"parsed": False, "reason": "unsupported_or_missing_lib"}

        parser = self.get_parser(lang)
        if not parser:
             return {"parsed": False, "reason": "parser_init_failed"}

        try:
            tree = parser.parse(bytes(content, "utf8"))
            root = tree.root_node
            
            # Basic extraction (e.g. counting functions)
            # This is a stub for more complex logic (walking the tree)
            # In a real impl, we would use queries to find function_definition
            
            return {
                "parsed": True,
                "language": lang,
                "node_type": root.type,
                "child_count": root.child_count,
                # "sexp": root.sexp() # S-expression string
            }
        except Exception as e:
            logger.error(f"Tree-sitter parse error: {e}")
            return {"parsed": False, "error": str(e)}

_parser = CodeParser()

def get_code_parser() -> CodeParser:
    return _parser
