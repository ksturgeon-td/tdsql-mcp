# teradata-sql-analytics Skill

A Claude Code skill that loads the Teradata Vantage native function guidelines and full syntax topic index into any session. No database credentials required — it's a read-only knowledge library.

When combined with a Teradata MCP server (e.g. `tdsql-mcp`), the skill handles native function guidance while the MCP server handles query execution.

---

## Installation

### Claude Code (CLI / IDE extensions)

```bash
# Clone the repo
git clone https://github.com/ksturgeon-td/tdsql-mcp.git
cd tdsql-mcp

# Install — copies SKILL.md and creates a relative symlink to the syntax library
mkdir -p ~/.claude/teradata-sql-analytics
cp skills/teradata-sql-analytics/SKILL.md ~/.claude/teradata-sql-analytics/SKILL.md
ln -sf "$(pwd)/src/tdsql_mcp/syntax" ~/.claude/teradata-sql-analytics/syntax
```

To update the syntax library later: `git pull` in the repo directory. The symlink picks up changes automatically.

### Claude Desktop & Claude.ai (ZIP upload)

> **Prerequisite:** Enable code execution in **Settings > Capabilities** before Skills become accessible.

```bash
# Build a self-contained skill folder (follows symlinks so syntax files are included)
rsync -rL skills/teradata-sql-analytics/ /tmp/teradata-sql-analytics/
cd /tmp && zip -r teradata-sql-analytics.zip teradata-sql-analytics/
```

Then: **Customize > Skills > + > Upload a skill** — upload `teradata-sql-analytics.zip`.

---

## Usage

**Claude Code** — type at the start of any session:

```
/teradata-sql-analytics
```

**Claude Desktop / Claude.ai** — enable the skill via **Customize > Skills**. It activates automatically in new conversations.

---

## Recommended Project / Session Instructions

Add these as project instructions (**Project > Instructions** in Claude Desktop or Claude.ai) for best results. This tells the agent to use the skill proactively rather than waiting to be asked:

```
You are working with a Teradata Vantage database.

IMPORTANT: Always prefer native Teradata table operators over hand-written SQL equivalents.
Teradata Vantage has built-in distributed functions for analytics, ML, data preparation,
text processing, and vector search. These run across all AMPs in parallel and outperform
equivalent hand-written SQL. Do NOT write manual SQL for operations like scaling, encoding,
binning, statistics, clustering, classification, or similarity search when a native function exists.

Before writing any analytics, transformation, or ML SQL:
  (1) use the /teradata-sql-analytics skill (syntax/guidelines.md) to see the canonical
      mapping of common operations to native Teradata functions,
  (2) use the /teradata-sql-analytics skill (syntax/index.md) to discover all available topics,
  (3) load the relevant topic(s) for exact syntax.

Use available MCP tools to explore the schema.
```

You can also paste this at the start of any session if you don't have a project configured.

---

## What's Included

| File | Purpose |
|------|---------|
| `SKILL.md` | Skill entrypoint — loaded when `/teradata-sql-analytics` is invoked |
| `syntax/guidelines.md` | Native function guidelines; canonical mapping of 50+ operations to native functions |
| `syntax/index.md` | Full topic directory and workflow sequences |
| `syntax/<topic>.md` | Detailed syntax for each function domain — loaded on-demand |

The full topic list is in [`syntax/index.md`](syntax/index.md).
