"""Quick test to verify MCP server can be invoked."""

import os
import sys

# Set environment for test
os.environ["PHANTOM_DB_PATH"] = ":memory:"
os.environ["PHANTOM_EMBEDDING_BACKEND"] = "local"

# Test import and initialization
try:
    from phantom_state.mcp import server, TOOLS, get_engine

    print(f"[OK] MCP server module imported successfully")
    print(f"[OK] Found {len(TOOLS)} tools:")
    for tool in TOOLS:
        print(f"  - {tool.name}: {tool.description}")

    # Test engine initialization
    engine = get_engine()
    print(f"\n[OK] Engine initialized with config:")
    print(f"  - db_path: {engine.config.db_path}")
    print(f"  - embedding_backend: {engine.config.embedding_backend}")
    print(f"  - vector_dimensions: {engine.config.vector_dimensions}")

    # Clean up
    engine.close()

    print("\n[OK] All tests passed!")
    sys.exit(0)

except Exception as e:
    print(f"\n[ERROR] {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
