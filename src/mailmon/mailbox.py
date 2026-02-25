import os
from functools import cache
from typing import Dict, Iterator

from jmapc import (
    Client,
    Comparator,
    Email,
    EmailQueryFilterCondition,
    Mailbox,
    Ref,
)
from jmapc.methods import (
    EmailGet,
    EmailGetResponse,
    EmailQuery,
    MailboxGet,
    MailboxGetResponse,
)

client = Client.create_with_api_token(
    host=os.environ["JMAP_API_HOST"], api_token=os.environ["JMAP_API_TOKEN"]
)


@cache
def get_mailboxes() -> Dict[str, Mailbox]:
    res = client.request(MailboxGet(ids=None))
    assert isinstance(res, MailboxGetResponse)
    return dict((d.name, d) for d in res.data if d.name)


def get_mailbox(name: str) -> Mailbox:
    return get_mailboxes()[name]


def get_emails(mailbox: Mailbox, page_size=50) -> Iterator[Email]:
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
                EmailGet(ids=Ref("/ids")),
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
