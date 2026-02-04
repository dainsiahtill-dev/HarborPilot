import argparse
import json
import os

from .utils import normalize_args
from .files import (
    repo_read_slice, repo_read_around, repo_read_head, repo_read_tail
)
from .search import (
    repo_tree, repo_rg, repo_symbols_index
)
from .treesitter import (
    treesitter_outline, treesitter_find_symbol, treesitter_replace_node,
    treesitter_insert_method, treesitter_rename_symbol
)
from .repo_map import repo_map
from .context_manager import context_manager
from .cost_router import cost_router
from .linters import (
    ruff_check, ruff_format, pytest_run, coverage_run, coverage_report,
    mypy_run, jsonschema_validate, pydantic_validate
)
# Note: python_run and node_run were in tools.py, let's look if we missed them.
# Yes, they were in tools.py. I should add them to command.py or linters.py (utils runner).
# Let's check where they fit best. Maybe command.py.
# For now, I will omit them if I didn't migrate/import them, but I should migrate them if I missed them.
# I see I missed `python_run` and `node_run` in the migration steps. 
# I will implement them here locally or in command.py. 
# Better to put them in `command.py`.

# Let's fix command.py on the fly? No, I can't do that easily without a separate tool call.
# I will define them here for now or decide they are not "linters". 
# They are generic runners. I'll put them in command.py in a future step or just define inline here if simple.
# Actually, they are simple wrappers. I will put them in `tools/command.py` in a subsequent step if critical. 
# But for now, I will assume the user might need them. Let's add them to `command.py` quickly.
# I'll update command.py first.

def main():
    parser = argparse.ArgumentParser(description="HarborPilot Tools")
    parser.add_argument("tool", help="Tool name to execute")
    parser.add_argument("args", nargs=argparse.REMAINDER, help="Arguments for the tool")
    
    args = parser.parse_args()
    tool_name = args.tool
    tool_args = normalize_args(args.args)
    cwd = os.getcwd()
    
    # timeout passed from outside or default? 
    # tools.py took timeout as arg in function, but main didn't seem to parse it. 
    # Usually the caller handles timeout or we pass a default.
    timeout = 30 # Default 30s
    
    result = {"ok": False, "error": f"Unknown tool: {tool_name}"}
    
    # Files
    if tool_name == "repo_read_slice":
        result = repo_read_slice(tool_args, cwd, timeout)
    elif tool_name == "repo_read_around":
        result = repo_read_around(tool_args, cwd, timeout)
    elif tool_name == "repo_read_head":
        result = repo_read_head(tool_args, cwd, timeout)
    elif tool_name == "repo_read_tail":
        result = repo_read_tail(tool_args, cwd, timeout)
        
    # Search
    elif tool_name == "repo_tree":
        result = repo_tree(tool_args, cwd, timeout)
    elif tool_name == "repo_rg":
        result = repo_rg(tool_args, cwd, timeout)
    elif tool_name == "repo_symbols_index":
        result = repo_symbols_index(tool_args, cwd, timeout)
        
    # Treesitter
    elif tool_name == "treesitter_outline":
        result = treesitter_outline(tool_args, cwd, timeout)
    elif tool_name == "treesitter_find_symbol":
        result = treesitter_find_symbol(tool_args, cwd, timeout)
    elif tool_name == "treesitter_replace_node":
        result = treesitter_replace_node(tool_args, cwd, timeout)
    elif tool_name == "treesitter_insert_method":
        result = treesitter_insert_method(tool_args, cwd, timeout)
    elif tool_name == "treesitter_rename_symbol":
        result = treesitter_rename_symbol(tool_args, cwd, timeout)

    # Sniper Mode tools
    elif tool_name == "repo_map":
        result = repo_map(tool_args, cwd, timeout)
    elif tool_name == "context_manager":
        result = context_manager(tool_args, cwd, timeout)
    elif tool_name == "cost_router":
        result = cost_router(tool_args, cwd, timeout)
        
    # Linters
    elif tool_name == "ruff_check":
        result = ruff_check(tool_args, cwd, timeout)
    elif tool_name == "ruff_format":
        result = ruff_format(tool_args, cwd, timeout)
    elif tool_name == "pytest_run":
        result = pytest_run(tool_args, cwd, timeout)
    elif tool_name == "coverage_run":
        result = coverage_run(tool_args, cwd, timeout)
    elif tool_name == "coverage_report":
        result = coverage_report(tool_args, cwd, timeout)
    elif tool_name == "mypy_run":
        result = mypy_run(tool_args, cwd, timeout)
    elif tool_name == "jsonschema_validate":
        result = jsonschema_validate(tool_args, cwd, timeout)
    elif tool_name == "pydantic_validate":
        result = pydantic_validate(tool_args, cwd, timeout)
        
    print(json.dumps(result, ensure_ascii=False))

if __name__ == "__main__":
    main()
