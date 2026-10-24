from __future__ import annotations

import re
from io import BytesIO

from interviewos.textutil import excerpt_in_source

DEFAULT_TITLES = [
    "Product Manager",
    "Product Strategy",
    "GTM",
    "Deployment",
]


def proof_lines(resume_text: str, *, limit: int = 3) -> list[str]:
    """Keep resume lines only when the excerpt is contained in the pasted text."""
    proofs: list[str] = []
    for raw in resume_text.splitlines():
        line = " ".join(raw.strip(" -\t•").split())
        if len(line) < 40:
            continue
        if not excerpt_in_source(line, resume_text):
            continue
        proofs.append(line[:280])
        if len(proofs) >= limit:
            break
    return proofs


def normalize_linkedin(url: str) -> str:
    value = url.strip()
    if not value:
        return ""
    if "linkedin.com/in/" not in value.lower():
        raise ValueError("Use a LinkedIn profile URL that contains linkedin.com/in/.")
    if not value.startswith("http"):
        value = "https://" + value
    return value.split("?")[0].rstrip("/")


def person_name(person: dict | None) -> str:
    if not person:
        return ""
    basic = person.get("basic_profile") or {}
    return str(basic.get("name") or "").strip()


def person_title(person: dict | None) -> str:
    if not person:
        return ""
    basic = person.get("basic_profile") or {}
    title = str(basic.get("current_title") or basic.get("headline") or "").strip()
    return title


def person_location(person: dict | None) -> str:
    if not person:
        return ""
    location = (person.get("basic_profile") or {}).get("location") or {}
    if isinstance(location, str):
        return location
    return str(location.get("raw") or location.get("country") or "")


def current_employers(person: dict | None) -> list[dict]:
    if not person:
        return []
    details = ((person.get("experience") or {}).get("employment_details") or {})
    current = details.get("current") or []
    return list(current) if isinstance(current, list) else []


_GENERIC = {
    "product", "manager", "management", "senior", "lead", "head", "office", "founder",
    "the", "and", "for", "with", "from", "that", "this", "your", "role", "team",
    "india", "bengaluru", "bangalore", "at", "of", "in", "to", "a", "an",
    "work", "working", "years", "year", "data", "customer", "customers", "products",
    "taking", "using", "across", "their", "have", "been", "into", "over", "more",
    "company", "business", "solution", "solutions", "market", "markets",
}


def profile_terms(person: dict | None, resume_text: str) -> list[str]:
    """Distinctive words from the profile and resume. Generic title words are left out."""
    chunks = [resume_text or "", person_title(person)]
    skills = (person or {}).get("skills") or []
    if isinstance(skills, list):
        for skill in skills:
            chunks.append(skill if isinstance(skill, str) else str((skill or {}).get("name") or ""))
    details = ((person or {}).get("experience") or {}).get("employment_details") or {}
    for bucket in ("current", "past"):
        for role in (details.get(bucket) or [])[:4]:
            if isinstance(role, dict):
                chunks.append(str(role.get("title") or ""))
                chunks.append(str(role.get("name") or ""))
    found: list[str] = []
    seen: set[str] = set()
    for chunk in chunks:
        for raw in chunk.replace("&", " ").replace("/", " ").replace("-", " ").split():
            word = "".join(char for char in raw.lower() if char.isalnum())
            if len(word) < 3 or word in _GENERIC or word in seen:
                continue
            seen.add(word)
            found.append(word)
            if len(found) >= 16:
                return found
    return found


def work_brief(person: dict | None, resume_text: str) -> str:
    """The candidate's work, with the contact header left out."""
    parts: list[str] = []
    title = person_title(person)
    if title:
        parts.append(title)
    for role in current_employers(person)[:3]:
        label = " ".join(bit for bit in [str(role.get("title") or ""), str(role.get("name") or "")] if bit)
        if label:
            parts.append(label)
    for line in re.split(r"[\n|•]+", resume_text or ""):
        cleaned = " ".join(line.split())
        if len(cleaned) < 40 or "@" in cleaned or re.search(r"\d[\d\s+-]{8,}", cleaned):
            continue
        parts.append(cleaned)
        if len(parts) >= 8:
            break
    return " ".join(parts)[:1600]


def extract_pdf(data: bytes) -> str:
    from pypdf import PdfReader

    reader = PdfReader(BytesIO(data))
    return "\n".join((page.extract_text() or "") for page in reader.pages).strip()


def search_titles(preferred: list[str], current_title: str) -> list[str]:
    titles: list[str] = []
    specific = [title.strip() for title in (preferred or DEFAULT_TITLES) if title.strip()]
    # A bare "Product Manager" query fills the list with unrelated postings.
    ordered = [title for title in specific if title.lower() != "product manager"]
    ordered.extend(title for title in specific if title.lower() == "product manager")
    if current_title:
        short = current_title.split("|")[0].split(",")[0].strip()
        if 3 < len(short) <= 40 and " at " not in short.lower():
            ordered.insert(0, short)
    for title in ordered:
        if title not in titles:
            titles.append(title)
    return titles[:4]
