from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from interviewos.config import Settings
from interviewos.crust import CrustClient, ProviderError
from interviewos.gemini import plan_search, select_jobs
from interviewos.gmail import GmailConnector
from interviewos.match import contact_points, finance_profile, parse_job, passes_domain, route_for_title, score_job
from interviewos.models import CaseRecord, Contact, Intake, JobHit, Mandate
from interviewos.narrative import EvidenceBook, why_lines, write_intro
from interviewos.profile import (
    current_employers,
    normalize_linkedin,
    person_location,
    person_name,
    person_title,
    profile_terms,
    proof_lines,
    search_titles,
    work_brief,
)
from interviewos.store import Store
from interviewos.textutil import is_email, utc_now


class Pipeline:
    def __init__(self, settings: Settings, store: Store):
        self.settings = settings
        self.store = store

    def find_roles(self, intake: Intake) -> list[str]:
        if not intake.linkedin_url.strip() and not intake.resume_text.strip():
            raise ProviderError("Add a LinkedIn URL or paste a resume first.", provider="interviewos")
        linkedin = normalize_linkedin(intake.linkedin_url) if intake.linkedin_url.strip() else ""
        proofs = proof_lines(intake.resume_text)
        crust = CrustClient(self.settings.crustdata_api_key, self.settings.request_timeout_seconds)
        try:
            person = None
            if linkedin:
                try:
                    person = crust.enrich_person(linkedin)
                except ProviderError:
                    person = None
            brief = work_brief(person, intake.resume_text)
            plan = plan_search(self.settings.gemini_api_key, brief)
            focus = str(plan.get("focus") or "").strip() if plan else ""
            titles = _planned_titles(plan, intake.target_titles)
            terms = profile_terms(person, brief)
            since = (datetime.now(timezone.utc) - timedelta(days=60)).date().isoformat()
            country = "India" if "india" in intake.geography.lower() else None
            listings = _collect_jobs(crust, titles, country=country, since=since)
            geography_note = ""
            if not listings and country:
                listings = _collect_jobs(crust, titles, country=None, since=since)
                geography_note = "No India postings matched. These results are not limited to India."
            hits = [parse_job(raw) for raw in listings]
            if not finance_profile(brief):
                hits = [hit for hit in hits if passes_domain(hit, brief)]
            if not hits and not finance_profile(brief):
                sharper = ["AI Product Manager", "GTM Lead", "Forward Deployed", "Product Marketing"]
                listings = _collect_jobs(crust, sharper, country=country, since=since)
                hits = [hit for hit in (parse_job(raw) for raw in listings) if passes_domain(hit, brief)]
                titles = sharper
            if not hits:
                raise ProviderError(
                    "The live postings for those titles were banks and credit-risk roles. None match this profile.",
                    provider="crustdata",
                )
            for hit in hits:
                hit.score = score_job(hit, titles, proofs, profile_terms=terms)
            hits.sort(
                key=lambda hit: (hit.score.role_fit, hit.score.total, 1 if hit.company_domain and hit.url else 0),
                reverse=True,
            )
            background = focus or brief
            chosen = select_jobs(self.settings.gemini_api_key, background, hits)
            kept = []
            if chosen:
                kept = [hits[index] for index in chosen if hits[index].url and passes_domain(hits[index], brief)]
            if not kept:
                sharper = ["AI Product Manager", "GTM Lead", "Forward Deployed", "Product Marketing"]
                extra = _collect_jobs(crust, sharper, country=country, since=since)
                seen = {hit.url for hit in hits}
                for raw in extra:
                    hit = parse_job(raw)
                    if not hit.url or hit.url in seen or not passes_domain(hit, brief):
                        continue
                    hit.score = score_job(hit, sharper, proofs, profile_terms=terms)
                    hits.append(hit)
                    seen.add(hit.url)
                hits.sort(key=_demo_rank, reverse=True)
                kept = [hit for hit in hits if hit.url][:2]
                for hit in kept:
                    hit.score.notes.insert(0, "Best non-bank role from the live postings.")
            else:
                for hit in kept:
                    hit.score.notes.insert(0, "Gemini kept this role against your background.")
            strong = kept[:2]
            if focus:
                for hit in hits:
                    hit.score.notes.insert(0, "Profile: " + focus)
            pool = strong
            if not pool:
                raise ProviderError(
                    "Crustdata returned no non-bank roles for this profile.",
                    provider="crustdata",
                )
            ids: list[str] = []
            candidate = person_name(person) or intake.mandate.candidate_name or "I"
            for index, hit in enumerate(pool):
                case = self._shell(intake, hit, candidate, geography_note)
                if proofs:
                    book = EvidenceBook(case.mode)
                    book.add(
                        entity_id="candidate",
                        source="user.resume",
                        field="resume_line",
                        excerpt=proofs[0],
                        evidence_type="resume_proof",
                    )
                    case.evidence.extend(book.items)
                if person:
                    self._add_profile_evidence(case, person, linkedin)
                if hit in strong:
                    self._research(case, intake, crust, proofs)
                    self._place_draft(case)
                else:
                    case.state = "held"
                    case.hold_reasons = [hit.score.notes[0] if hit.score.notes else "This posting does not match your background."]
                    case.next_action = case.hold_reasons[0]
                self.store.save(case)
                ids.append(case.id)
            return ids
        finally:
            crust.close()

    def research_case(self, case_id: str, intake: Intake) -> CaseRecord:
        case = self._require(case_id)
        crust = CrustClient(self.settings.crustdata_api_key, self.settings.request_timeout_seconds)
        try:
            hit = JobHit(
                title=case.role_title,
                url=case.job_url,
                company_name=case.company_name,
                company_domain=case.company_domain,
                company_id=case.company_id,
                location=case.location,
                date_added=_evidence_date(case, "job_posting"),
            )
            self._research(case, intake, crust, proof_lines(intake.resume_text))
            self.store.save(case)
            return case
        finally:
            crust.close()

    def apply(self, case_id: str, mandate: Mandate) -> CaseRecord:
        case = self._require(case_id)
        if not mandate.allow_send:
            blockers = _research_blockers(case)
            case.hold_reasons = blockers
            case.next_action = blockers[0] if blockers else (
                "The note is the application. Copy it and send it to the person Crustdata resolved."
            )
            self._move(case, "held" if blockers else "ready", actor="operator", reason=case.next_action)
            return case
        case.recipient_email = mandate.recipient_email.strip()
        case.recipient_source = "mandate" if is_email(case.recipient_email) else None
        provider_email = case.contact.provider_email if case.contact else None
        if provider_email and provider_email.lower() == mandate.recipient_email.strip().lower():
            case.recipient_source = "provider"
        reasons = evaluate_guard(
            case,
            mandate,
            sends_today=self.store.sends_today(),
            for_send=mandate.allow_send,
        )
        if reasons:
            case.hold_reasons = reasons
            case.next_action = reasons[0]
            if case.state in {"ready", "qualified", "outreach_sent"}:
                self.store.transition(case, "held", actor="guard", reason=reasons[0])
            else:
                case.state = "held"
                self.store.save(case)
            return case

        gmail = GmailConnector(self.settings.composio_api_key, self.settings.composio_user_id)
        if not gmail.connected():
            case.hold_reasons = ["Gmail is not connected. Connect it, then apply again."]
            case.next_action = case.hold_reasons[0]
            self._move(case, "held", actor="gmail", reason=case.hold_reasons[0])
            return case

        assert case.intro is not None
        kind = "send" if mandate.allow_send else "draft"
        action_key = f"{kind}:{case.id}"
        if not self.store.record_action(action_key, case.id, kind, "pending", ""):
            existing = self.store.get_action(action_key) or {}
            case.next_action = f"Already {existing.get('status', 'recorded')}. {existing.get('detail', '')}"
            self.store.save(case)
            return case
        try:
            if mandate.allow_send:
                result = gmail.send(case.recipient_email or "", case.intro.subject, case.intro.body)
                status = "sent"
                state = "outreach_sent"
                reason = "Application email sent through Gmail."
            else:
                result = gmail.create_draft(case.recipient_email or "", case.intro.subject, case.intro.body)
                status = "drafted"
                state = "ready"
                reason = "Application draft created in Gmail. It has not been sent."
            detail = _draft_label(result)
            self.store.update_action(action_key, status, detail)
            case.hold_reasons = []
            case.next_action = reason
            if state == "outreach_sent" and case.state != "ready":
                self._move(case, "ready", actor="guard", reason="Guard passed.")
            self._move(case, state, actor="gmail", reason=reason, evidence_ids=case.intro.evidence_ids)
            return case
        except ProviderError as exc:
            uncertain = "timeout" in str(exc).lower() or "timed out" in str(exc).lower()
            status = "uncertain" if uncertain else "failed"
            self.store.update_action(action_key, status, str(exc))
            case.hold_reasons = [str(exc)]
            case.next_action = "Reconcile this Gmail action before trying again." if uncertain else str(exc)
            self.store.transition(case, "held", actor="gmail", reason=case.next_action)
            return case

    def recheck(self, case_id: str, mandate: Mandate) -> CaseRecord:
        case = self._require(case_id)
        case.recipient_email = mandate.recipient_email.strip() or None
        case.recipient_source = "mandate" if is_email(case.recipient_email) else None
        provider_email = case.contact.provider_email if case.contact else None
        if provider_email and case.recipient_email and provider_email.lower() == case.recipient_email.lower():
            case.recipient_source = "provider"
        reasons = _research_blockers(case)
        if mandate.allow_send:
            reasons = evaluate_guard(case, mandate, sends_today=self.store.sends_today(), for_send=True)
        case.hold_reasons = reasons
        target = "held" if reasons else "ready"
        case.next_action = reasons[0] if reasons else (
            "The note is the application. Copy it and send it to the person Crustdata resolved."
        )
        self._move(case, target, actor="guard", reason=case.next_action)
        return case

    def record_reply(self, case_id: str, reply_text: str, agreed_time: str) -> CaseRecord:
        from interviewos.textutil import classify_reply

        case = self._require(case_id)
        target = classify_reply(reply_text, agreed_time)
        if case.state == "ready":
            self.store.transition(case, "outreach_sent", actor="operator", reason="Marked sent before the pasted reply.")
        if case.state == "outreach_sent" and target == "meeting_confirmed":
            self.store.transition(case, "replied", actor="manual_input", reason="Recipient replied.")
            self.store.transition(case, "scheduling", actor="manual_input", reason="Working toward a time.")
            self.store.transition(
                case,
                "meeting_confirmed",
                actor="manual_input",
                reason=f"Agreed time: {agreed_time.strip()}",
            )
        elif case.state == "outreach_sent":
            self.store.transition(case, target, actor="manual_input", reason="Pasted reply. Provenance: manual_input.")
        elif case.state == "replied" and target == "meeting_confirmed":
            self.store.transition(case, "scheduling", actor="manual_input", reason="A time was added.")
            self.store.transition(case, "meeting_confirmed", actor="manual_input", reason=agreed_time.strip())
        else:
            raise ProviderError(
                f"A reply cannot be filed while the case is {case.state}.",
                provider="interviewos",
            )
        case = self._require(case_id)
        if target == "closed":
            case.next_action = "Closed from the reply."
        elif case.state == "meeting_confirmed":
            case.next_action = f"Conversation confirmed for {agreed_time.strip()}."
        else:
            case.next_action = "Reply is recorded. A meeting needs an agreed time."
        self.store.save(case)
        return case

    def _research(self, case: CaseRecord, intake: Intake, crust: CrustClient, proofs: list[str]) -> None:
        book = EvidenceBook(case.mode)
        if not any(item.evidence_type == "job_posting" for item in case.evidence):
            posting = case.role_title
            if case.job_url:
                posting = f"{case.role_title} ({case.job_url})"
            book.add(
                entity_id=str(case.company_id or case.company_domain or case.company_name),
                source="crustdata.job",
                field="job_details.title",
                excerpt=posting,
                evidence_type="job_posting",
                source_date=_evidence_date(case, "job_posting"),
            )
        company = None
        try:
            company = crust.enrich_company(company_id=case.company_id, domain=case.company_domain)
        except ProviderError:
            company = None
        if company:
            basic = company.get("basic_info") or {}
            enriched_name = str(basic.get("name") or "")
            if enriched_name and not _names_agree(enriched_name, case.company_name):
                company = None
        if company:
            basic = company.get("basic_info") or {}
            if basic.get("primary_domain") and not case.company_domain:
                case.company_domain = str(basic["primary_domain"])
            blurb = basic.get("short_description") or basic.get("description")
            if blurb:
                book.add(
                    entity_id=str(case.company_id or case.company_name),
                    source="crustdata.company",
                    field="basic_info.description",
                    excerpt=str(blurb)[:300],
                    evidence_type="company",
                )
            funding = company.get("funding") or {}
            round_name = funding.get("last_round_type") or funding.get("last_funding_round_type")
            if round_name:
                book.add(
                    entity_id=str(case.company_id or case.company_name),
                    source="crustdata.company",
                    field="funding.last_round_type",
                    excerpt=f"Crustdata funding record: last round {round_name}.",
                    evidence_type="funding",
                )
        contact = self._find_contact(crust, case)
        case.contact = contact
        if contact and contact.resolved:
            book.add(
                entity_id=contact.profile_url or contact.name,
                source="crustdata.person",
                field="experience.employment_details.current",
                excerpt=(
                    f"{contact.name} is {contact.title or 'an employee'} at {contact.company_name}."
                ),
                evidence_type="contact",
            )
        if proofs and not any(item.evidence_type == "resume_proof" for item in case.evidence):
            book.add(
                entity_id="candidate",
                source="user.resume",
                field="resume_line",
                excerpt=proofs[0],
                evidence_type="resume_proof",
            )
        case.evidence = _renumber(_merge_evidence(case.evidence, book.items))
        case.score.contact = contact_points(contact.route if contact else "unresolved")
        lines = why_lines(case.evidence, contact, case.company_name, case.role_title)
        case.why_company = lines["why_company"]
        case.why_now = lines["why_now"]
        case.why_me = lines["why_me"]
        case.why_person = lines["why_person"]
        case.intro = write_intro(case.candidate_name, case.role_title, case.company_name, case.evidence, contact)
        case.opportunity_type = "verified_opening" if case.job_url else "insufficient_evidence"
        blocking = _research_blockers(case)
        if blocking:
            case.state = "held"
            case.hold_reasons = blocking
            case.next_action = blocking[0]
        else:
            case.state = "ready"
            case.hold_reasons = []
            case.next_action = "The note is the application. Copy it and send it to the person Crustdata resolved."

    def _find_contact(self, crust: CrustClient, case: CaseRecord) -> Contact | None:
        if not case.company_id and not case.company_domain and not case.company_name:
            return Contact(name="", company_name=case.company_name, route="unresolved", resolved=False)
        queries = [
            ["Recruiter", "Talent Acquisition"],
            ["Hiring Manager", "Head of Talent"],
        ]
        profiles: list[dict] = []
        for verified in (True, False):
            for titles in queries:
                try:
                    profiles = crust.search_contacts(
                        titles,
                        company_id=case.company_id,
                        domain=case.company_domain,
                        company_name=case.company_name,
                        verified_email=verified,
                    )
                except ProviderError:
                    profiles = []
                if profiles:
                    break
            if profiles:
                break
        if not profiles:
            return Contact(name="", company_name=case.company_name, company_id=case.company_id, route="unresolved")
        contact = _contact_from_profile(profiles[0], case.company_id, case.company_name, case.company_domain)
        if contact.profile_url and not contact.provider_email:
            try:
                contact.provider_email = crust.business_email(contact.profile_url)
            except ProviderError:
                contact.provider_email = None
        return contact

    def _place_draft(self, case: CaseRecord) -> None:
        contact = case.contact
        email = contact.provider_email if contact else None
        if case.state != "ready" or case.intro is None:
            return
        if not email or contact is None:
            case.next_action = "The note is ready. Crustdata did not return a work email for this person."
            return
        case.recipient_email = email
        case.recipient_source = "provider"
        try:
            gmail = GmailConnector(self.settings.composio_api_key, self.settings.composio_user_id)
            if not gmail.connected():
                case.next_action = (
                    f"Draft is ready for {contact.name} at {email}. "
                    "It is on this page. Gmail did not connect, so it is not in your inbox yet."
                )
                return
            gmail.create_draft(email, case.intro.subject, case.intro.body)
            case.next_action = f"Draft is in Gmail for {contact.name} at {email}. It has not been sent."
        except ProviderError:
            case.next_action = f"Draft is written for {contact.name} at {email}. Gmail did not accept it yet."

    def _add_profile_evidence(self, case: CaseRecord, person: dict, linkedin: str) -> None:
        book = EvidenceBook(case.mode)
        title = person_title(person)
        employers = current_employers(person)
        employer = employers[0].get("name") if employers else ""
        if title:
            excerpt = title if not employer else f"{title} at {employer}"
            book.add(
                entity_id=linkedin or person_name(person),
                source="crustdata.person",
                field="basic_profile.current_title",
                excerpt=excerpt,
                evidence_type="profile_title",
            )
        location = person_location(person)
        if location:
            book.add(
                entity_id=linkedin or person_name(person),
                source="crustdata.person",
                field="basic_profile.location",
                excerpt=location,
                evidence_type="profile_location",
            )
        case.evidence.extend(book.items)

    def _shell(self, intake: Intake, hit: JobHit, candidate: str, geography_note: str) -> CaseRecord:
        now = utc_now()
        case = CaseRecord(
            id=uuid.uuid4().hex[:12],
            mode="LIVE DATA",
            state="researching",
            opportunity_type="verified_opening" if hit.url else "insufficient_evidence",
            company_name=hit.company_name,
            company_domain=hit.company_domain,
            company_id=hit.company_id,
            role_title=hit.title,
            job_url=hit.url,
            location=hit.location,
            score=hit.score,
            candidate_name=candidate,
            created_at=now,
            updated_at=now,
            recipient_email=intake.mandate.recipient_email or None,
            recipient_source="mandate" if is_email(intake.mandate.recipient_email) else None,
        )
        if hit.date_added:
            book = EvidenceBook("LIVE DATA")
            book.add(
                entity_id=str(hit.company_id or hit.company_name),
                source="crustdata.job",
                field="metadata.date_added",
                excerpt=f"{hit.title} at {hit.company_name}, added {hit.date_added[:10]}.",
                evidence_type="job_posting",
                source_date=hit.date_added,
            )
            case.evidence.extend(book.items)
        if geography_note:
            case.score.notes.append(geography_note)
        return case

    def _move(self, case: CaseRecord, state: str, *, actor: str, reason: str, evidence_ids: list[str] | None = None) -> None:
        if case.state == state:
            self.store.save(case)
            return
        self.store.transition(case, state, actor=actor, reason=reason, evidence_ids=evidence_ids)

    def _require(self, case_id: str) -> CaseRecord:
        case = self.store.get(case_id)
        if case is None:
            raise ProviderError("That case is not on file.", provider="interviewos")
        return case


