# ast-grep Plugin Marketplace for AI Agents

A Claude Code plugin marketplace containing the ast-grep skill for powerful structural code search using Abstract Syntax Tree (AST) patterns. Search your codebase based on code structure rather than just text matching.

## What is This?

This is a **Claude Code plugin marketplace** that provides the **ast-grep plugin**. The plugin includes a skill that teaches Claude how to write and use ast-grep rules to perform advanced code searches. Unlike traditional text-based search (grep, ripgrep), ast-grep understands the structure of your code, allowing you to find patterns like:

- "Find all async functions that don't have error handling"
- "Locate all React components that use a specific hook"
- "Find functions with more than 3 parameters"
- "Search for console.log calls inside class methods"




## Prerequisites

You need to have ast-grep installed on your system:

```bash
# macOS
brew install ast-grep

# npm
npm install -g @ast-grep/cli

# cargo
cargo install ast-grep
```

Verify installation:
```bash
ast-grep --version
```

## Installation

### Option 1: Install via skills.sh (Recommended)

```
npx skills add ast-grep/agent-skill
```

### Option 2: Install via Marketplace 

1. **Add the marketplace** to your Claude Code:

```bash
/plugin marketplace add ast-grep/agent-skill
```

2. **Install the ast-grep plugin**:

```bash
/plugin install ast-grep
```

`/plugin install` activates the plugin in the running session, reporting `Installed ast-grep. Plugin is now active.`, so no restart is needed.
Run `/plugin` to confirm it is listed.

### Option 3: Install Locally for Development

If you're developing or testing locally:

```bash
# Clone the repository
git clone https://github.com/ast-grep/agent-skill.git /path/to/local-marketplace

# Add as local marketplace
/plugin marketplace add /path/to/local-marketplace

# Install the plugin
/plugin install ast-grep
```

## How to Use

Once installed, ask Claude to search your code using structural patterns.

Installing the skill makes it **discovered**, not **preferred**.
Claude Code loads it and matches its description against your query, but on any given search it is also holding a text-search tool that needs no setup, so it often takes that instead.
Naming ast-grep or structural search ("Use ast-grep to find...") invokes the skill reliably.

To get that preference without repeating it every query, state it once in your `AGENTS.md` or `CLAUDE.md`:

```markdown
You are operating in an environment where `ast-grep` is installed.
For any code search that requires understanding of syntax or code structure, you should default to using `ast-grep --lang [language] -p '<pattern>'`.
Adjust the `--lang` flag as needed for the specific programming language.
Avoid using text-only search tools unless a plain-text search is explicitly requested.
```

