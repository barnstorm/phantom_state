"""Example of using Phantom State through MCP.

This demonstrates how a DM or orchestrator would interact with the MCP server.
"""

import asyncio
import json
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def run_example():
    """Run example MCP interactions."""
    # Connect to the MCP server
    server_params = StdioServerParameters(
        command="phantom-state-mcp",
        env={
            "PHANTOM_DB_PATH": "example_narrative.db",
            "PHANTOM_EMBEDDING_BACKEND": "local",
        },
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            # Initialize connection
            await session.initialize()

            # List available tools
            tools = await session.list_tools()
            print(f"Available tools: {[t.name for t in tools.tools]}")

            # Create moments
            print("\n=== Creating moments ===")
            await session.call_tool(
                "create_moment",
                {"id": "m1", "sequence": 1, "label": "Opening scene"},
            )
            await session.call_tool(
                "create_moment",
                {"id": "m2", "sequence": 2, "label": "Discovery"},
            )

            # Create root take
            print("\n=== Creating take ===")
            take_result = await session.call_tool("create_take", {})
            print(take_result)

            # Register characters
            print("\n=== Registering characters ===")
            await session.call_tool(
                "register_character",
                {
                    "id": "alice",
                    "name": "Alice",
                    "traits": {
                        "curious": True,
                        "analytical": True,
                    },
                    "voice": {
                        "style": "precise",
                        "favors_questions": True,
                    },
                },
            )
            await session.call_tool(
                "register_character",
                {
                    "id": "bob",
                    "name": "Bob",
                    "traits": {
                        "secretive": True,
                        "protective": True,
                    },
                },
            )

            # Log a fact (that only Bob knows)
            print("\n=== Logging facts ===")
            fact_result = await session.call_tool(
                "log_fact",
                {
                    "content": "The safe combination is 7-3-9",
                    "category": "secret",
                    "moment_id": "m1",
                },
            )
            fact_id = int(fact_result.content[0].text.split(": ")[1])

            # Bob learns the fact
            await session.call_tool(
                "log_knowledge",
                {
                    "character_id": "bob",
                    "fact_id": fact_id,
                    "moment_id": "m1",
                    "take_id": 1,
                    "source": "discovered",
                },
            )

            # Record dialogue (Alice doesn't learn the secret)
            print("\n=== Recording dialogue ===")
            await session.call_tool(
                "dialogue",
                {
                    "speaker": "alice",
                    "content": "Hey Bob, do you know anything about that safe?",
                    "moment_id": "m1",
                    "take_id": 1,
                    "listeners": ["bob"],
                },
            )
            await session.call_tool(
                "dialogue",
                {
                    "speaker": "bob",
                    "content": "What safe?",
                    "moment_id": "m1",
                    "take_id": 1,
                    "listeners": ["alice"],
                },
            )

            # Query what each character knows
            print("\n=== Alice's state (should NOT know combination) ===")
            alice_state = await session.call_tool(
                "query_state",
                {
                    "character_id": "alice",
                    "moment_id": "m1",
                    "take_id": 1,
                },
            )
            alice_data = json.loads(alice_state.content[0].text)
            print(f"Facts known: {len(alice_data['facts'])}")
            print(f"Memories: {len(alice_data['memories'])}")
            for mem in alice_data["memories"]:
                print(f"  - [{mem['chunk_type']}] {mem['chunk']}")

            print("\n=== Bob's state (SHOULD know combination) ===")
            bob_state = await session.call_tool(
                "query_state",
                {
                    "character_id": "bob",
                    "moment_id": "m1",
                    "take_id": 1,
                },
            )
            bob_data = json.loads(bob_state.content[0].text)
            print(f"Facts known: {len(bob_data['facts'])}")
            for fact in bob_data["facts"]:
                print(f"  - [{fact['category']}] {fact['content']}")
            print(f"Memories: {len(bob_data['memories'])}")
            for mem in bob_data["memories"]:
                print(f"  - [{mem['chunk_type']}] {mem['chunk']}")


if __name__ == "__main__":
    asyncio.run(run_example())