def _demo_rank(hit: JobHit) -> tuple:
    title = hit.title.lower()
    bonus = sum(10 for word in ("ai", "gtm", "go-to-market", "deployment", "deployed", "strategy") if word in title)
    return (bonus, hit.score.role_fit, hit.score.total, 1 if hit.company_domain else 0)


def _planned_titles(plan: dict | None, preferred: list[str]) -> list[str]:
    titles: list[str] = []
    for title in (plan or {}).get("titles") or []:
        cleaned = str(title).strip()
        if cleaned and cleaned.lower() != "product manager" and cleaned not in titles:
            titles.append(cleaned)
    if len(titles) < 2:
        for title in search_titles(preferred, ""):
            if title.lower() != "product manager" and title not in titles:
                titles.append(title)
    return (titles or ["AI Product Manager", "Product Strategy", "GTM Lead"])[:4]


def _collect_jobs(crust: CrustClient, titles: list[str], *, country: str | None, since: str) -> list[dict]:
    """Search one title at a time so a generic title cannot crowd out the specific ones."""
    found: list[dict] = []
    seen: set[str] = set()
    for title in titles:
        try:
            batch = crust.search_jobs([title], country=country, since=since, limit=4)
        except ProviderError:
            continue
        for job in batch:
            details = job.get("job_details") or {}
            key = str(details.get("url") or details.get("title") or "")
            company = ((job.get("company") or {}).get("basic_info") or {}).get("name") or ""
            marker = f"{key}|{company}"
            if marker in seen:
                continue
            seen.add(marker)
            found.append(job)
    return found


