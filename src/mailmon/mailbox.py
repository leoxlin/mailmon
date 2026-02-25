import os
from functools import cache
from typing import Dict, Iterator, List, Optional

from jmapc import (
    Client,
    Comparator,
    Email,
    EmailAddress,
    EmailQueryFilterCondition,
    Mailbox,
    Ref,
)
from jmapc.methods import (
    EmailGet,
    EmailGetResponse,
    EmailQuery,
    EmailSet,
    EmailSetResponse,
    MailboxGet,
    MailboxGetResponse,
)

# TODO: Create abstraction and support other protocol
client = Client.create_with_api_token(
    host=os.environ["JMAP_API_HOST"], api_token=os.environ["JMAP_API_TOKEN"]
)


def format_addresses(addrs: Optional[List[EmailAddress]]) -> str:
    return ",".join(map(lambda e: e.email or "", addrs or []))


def format_email_body(email: Email) -> str:
    body = email.body_values or {}
    return "\n".join([ebv.value for ebv in body.values() if ebv.value])


@cache
def get_mailboxes() -> Dict[str, Mailbox]:
    res = client.request(MailboxGet(ids=None))
    assert isinstance(res, MailboxGetResponse)
    return dict((d.name, d) for d in res.data if d.name)


def get_mailbox_name(id: str) -> str:
    return next(mb.name or id for mb in get_mailboxes().values() if mb.id == id)


def get_mailbox(name: str) -> Mailbox:
    return get_mailboxes()[name]


def get_email(id: str) -> Email:
    res = client.request(
        EmailGet(
            ids=[id],
            fetch_text_body_values=True,
        )
    )
    assert isinstance(res, EmailGetResponse)
    return res.data[0]


def move_email(id: str, mailboxes: List[Mailbox]) -> bool:
    update = {}
    update[id] = {"mailboxIds": dict((f"{mb.id}", True) for mb in mailboxes)}
    print(update)
    res = client.request(EmailSet(update=update))
    assert isinstance(res, EmailSetResponse)
    return res.updated != None


def get_emails(mailbox: Mailbox, page_size=30) -> Iterator[Email]:
    anchor = None

    def _get_page():
        (_, res) = client.request(
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
        assert isinstance(res.response, EmailGetResponse)
        return res.response.data

    while True:
        page = _get_page()
        for email in page:
            anchor = email.id
            yield email
        if len(page) < page_size:
            break
