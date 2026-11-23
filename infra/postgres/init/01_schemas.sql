CREATE EXTENSION IF NOT EXISTS vector;

CREATE SCHEMA IF NOT EXISTS raw;      -- data as-is from CSV
CREATE SCHEMA IF NOT EXISTS staging;  -- cleaned & typed (dbt)
CREATE SCHEMA IF NOT EXISTS marts;    -- star schema for BI & agent (dbt)
CREATE SCHEMA IF NOT EXISTS knowledge; -- embedded docs for RAG (mcp_server/index_docs.py)