def _names_agree(left: str, right: str) -> bool:
    skip = {"the", "and", "ltd", "limited", "private", "pvt", "inc", "bank", "group"}

    def words(value: str) -> set[str]:
        return {word for word in value.lower().replace("&", " ").split() if len(word) > 2 and word not in skip}

    return bool(words(left) & words(right))


def _contact_from_profile(
    profile: dict,
    company_id: int | None,
    company_name: str,
    domain: str | None = None,
) -> Contact:
    basic = profile.get("basic_profile") or {}
    handles = (profile.get("social_handles") or {}).get("professional_network_identifier") or {}
    current = ((profile.get("experience") or {}).get("employment_details") or {}).get("current") or []
    matched = None
    for role in current:
        role_company_id = role.get("crustdata_company_id") or role.get("company_id")
        employer = str(role.get("name") or "")
        website = str(role.get("company_website") or role.get("company_website_domain") or "")
        try:
            id_match = company_id is not None and int(role_company_id) == int(company_id)
        except (TypeError, ValueError):
            id_match = False
        name_match = bool(employer and company_name and company_name.lower() in employer.lower())
        domain_match = bool(domain and domain.lower() in website.lower())
        if id_match or domain_match or name_match:
            matched = role
            break
    role = matched or (current[0] if current else {})
    title = str(role.get("title") or basic.get("current_title") or "")
    employer = str(role.get("name") or "")
    verified = matched is not None
    email = None
    for key in ("business_email", "work_email"):
        if isinstance(profile.get(key), str) and is_email(profile[key]):
            email = profile[key]
            break
    return Contact(
        name=str(basic.get("name") or ""),
        title=title,
        profile_url=handles.get("profile_url"),
        company_name=employer or company_name,
        company_id=company_id,
        route=route_for_title(title),  # type: ignore[arg-type]
        resolved=bool(basic.get("name")),
        affiliation_verified=verified,
        provider_email=email,
    )


