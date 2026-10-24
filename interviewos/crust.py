from __future__ import annotations

import time
from typing import Any

import httpx


class ProviderError(RuntimeError):
    def __init__(self, message: str, *, status: int = 0, provider: str):
        super().__init__(message)
        self.status = status
        self.provider = provider


class CrustClient:
    """Crustdata API version 2025-11-01. One retry on transient failures. No retry on 401."""

    def __init__(self, api_key: str, timeout: float = 40):
        self.api_key = api_key.strip()
        self.credits_used = 0.0
        self._client = httpx.Client(
            base_url="https://api.crustdata.com",
            timeout=timeout,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "x-api-version": "2025-11-01",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        )

    def close(self) -> None:
        self._client.close()

    def post(self, path: str, body: dict[str, Any]) -> Any:
        if not self.api_key:
            raise ProviderError("CRUSTDATA_API_KEY is not set.", status=0, provider="crustdata")
        last_error: ProviderError | None = None
        for attempt in range(2):
            response = self._client.post(path, json=body)
            self._add_credits(response.headers.get("x-credits-used"))
            if response.status_code in {429, 502, 503} and attempt == 0:
                time.sleep(1.2)
                continue
            if response.status_code == 401:
                raise ProviderError("Crustdata rejected the API key.", status=401, provider="crustdata")
            if response.status_code >= 400:
                last_error = ProviderError(
                    _clip(response.text),
                    status=response.status_code,
                    provider="crustdata",
                )
                raise last_error
            return response.json()
        if last_error:
            raise last_error
        raise ProviderError("Crustdata request failed.", provider="crustdata")

    def _add_credits(self, raw: str | None) -> None:
        if not raw:
            return
        try:
            self.credits_used += float(raw)
        except ValueError:
            return

    def enrich_person(self, profile_url: str) -> dict[str, Any] | None:
        payload = self.post(
            "/person/enrich",
            {
                "professional_network_profile_urls": [profile_url],
                "fields": ["basic_profile", "social_handles", "experience", "education", "skills"],
            },
        )
        return _first_person(payload)

    def search_jobs(
        self,
        titles: list[str],
        *,
        country: str | None,
        since: str,
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        title_conditions = [
            {"field": "job_details.title", "type": "[.]", "value": title}
            for title in titles[:4]
            if title.strip()
        ]
        if not title_conditions:
            raise ProviderError("No target titles to search.", provider="crustdata")
        conditions: list[dict[str, Any]] = [
            {"op": "or", "conditions": title_conditions},
            {"field": "metadata.date_added", "type": "=>", "value": since},
        ]
        if country:
            conditions.append({"field": "location.country", "type": "=", "value": country})
        payload = self.post(
            "/job/search",
            {
                "filters": {"op": "and", "conditions": conditions},
                "fields": [
                    "job_details.title",
                    "job_details.url",
                    "job_details.category",
                    "content.description",
                    "company.basic_info.name",
                    "company.basic_info.primary_domain",
                    "location.raw",
                    "location.city",
                    "location.country",
                    "metadata.date_added",
                ],
                "sorts": [{"field": "metadata.date_added", "order": "desc"}],
                "limit": limit,
            },
        )
        listings = payload.get("job_listings") if isinstance(payload, dict) else None
        return list(listings or [])

    def enrich_company(self, *, company_id: int | None, domain: str | None) -> dict[str, Any] | None:
        if company_id:
            body: dict[str, Any] = {
                "crustdata_company_ids": [company_id],
                "fields": ["basic_info", "headcount", "funding", "hiring"],
            }
        elif domain:
            body = {
                "domains": [domain],
                "fields": ["basic_info", "headcount", "funding", "hiring"],
            }
        else:
            return None
        payload = self.post("/company/enrich", body)
        return _first_company(payload)

    def search_contacts(
        self,
        titles: list[str],
        *,
        company_id: int | None = None,
        domain: str | None = None,
        company_name: str | None = None,
        verified_email: bool = False,
    ) -> list[dict[str, Any]]:
        title_conditions = [
            {"field": "experience.employment_details.current.title", "type": "[.]", "value": title}
            for title in titles
            if title.strip()
        ]
        if domain:
            identity: dict[str, Any] = {
                "field": "experience.employment_details.current.company_website_domain",
                "type": "=",
                "value": domain,
            }
        elif company_id:
            identity = {
                "field": "experience.employment_details.current.company_id",
                "type": "=",
                "value": company_id,
            }
        elif company_name:
            identity = {
                "field": "experience.employment_details.current.company_name",
                "type": "=",
                "value": company_name,
            }
        else:
            return []
        conditions: list[dict[str, Any]] = [identity]
        if title_conditions:
            conditions.append({"op": "or", "conditions": title_conditions})
        if verified_email:
            conditions.append(
                {
                    "field": "experience.employment_details.current.business_email_verified",
                    "type": "=",
                    "value": True,
                }
            )
        payload = self.post(
            "/person/search",
            {
                "filters": {"op": "and", "conditions": conditions},
                "limit": 5,
            },
        )
        profiles = payload.get("profiles") if isinstance(payload, dict) else None
        return list(profiles or [])

    def business_email(self, profile_url: str) -> str | None:
        if not profile_url:
            return None
        payload = self.post(
            "/person/enrich",
            {
                "professional_network_profile_urls": [profile_url],
                "fields": ["contact.business_emails"],
            },
        )
        return _business_email(payload)


def _business_email(payload: Any) -> str | None:
    found: list[str] = []

    def walk(node: Any, in_business: bool) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                walk(value, in_business or key in {"business_emails", "business_email"})
        elif isinstance(node, list):
            for item in node:
                walk(item, in_business)
        elif in_business and isinstance(node, str) and "@" in node and "." in node.split("@")[-1]:
            found.append(node.strip())

    walk(payload, False)
    return found[0] if found else None


def _clip(text: str) -> str:
    text = " ".join(text.split())
    return text[:400] if text else "Crustdata returned an error."


def _first_person(payload: Any) -> dict[str, Any] | None:
    rows = payload if isinstance(payload, list) else []
    if not rows:
        return None
    matches = rows[0].get("matches") or []
    if not matches:
        return None
    return matches[0].get("person_data") or None


def _first_company(payload: Any) -> dict[str, Any] | None:
    rows = payload if isinstance(payload, list) else []
    if not rows:
        return None
    matches = rows[0].get("matches") or []
    if not matches:
        return None
    return matches[0].get("company_data") or None
