# Mailmon

Mailmon is an email management and monitoring tool. It is designed to sort your
emails, apply powerful rules that isn't offered by mail providers and provide
monitoring and summaries. Mailmon does not replace your email client.

## Mailmon vs OpenClaw/Filters

Giving an agent full reign over your mailbox is unpredictable and dangerous.
Writing filters for every single category is also unsustainable in the world of
email overload. Mailmon seeks to be inbetween those solutions where it leverages
LLMs but still gives you full control.

## Development

```
cp .env.example .env
uv sync --frozen
uv run mailmon
```

## AI Disclosure

- Mailmon leverages LLMs to read and process your email into categories
- Mailmon is LLM backend agnostic and policies of LLM providers apply
- Claude is prompted for examples and choosing specific libraries
- Claude Code is used for some scaffolding but not vibe coding
- Claude Code is used for some test generation
