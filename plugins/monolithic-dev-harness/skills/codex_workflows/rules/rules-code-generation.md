# Avoid Markdown Fences in Code Generation

**CRITICAL:** When generating code suggestions, snippets, or inline completions, do NOT wrap the code in markdown fences (e.g., ` ```dart `).

1. Provide ONLY the raw code characters.
2. Ensure no leading or trailing markdown markers are included.
3. This applies to both the Agent Chat and any internal Autocomplete inference tracks.