See [Using ast-grep with AI Tools](https://ast-grep.github.io/advanced/prompting.html) for more on prompting, including feeding the docs to an agent and the MCP server.

### Example Queries

**Find async functions with await:**
```
Find all async functions in this project that use await
```

**Find missing error handling:**
```
Show me async functions that don't have try-catch blocks
```

**Find specific function calls:**
```
Find all places where we call console.log with more than one argument
```

**Find code in specific contexts:**
```
Find all setState calls inside useEffect hooks
```

### How It Works

When you ask Claude to search for code patterns:

1. Claude analyzes your query and determines if ast-grep is appropriate
2. It creates example code that matches your search criteria
3. It writes an ast-grep rule to match the pattern
4. It tests the rule against the example code
5. Once verified, it searches your entire codebase
6. Results are presented with file paths and line numbers

## Supported Languages

ast-grep supports many programming languages including:

- JavaScript/TypeScript
- Python
- Rust
- Go
- Java
- C/C++
- Ruby
- PHP
- And many more

## Key Features

- **Structure-aware search**: Matches code based on AST structure, not just text
- **Metavariables**: Use `$VAR` to match any expression, statement, or identifier
- **Relational queries**: Find code inside specific contexts (e.g., "find X inside Y")
- **Composite logic**: Combine rules with AND, OR, NOT operations
- **Test-driven approach**: Rules are tested before running on your codebase

## Advanced Usage

### Direct ast-grep Commands

While Claude will handle most use cases automatically, you can also use ast-grep directly:

```bash
# Simple pattern search
ast-grep run --pattern 'console.log($ARG)' --lang javascript .

# Complex rule-based search
ast-grep scan --inline-rules "id: my-rule
language: javascript
rule:
  kind: function_declaration
  has:
    pattern: await \$EXPR
    stopBy: end" .
```

### Debugging

If a search isn't working as expected, ask Claude to:
- Show you the ast-grep rule it created
- Inspect the AST structure of your code
- Test the rule against example code

A zero-match run exits successfully, so "no results" and "wrong pattern" look identical.
Two things help when a pattern is the suspect:

- Load [`llms-full.txt`](https://ast-grep.github.io/llms-full.txt), the whole ast-grep documentation as one file, into the agent's context so it stops guessing at rule syntax.
- Use [`ast-grep-mcp`](https://github.com/ast-grep/ast-grep-mcp) to let the agent dump the AST and test a pattern against a snippet, iterating instead of committing to one guess.

## Repository Structure

This is a Claude Code plugin marketplace repository with the following structure:

```
agent-skill/
├── .claude-plugin/
│   └── marketplace.json           # Marketplace manifest
├── ast-grep/                       # ast-grep plugin
│   ├── .claude-plugin/
│   │   └── plugin.json            # Plugin manifest
│   └── skills/
│       ├── ast-grep/
│       │   ├── SKILL.md           # Skill instructions for Claude
│       │   └── references/
│       │       └── rule_reference.md  # ast-grep rule documentation
│       └── outline/
│           └── SKILL.md           # Structural codebase map skill
└── README.md                       # This file
```

### Key Files

- **`.claude-plugin/marketplace.json`**: Marketplace manifest defining available plugins
- **`ast-grep/.claude-plugin/plugin.json`**: Plugin manifest for the ast-grep plugin
- **`ast-grep/skills/ast-grep/SKILL.md`**: Main skill instructions that Claude uses
- **`ast-grep/skills/ast-grep/references/`**: Supporting documentation and reference materials
- **`ast-grep/skills/outline/SKILL.md`**: Cheap structural map of a codebase, for exploring before reading full source

## Tips for Best Results

1. **Be specific**: The more details you provide, the better the search results
2. **Provide examples**: If possible, show Claude an example of what you want to find
3. **Iterate**: Start with a broad search and narrow it down
4. **Ask for explanations**: Ask Claude to explain the ast-grep rule it creates

## Examples of What You Can Search For

### Code Quality
- Functions without return statements
- Functions with too many parameters
- Unused variables
- Missing null checks

### Patterns
- React hooks usage patterns
- API call patterns
- Database query patterns
- Error handling patterns

### Refactoring
- Find all uses of deprecated functions
- Locate code that needs migration
- Find inconsistent patterns across codebase

### Security
- Potential SQL injection points
- Unsafe eval usage
- Missing input validation

## Troubleshooting

**Claude isn't using the skill:**
- Make sure ast-grep is installed (`ast-grep --version`)
- Try being more explicit: "Use ast-grep to search for..."

**No results found:**
- Try a simpler query first
- Ask Claude to show you the rule and test it
- Provide an example of code you want to match

**Unexpected results:**
- Refine your query with more details
- Ask Claude to exclude certain patterns
- Request to see the AST structure of your code

## Contributing

To improve this skill:
1. Edit `SKILL.md` to update Claude's instructions
2. Add examples to `references/` directory
3. Test with various code patterns

## Resources

- [ast-grep Official Documentation](https://ast-grep.github.io/)
- [ast-grep Playground](https://ast-grep.github.io/playground.html) - Test patterns online
- [ast-grep GitHub](https://github.com/ast-grep/ast-grep)

## License

This skill follows ast-grep's MIT license for any included documentation or examples.

## Support

For issues with:
- **This skill**: Open an issue in this repository
- **ast-grep itself**: Visit [ast-grep GitHub](https://github.com/ast-grep/ast-grep)
- **Claude Code**: Check [Claude Code documentation](https://code.claude.com/)
