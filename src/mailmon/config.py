import os
from dataclasses import dataclass, field

import yaml

EXAMPLE_RULES = """\
folders: []
# - name: Update
#   description: Automated updates like reminders, 2fa code, login notification
#   examples:
#     - A new sign-in on Windows
#     - Your one-time code
# - name: Newsletter
#   description: Newsletters, local events, and substack
#   examples:
#     - News & Events
#     - Summer 2025 Newsletter
# - name: Receipt
#   description: Receipts, delivery & order confirmations
#   examples:
#     - Your Friday evening trip with Uber
#     - Your receipt from Apple
# - name: Finance
#   description: Financial statement, monthly statements, investments
#   examples:
#     - Your credit card statement is available
#     - Your January 2026 transaction history
"""


class ConfigError(Exception):
    pass


def _get_file_env(env_var: str, default_filename: str) -> str:
    return os.path.expanduser(
        os.environ.get(env_var, f"~/.config/mailmon/{default_filename}")
    )


@dataclass
class FolderPromptRule:
    name: str
    description: str
    examples: list[str] = field(default_factory=list)


@dataclass
class Rules:
    folder_prompts: list[FolderPromptRule] = field(default_factory=list)
    system_folders: list[str] = field(default_factory=list)

    @classmethod
    def from_file(cls, path: str) -> "Rules":
        if not os.path.exists(path):
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w") as f:
                f.write(EXAMPLE_RULES)
            raise ConfigError(
                f"No rules file found. Generated example at {path}\n"
                "Edit the file to add your folder rules, then run again."
            )

        folder_prompts = []
        with open(path) as f:
            data = yaml.safe_load(f)
            folder_prompts = [
                FolderPromptRule(
                    name=f["name"],
                    description=f["description"],
                    examples=f.get("examples", []),
                )
                for f in data.get("folders", [])
            ]
        return cls(
            folder_prompts=folder_prompts,
            system_folders=data.get(
                "system_folders",
                [
                    "Inbox",
                    "Archive",
                    "Drafts",
                    "Sent",
                    "Spam",
                    "Trash",
                ],
            ),
        )


@dataclass
class JMAPConfig:
    api_host: str
    api_token: str


@dataclass
class LLMConfig:
    model: str
    api_host: str
    api_token: str


@dataclass
class Config:
    jmap: JMAPConfig
    llm: LLMConfig
    rules: Rules
    plan_file: str

    @classmethod
    def from_env(cls) -> "Config":
        from dotenv import load_dotenv

        load_dotenv()
        rules_file = _get_file_env("RULES_FILE", "rules.yaml")
        return cls(
            jmap=JMAPConfig(
                api_host=os.environ["JMAP_API_HOST"],
                api_token=os.environ["JMAP_API_TOKEN"],
            ),
            llm=LLMConfig(
                model=os.environ["LLM_MODEL"],
                api_host=os.environ["LLM_API_HOST"],
                api_token=os.environ["LLM_API_TOKEN"],
            ),
            rules=Rules.from_file(rules_file),
            plan_file=_get_file_env("PLAN_FILE", "plan.db"),
        )
