from collections.abc import Iterator
from functools import cache
from typing import Optional

from jmapc import Client, Comparator, EmailQueryFilterCondition, Ref
from jmapc import Email as JMAPEmail
from jmapc import Mailbox as JMAPMailbox
from jmapc.methods import (
    EmailGet,
    EmailGetResponse,
    EmailQuery,
    EmailSet,
    EmailSetResponse,
    MailboxGet,
    MailboxGetResponse,
)

from mailmon.config import JMAPConfig
from mailmon.mailbox.models import Email, Mailbox, MailboxBackend, MailboxError


class JMAPBackend(MailboxBackend):
    def __init__(self, config: JMAPConfig) -> None:
        self.client = Client.create_with_api_token(
            host=config.api_host, api_token=config.api_token
        )

    @staticmethod
    def _to_email_addresses(
        addrs: list | None,
    ) -> list[str] | None:
        if addrs is None:
            return None
        return [a.email or "" for a in addrs]

    @staticmethod
    def _to_mailbox(mb: JMAPMailbox) -> Mailbox:
        return Mailbox(id=mb.id, name=mb.name)

    @staticmethod
    def _to_email(email: JMAPEmail) -> Email:
        body_values = None
        if email.body_values:
            body_values = {k: v.value for k, v in email.body_values.items()}
        return Email(
            id=email.id,
            mail_from=JMAPBackend._to_email_addresses(email.mail_from),
            to=JMAPBackend._to_email_addresses(email.to),
            subject=email.subject,
            body_values=body_values,
            mailbox_ids=email.mailbox_ids,
        )

    @cache
    def get_mailboxes(self) -> dict[str, Mailbox]:
        res = self.client.request(MailboxGet(ids=None))
        assert isinstance(res, MailboxGetResponse)
        return {d.name: self._to_mailbox(d) for d in res.data if d.name}

    def get_email(self, id: str) -> Optional[Email]:
        res = self.client.request(
            EmailGet(
                ids=[id],
                fetch_text_body_values=True,
            )
        )
        assert isinstance(res, EmailGetResponse)
        if res.data:
            return self._to_email(res.data[0])
        return None

    def move_email(self, id: str, mailboxes: list[Mailbox]) -> bool:
        update = {id: {"mailboxIds": {mb.id: True for mb in mailboxes}}}
        res = self.client.request(EmailSet(update=update))
        assert isinstance(res, EmailSetResponse)
        return res.updated is not None

    def get_emails(self, mailbox: Mailbox, page_size: int = 30) -> Iterator[Email]:
        anchor = None

        def _get_page():
            (qres, res) = self.client.request(
                [
                    EmailQuery(
                        collapse_threads=True,
                        filter=EmailQueryFilterCondition(
                            in_mailbox=mailbox.id,
                        ),
                        sort=[Comparator(property="receivedAt", is_ascending=False)],
                        anchor=anchor,
                        anchor_offset=1,
                        limit=page_size,
                    ),
                    EmailGet(
                        ids=Ref("/ids"),
                        fetch_text_body_values=True,
                    ),
                ]
            )
            if isinstance(res.response, EmailGetResponse):
                return res.response.data
            elif isinstance(qres.response, Exception):
                raise qres.response
            elif isinstance(res.response, Exception):
                raise res.response
            else:
                raise MailboxError("Fetch email page failed")

        while True:
            page = _get_page()
            for email in page:
                anchor = email.id
                yield self._to_email(email)
            if len(page) < page_size:
                break
