# HarborPilot Tools Inventory

**Purpose**: Provide a unified catalog of pre-installed tools for Director automation, facilitating planning, execution, and QA workflows.  
**Note**: These tools are pre-installed in the local environment and do not require Director to install via pip.

---

## 1. Code Quality & Formatting

### ruff
- **Function**: Ultra-fast linting and formatting with auto-fix capabilities
- **Features**: High speed, comprehensive rule coverage, ideal for quick regression after batch changes
- **Purpose**: Improve code consistency and reduce style-related issues
- **Examples**:
  ```bash
  ruff check .
  ruff format .
  ```

---

## 2. Testing & Coverage

### pytest
- **Function**: Mainstream Python testing framework
- **Features**: Rich ecosystem, clear assertions
- **Purpose**: Verify correctness of changes
- **Example**: `pytest`

### coverage
- **Function**: Test coverage statistics
- **Features**: Generates text/HTML reports
- **Purpose**: Evaluate test quality
- **Example**: `coverage run -m pytest && coverage report -m`

---

## 3. Static Type Checking

### mypy
- **Function**: Python static type checking
- **Features**: Detect type issues before runtime
- **Purpose**: Reduce runtime errors
- **Example**: `mypy .`

---

## 4. Structured Data Validation

### pydantic
- **Function**: Data modeling and validation
- **Features**: Strong typing, traceable errors
- **Purpose**: Validate JSON outputs (PM_TASKS, DIRECTOR_RESULT, etc.)

### jsonschema
- **Function**: JSON Schema validation
- **Features**: Standardized input/output structure validation
- **Purpose**: Ensure model output contract consistency

---

## 5. Syntax Parsing & Safe Refactoring

### tree_sitter & tree_sitter_languages
- **Function**: Multi-language syntax tree parsing (TS/JS/Python, etc.)
- **Features**: Structure-level analysis, avoids string-based modification errors
- **Purpose**: More reliable automated code modifications
- **Related tools.py wrappers**:
  - `treesitter_outline` / `treesitter_find_symbol`
  - `treesitter_replace_node` / `treesitter_insert_method` / `treesitter_rename_symbol`

---

## 6. Logging & Readability

### rich
- **Function**: Enhanced terminal output
- **Features**: Syntax highlighting, tables, progress bars
- **Purpose**: Improve log readability and debugging efficiency

---

## 7. Usage Guidelines (For Director)

- **Quick style fixes**: Prioritize ruff
- **Change validation**: pytest / coverage / mypy
- **Structured data handling**: pydantic / jsonschema
- **Complex file structure parsing**: tree_sitter family
- **Safe function/class refactoring**: Prioritize tree-sitter structured refactoring tools

---

## 8. Important Notes

- Director automatically executes `repo_*` tools (`repo_tree`, `repo_rg`, `read_*`, `diff`) during Tool Planner phase for location and slice reading.
- Other Python tools require `tool_commands` specification or manual execution.
  - If Patch Planner doesn't provide `tool_commands`, Director defaults to: ruff → mypy → pytest (disable with `--no-default-tools`).

---

## 9. Unified Tool Interface (tools.py)

For convenient Director/script invocation, a unified `tools.py` interface is available:

```bash
python tools.py list                    # List available tools
python tools.py <tool_name> -- <args>  # Execute tool
```

**Supported tools**: ruff / pytest / coverage / mypy / jsonschema / pydantic / tree_sitter

**Additional capabilities**:
- Built-in `repo_*`, tree-sitter structured refactoring, repo indexing, lancedb retrieval
- Policy validation: `python tools.py policy_validate -- director_policy.json`

**Integration**: Planner can output `tool_commands` (optional) for automatic Director execution via tools.py.

---

## 10. Repo-IO Tools (Location & Slice Reading)

New built-in tools.py capabilities:

- `repo_tree`: Directory tree output (with depth limit)
- `repo_rg`: Full-text search (with line numbers)
- `repo_read_around`: Read by line number window
- `repo_read_slice`: Read by start-end line range
- `repo_read_head` / `repo_read_tail`: Read head/tail sections
- `repo_diff`: git diff / diff --stat

**Goal**: Enable Director's "locate → slice read" efficient information acquisition capability.

---

## 11. Evidence Collection

- Each ToolPlanner evidence collection generates a summary package:
  `.harborpilot/runtime/evidence/EVIDENCE_<task_id>_<iter>.json`
- Contains read files, line ranges, hashes, truncation info for replay and error correction.

---

## 12. Runtime Evidence Tools (tools.py built-in)

- `pytest_target`: Run specific test cases only (faster)
- `python_run`: Execute minimal reproduction scripts, collect stdout/stderr
- `node_run`: Run Node/TS reproduction scripts (suitable for frontend/toolchain)

---

## 13. Repo Indexing & Local RAG (tools.py built-in)

- `repo_symbols_index`: Quick symbol → file mapping
- `repo_import_graph`: Coarse-grained import dependency graph
- `repo_api_surface`: List public APIs (functions/classes/exports)
- `lancedb_index_code` / `lancedb_query_code`: Local code vector indexing and retrieval (optional lancedb dependency)

---

## 14. Policy Validation (tools.py built-in)

- `policy_validate`: Validate director_policy.json field and range legality
- **Example**: `python tools.py policy_validate -- .harborpilot/runtime/director_policy.json`

---

## 15. Tool Categories Summary

| Category | Tools | Primary Use Case |
|----------|-------|------------------|
| **Code Quality** | ruff | Linting, formatting |
| **Testing** | pytest, coverage | Test execution, coverage |
| **Type Safety** | mypy | Static type checking |
| **Data Validation** | pydantic, jsonschema | Schema validation |
| **Code Analysis** | tree_sitter | AST parsing, safe refactoring |
| **Presentation** | rich | Enhanced terminal output |
| **Repository** | repo_* | File system operations |
| **Evidence** | pytest_target, python_run, node_run | Runtime validation |
| **Indexing** | lancedb_*, repo_* | Code search and retrieval |
| **Policy** | policy_validate | Configuration validation |
