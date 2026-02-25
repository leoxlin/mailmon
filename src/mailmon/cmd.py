# ruff: noqa: E402
import json
from itertools import islice
from typing import Optional

import typer
from dotenv.main import load_dotenv
from rich import print as rprint

# Load .env into os.environ before imports
load_dotenv()

from mailmon.llm import Classifier
from mailmon.mailbox import get_email, get_emails, get_mailbox, get_mailboxes

app = typer.Typer()


@app.command()
def prompt(email_id: Optional[str] = None):
    mailboxes = get_mailboxes()
    classifier = Classifier(mailboxes)
    rprint(":robot: [bold green]System Prompt:[/bold green]\n")
    print(classifier.system_prompt())

    if email_id:
        email = get_email(email_id)
        print()
        rprint(":man_medium_skin_tone: [bold green]User Prompt:[/bold green]\n")
        print(classifier.user_prompt(email))


@app.command()
def plan(email_id: Optional[str] = None):
    mailboxes = get_mailboxes()
    emails = []
    if email_id:
        emails = [get_email(email_id)]
    else:
        inbox = get_mailbox("Inbox")
        emails = islice(get_emails(inbox), 10)
    classifier = Classifier(mailboxes)
    for email in emails:
        result = json.loads(
            classifier.classify(email).json()["choices"][0]["message"]["content"]
        )
        print(f"{email.id}:", email.subject)
        print(
            f"Folder: {result['folder']}",
            f"Confidence: {result['confidence']}",
            f"Reason: {result['reason']}",
        )
        print()


@app.command()
def apply():
    print("TODO")
    pass


def main() -> int:
    return app()
