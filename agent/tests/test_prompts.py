from olist_agent.prompts import SYSTEM_PROMPT

MCP_TOOLS = ["list_tables", "describe_table", "run_readonly_sql", "search_docs"]


def test_prompt_mentions_every_mcp_tool():
    # renaming a tool on the server must not silently break the instructions
    for name in MCP_TOOLS:
        assert name in SYSTEM_PROMPT
