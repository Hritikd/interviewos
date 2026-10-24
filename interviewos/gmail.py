from __future__ import annotations

from typing import Any

from interviewos.crust import ProviderError


class GmailConnector:
    """Composio session scoped to Gmail. Draft is the default apply action. Send is a separate call."""

    def __init__(self, api_key: str, user_id: str):
        self.api_key = api_key.strip()
        self.user_id = user_id
        self._session: Any = None

    def session(self) -> Any:
        if not self.api_key:
            raise ProviderError("COMPOSIO_API_KEY is not set.", status=0, provider="composio")
        if self._session is None:
            from composio import Composio

            try:
                composio = Composio(api_key=self.api_key)
                self._session = composio.sessions.create(user_id=self.user_id, toolkits=["gmail"])
            except Exception as exc:
                raise ProviderError(
                    "Gmail is skipped. Composio rejected the API key, so the note stays on this page.",
                    provider="composio",
                ) from exc
        return self._session

    def connect_url(self) -> str:
        request = self.session().authorize("gmail")
        return str(request.redirect_url)

    def connected(self) -> bool:
        try:
            details = self.session().toolkits(toolkits=["gmail"])
        except ProviderError:
            return False
        return _is_gmail_connected(details)

    def create_draft(self, recipient: str, subject: str, body: str) -> dict[str, Any]:
        return self._execute(
            "GMAIL_CREATE_EMAIL_DRAFT",
            {
                "recipient_email": recipient,
                "subject": subject,
                "body": body,
                "is_html": False,
            },
        )

    def send(self, recipient: str, subject: str, body: str) -> dict[str, Any]:
        return self._execute(
            "GMAIL_SEND_EMAIL",
            {
                "recipient_email": recipient,
                "subject": subject,
                "body": body,
                "is_html": False,
            },
        )

    def _execute(self, slug: str, arguments: dict[str, Any]) -> dict[str, Any]:
        try:
            result = self.session().execute(slug, arguments=arguments)
        except Exception as exc:
            name = exc.__class__.__name__
            if name == "ToolInputRequiredError":
                raise ProviderError(
                    "Gmail needs an approval in the Composio connect flow before this send.",
                    provider="composio",
                ) from exc
            raise ProviderError(str(exc)[:300], provider="composio") from exc
        data = _as_data(result)
        if data.get("successful") is False:
            raise ProviderError(str(data.get("error") or "Gmail did not accept the message."), provider="composio")
        return data


def _as_data(result: Any) -> dict[str, Any]:
    data = getattr(result, "data", result)
    if hasattr(data, "model_dump"):
        data = data.model_dump()
    if isinstance(data, str):
        return {"raw": data, "successful": True}
    if isinstance(data, dict):
        return data
    return {"raw": str(data), "successful": True}


def _is_gmail_connected(details: Any) -> bool:
    items: Any = details
    for attr in ("items", "toolkits"):
        if hasattr(details, attr):
            items = getattr(details, attr)
            break
    if isinstance(details, dict):
        items = details.get("items") or details.get("toolkits") or [details]
    if not isinstance(items, list):
        items = [items]
    for item in items:
        if isinstance(item, dict):
            slug = str(item.get("slug") or item.get("toolkit") or "")
            connected = item.get("is_connected")
            status = str(item.get("status") or item.get("connection_status") or "")
        else:
            slug = str(getattr(item, "slug", "") or getattr(item, "toolkit", ""))
            connected = getattr(item, "is_connected", None)
            status = str(getattr(item, "status", "") or getattr(item, "connection_status", ""))
        if slug and "gmail" not in slug.lower():
            continue
        if connected is True or status.lower() in {"connected", "active"}:
            return True
    return False
