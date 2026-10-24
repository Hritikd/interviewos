from __future__ import annotations

from datetime import datetime, timezone

from interviewos.models import JobHit, Score


def parse_job(raw: dict) -> JobHit:
    details = raw.get("job_details") or {}
    company = raw.get("company") or {}
    basic = company.get("basic_info") or company
    location = raw.get("location") or {}
    metadata = raw.get("metadata") or {}
    company_id = _as_int(basic.get("crustdata_company_id") or basic.get("company_id"))
    content = raw.get("content") or {}
    description = str(details.get("description") or content.get("description") or "")
    excerpt = " ".join(description.split())[:320]
    loc_bits = [location.get("city"), location.get("country"), location.get("raw")]
    loc = next((str(bit) for bit in loc_bits if bit), None)
    return JobHit(
        title=str(details.get("title") or "Untitled role"),
        url=details.get("url") or None,
        company_name=str(basic.get("name") or "Unknown company"),
        company_domain=_domain(basic.get("primary_domain") or basic.get("website")),
        company_id=company_id,
        location=loc,
        category=details.get("category"),
        date_added=metadata.get("date_added"),
        description_excerpt=excerpt,
    )


def finance_role(job: JobHit) -> bool:
    company = f"{job.company_name} {job.company_domain or ''}".lower()
    title = job.title.lower()
    description = (job.description_excerpt or "").lower()
    company_words = set(company.replace("&", " ").replace(",", " ").replace("-", " ").split())
    if "citi" in company_words or "citigroup" in company_words:
        return True
    if any(name in company for name in ("bank", "barclays", "jpmorgan", "jp morgan", "hsbc", "citibank", "goldman", "morgan stanley", "hdfc", "icici", "kotak", "nbfc")):
        return True
    text = f"{title} {description}"
    if " bfs" in f" {title}" or "bfs consulting" in text:
        return True
    return any(marker in text for marker in ("credit risk", "wholesale credit", "retail banking", "core banking", "investment banking"))


def finance_profile(text: str) -> bool:
    blob = (text or "").lower()
    return any(marker in blob for marker in ("credit risk", "nbfc", "retail banking", "investment banking", "underwriting", "core banking"))


def passes_domain(job: JobHit, profile_text: str) -> bool:
    """Pass/fail from the traces: an AI or GTM profile must not be handed a bank role."""
    if finance_profile(profile_text):
        return True
    return not finance_role(job)


def score_job(
    job: JobHit,
    titles: list[str],
    proofs: list[str],
    *,
    now: datetime | None = None,
    profile_terms: list[str] | None = None,
) -> Score:
    now = now or datetime.now(timezone.utc)
    notes: list[str] = []
    title_l = job.title.lower()
    blob = f"{job.title} {job.company_name} {job.description_excerpt}".lower()
    hits = [title for title in titles if title.lower() in title_l or _token_overlap(title, job.title)]
    matched_terms = [term for term in (profile_terms or []) if term.lower() in blob]
    if profile_terms is not None:
        if hits and len(matched_terms) >= 2:
            role_fit = 35
            notes.append("Matches your background: " + ", ".join(matched_terms[:4]) + ".")
        elif hits and matched_terms:
            role_fit = 16
            notes.append("Title matches, and the posting mentions " + matched_terms[0] + ".")
        elif hits:
            role_fit = 8
            notes.append("The title matches. The posting does not match your background.")
        else:
            role_fit = 4
            notes.append("This posting does not match the roles or the background.")
    elif hits:
        role_fit = 35
        notes.append("Title overlaps " + ", ".join(hits[:2]) + ".")
    else:
        role_fit = 12
        notes.append("Title is only a weak match to the target roles.")

    proof_hit = False
    for proof in proofs:
        tokens = [word for word in proof.lower().split() if len(word) > 4][:8]
        if any(word in title_l or word in job.description_excerpt.lower() for word in tokens):
            proof_hit = True
            break
    proof = 30 if proof_hit else (15 if proofs else 0)
    notes.append("A resume line shares wording with this role." if proof_hit else "No resume line matched this posting.")

    timing = 4
    posted = _parse_date(job.date_added)
    if posted is not None:
        age_days = (now - posted).days
        if age_days <= 14:
            timing = 20
            notes.append(f"Posted {age_days} days ago.")
        elif age_days <= 45:
            timing = 12
            notes.append(f"Posted {age_days} days ago.")
        else:
            timing = 6
            notes.append(f"Posted {age_days} days ago.")
    else:
        notes.append("Posting date is unknown.")

    return Score(role_fit=role_fit, proof=proof, timing=timing, contact=0, notes=notes)


def contact_points(route: str) -> int:
    if route == "recruiter":
        return 15
    if route == "functional_lead":
        return 10
    return 0


def route_for_title(title: str) -> str:
    lowered = title.lower()
    if any(word in lowered for word in ("recruit", "talent", "people partner", "sourcer")):
        return "recruiter"
    if any(word in lowered for word in ("head", "director", "vp", "vice president", "chief", "founder", "manager")):
        return "functional_lead"
    return "unresolved"


def _token_overlap(left: str, right: str) -> bool:
    left_tokens = {word for word in left.lower().split() if len(word) > 3}
    right_tokens = {word for word in right.lower().split() if len(word) > 3}
    return len(left_tokens & right_tokens) >= 2


def _as_int(value: object) -> int | None:
    try:
        if value is None or value == "":
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _domain(value: object) -> str | None:
    if not value:
        return None
    text = str(value).strip().lower()
    text = text.removeprefix("https://").removeprefix("http://").split("/")[0]
    return text.removeprefix("www.") or None


def _parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    raw = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed
