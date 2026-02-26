import textwrap
from functools import cache
from typing import Literal

import instructor
import litellm
from pydantic import BaseModel, create_model

from mailmon.config import Config, FolderPromptRule
from mailmon.mailbox import Email, Mailbox

litellm.suppress_debug_info = True


class ClassifierResult(BaseModel):
    folder: str
    confidence: Literal["high", "medium", "low"]
    reason: str


class Classifier:
    def __init__(self, config: Config, mailboxes: dict[str, Mailbox]) -> None:
        self.model = config.llm.model
        self.host = config.llm.api_host
        self.token = config.llm.api_token
        rules = config.rules
        folder_mapping = {rule.name: rule for rule in rules.folder_prompts}
        self.folder_rules: dict[str, FolderPromptRule] = {
            mb: folder_mapping[mb]
            for mb in mailboxes.keys()
            if mb not in rules.system_folders and mb in folder_mapping
        }
        self.folders = list(self.folder_rules.keys()) + ["Unknown"]
        self.client = instructor.from_litellm(
            litellm.completion, mode=instructor.Mode.JSON_SCHEMA
        )
        self.result_cls = create_model(
            "ClassifierResult",
            __base__=ClassifierResult,
            folder=(Literal[tuple(self.folders)], ...),
        )

    @cache
    def system_prompt(self):
        def _render_rule(rule: FolderPromptRule) -> str:
            return "\n".join(
                [
                    f"## {rule.name}",
                    f"Description: {rule.description}",
                    "Examples:",
                    "\n".join(f"  - {example}" for example in rule.examples),
                ]
            )

        folder_prompt = "\n\n".join(
            _render_rule(rule) for rule in self.folder_rules.values()
        )
        base_system_prompt = textwrap.dedent(
            """
            You are an email classifier. Categorize each email into exactly one of
            the following folders. Follow the rules, folder description, and examples
            closely.

            # Rules

              - You must pick the single best matching folder.
              - If no folder fits well, respond with "Unknown" folder.
              - When providing reason, keep it short to under 30 words.
              - Do not invent new folders.
              - Return only valid JSON.

            # Folders
            """
        ).strip()
        return "\n\n".join([base_system_prompt, folder_prompt])

    def user_prompt(self, email: Email):
        metadata = textwrap.dedent(
            f"""
            From: {email.formatted_from()}
            To: {email.formatted_to()}
            Subject: {email.subject}

            Body:
            """
        ).lstrip()
        return metadata + email.formatted_body()

    def classify(self, email: Email) -> ClassifierResult:
        return self.client.chat.completions.create(
            model=self.model,
            api_base=self.host,
            api_key=self.token,
            messages=[
                {
                    "role": "system",
                    "content": self.system_prompt(),
                },
                {
                    "role": "user",
                    "content": self.user_prompt(email),
                },
            ],
            response_model=self.result_cls,
            max_retries=3,
        )