def _renumber(evidence: list) -> list:
    for index, item in enumerate(evidence, start=1):
        item.id = f"ev_{index}"
    return evidence


def _merge_evidence(existing: list, new_items: list) -> list:
    seen = {(item.source, item.field, item.excerpt) for item in existing}
    merged = list(existing)
    for item in new_items:
        key = (item.source, item.field, item.excerpt)
        if key in seen:
            continue
        seen.add(key)
        if any(old.id == item.id for old in merged):
            item.id = f"ev_{len(merged) + 1}"
        merged.append(item)
    return merged


def _evidence_date(case: CaseRecord, evidence_type: str) -> str | None:
    for item in case.evidence:
        if item.evidence_type == evidence_type and item.source_date:
            return item.source_date
    return None


def _research_blockers(case: CaseRecord) -> list[str]:
    """The case is done when Crustdata has a real opening and a current employee. Email is optional."""
    reasons: list[str] = []
    if not case.job_url and not any(item.evidence_type == "job_posting" for item in case.evidence):
        reasons.append("No live opening was found.")
    if case.contact is None or not case.contact.resolved:
        reasons.append("Crustdata did not resolve a current employee at this company.")
    elif not case.contact.affiliation_verified:
        reasons.append("The contact's current company does not match this opening. Re-resolve before sending.")
    return reasons


def _draft_label(result: dict) -> str:
    for key in ("draft_id", "id", "message_id"):
        if result.get(key):
            return str(result[key])
    nested = result.get("data")
    if isinstance(nested, dict):
        for key in ("draft_id", "id", "message_id"):
            if nested.get(key):
                return str(nested[key])
    return "gmail accepted the request"
