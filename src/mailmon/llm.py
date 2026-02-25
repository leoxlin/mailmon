import os
import textwrap
from functools import cache
from typing import Dict, List, Optional

import requests
import yaml
from jmapc import Email, EmailAddress, Mailbox


def format_addresses(addrs: Optional[List[EmailAddress]]) -> str:
    return ",".join(map(lambda e: f"{e.name} <{e.email}>", addrs or []))


def get_mailmon_rules():
    # TODO: Generate example rules file if it doesn't exist
    with open(os.path.expanduser(os.environ["RULES_FILE"])) as file:
        return yaml.safe_load(file)


class Classifier:
    def __init__(self, mailboxes: Dict[str, Mailbox]) -> None:
        self.model = os.environ["LLM_MODEL"]
        self.host = os.environ["LLM_API_HOST"]
        self.token = os.environ["LLM_API_TOKEN"]
        self.rules = get_mailmon_rules()
        # TODO: Map rules to a python object
        folder_mapping = dict((f["name"], f) for f in self.rules["folders"])
        self.folder_rules = dict(
            (mb, folder_mapping[mb])
            for mb in mailboxes.keys()
            if mb not in self.rules["system_folders"] and mb in folder_mapping
        )
        self.folders = list(self.folder_rules.keys())

    @cache
    def system_prompt(self):
        def _render_rule(rule) -> str:

            return "\n".join(
                [
                    f"## {rule['name']}",
                    f"Description: {rule['description']}",
                    "Examples:",
                    "\n".join(f"  - {example}" for example in rule["examples"]),
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
        return textwrap.dedent(
            f"""
            From: {format_addresses(email.mail_from)}
            To: {format_addresses(email.to)}
            Subject: {email.subject}

            Body:
            {email.text_body}
            """
        ).strip()

    @cache
    def response_format(self):
        return {
            "type": "json_schema",
            "json_schema": {
                "name": "email_classification",
                "strict": True,
                "schema": {
                    "type": "object",
                    "properties": {
                        "folder": {
                            "type": "string",
                            "enum": self.folders,
                        },
                        "confidence": {
                            "type": "string",
                            "enum": ["high", "medium", "low"],
                        },
                        "reason": {"type": "string"},
                    },
                    "required": ["folder", "confidence", "reason"],
                    "additionalProperties": False,
                },
            },
        }

    def classify(self, email: Email):
        res = requests.post(
            url=self.host,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
            },
            json={
                "model": self.model,
                "messages": [
                    {
                        "role": "system",
                        "content": self.system_prompt(),
                    },
                    {
                        "role": "user",
                        "content": self.user_prompt(email),
                    },
                ],
                "response_format": self.response_format(),
            },
        )

        if not res.ok:
            # TODO: Handle errors properly
            print(str(res.reason))

        return res
