from abc import ABC, abstractmethod
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Optional


class MailboxError(Exception):
    pass


class MailboxBackend(ABC):
    @abstractmethod
    def get_mailboxes(self) -> dict[str, Mailbox]: ...

    @abstractmethod
    def get_email(self, id: str) -> Optional[Email]: ...

    @abstractmethod
    def get_emails(self, mailbox: Mailbox, page_size: int = 30) -> Iterator[Email]: ...

    @abstractmethod
    def move_email(self, id: str, mailboxes: list[Mailbox]) -> bool: ...

    def get_mailbox(self, name: str) -> Optional[Mailbox]:
        return self.get_mailboxes()[name]

    def get_mailbox_name(self, id: str) -> str:
        return next(
            mb.name or id for mb in self.get_mailboxes().values() if mb.id == id
        )


@dataclass
class Mailbox:
    id: str
    name: str | None = None


@dataclass
class Email:
    id: str | None = None
    mail_from: list[str] | None = None
    to: list[str] | None = None
    subject: str | None = None
    body_values: dict[str, str] | None = None
    mailbox_ids: dict[str, bool] | None = None

    def formatted_from(self) -> str:
        return ",".join(self.mail_from or [])

    def formatted_to(self) -> str:
        return ",".join(self.to or [])

    def formatted_body(self) -> str:
        body = self.body_values or {}
        return "\n".join(bv for bv in body.values() if bv)
