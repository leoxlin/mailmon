# ruff: noqa: E402
import json
from itertools import islice

import typer
from dotenv.main import load_dotenv

# Load .env into os.environ before imports
load_dotenv()

from mailmon.llm import Classifier
from mailmon.mailbox import get_emails, get_mailbox, get_mailboxes

app = typer.Typer()


@app.command()
def plan():
    inbox = get_mailbox("Inbox")
    mailboxes = get_mailboxes()
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


def main() -> int:
    return app()
