# Mailmon

Mailmon is an email management and monitoring tool. It is designed to sort your
emails, apply powerful rules that isn't offered by mail providers and provide
monitoring and summaries. Mailmon does not replace your email client.

## Mailmon vs OpenClaw/Filters

Giving an agent full reign over your mailbox is unpredictable and dangerous.
Writing filters for every single category is also unsustainable in the world of
email overload. Mailmon seeks to be inbetween those solutions where it leverages
LLMs but still gives you full control.

## Configuration

Mailmon creates a system prompt using a base prompt file and specific folder
prompts defined in the rules file (`~/.config/mailmon/rules.yaml`).

You can preview the prompt with `mailmon prompt`.

```yaml
folders:
  - name: Update
    description: Automated updates like reminders, 2fa code, login notification
    examples:
      - A new sign-in on Windows
      - Your one-time code
  - name: Newsletter
    description: Newsletters, local events, and substack
    examples:
      - News & Events
      - Summer 2025 Newsletter
  - name: Receipt
    description: Receipts, delivery & order confirmations
    examples:
      - Your Friday evening trip with Uber
      - Your receipt from Apple
  - name: Finance
    description: Financial statement, monthly statements, investments
    examples:
      - Your credit card statement is available
      - Your January 2026 transaction history
```


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
