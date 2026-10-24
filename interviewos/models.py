from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

DataMode = Literal["LIVE DATA", "RECORDED REPLAY", "SYNTHETIC TEST"]
CaseState = Literal[
    "intake",
    "researching",
    "qualified",
    "ready",
    "held",
    "outreach_sent",
    "replied",
    "scheduling",
    "meeting_confirmed",
    "paused",
    "closed",
    "failed",
]
OpportunityType = Literal["verified_opening", "inferred_need", "insufficient_evidence"]
ContactRoute = Literal["recruiter", "functional_lead", "unresolved"]


class Evidence(BaseModel):
    id: str
    entity_id: str
    source: str
    field: str
    excerpt: str
    retrieved_at: str
    source_date: str | None = None
    evidence_type: str
    mode: DataMode


class Contact(BaseModel):
    name: str
    title: str = ""
    profile_url: str | None = None
    company_name: str = ""
    company_id: int | None = None
    route: ContactRoute = "unresolved"
    resolved: bool = False
    affiliation_verified: bool = False
    provider_email: str | None = None


class Intro(BaseModel):
    subject: str
    body: str
    evidence_ids: list[str]


class Score(BaseModel):
    role_fit: int = 0
    proof: int = 0
    timing: int = 0
    contact: int = 0
    notes: list[str] = Field(default_factory=list)

    @property
    def total(self) -> int:
        return self.role_fit + self.proof + self.timing + self.contact


class TimelineEvent(BaseModel):
    at: str
    actor: str
    from_state: str
    to_state: str
    reason: str
    evidence_ids: list[str] = Field(default_factory=list)


class CaseRecord(BaseModel):
    id: str
    mode: DataMode
    state: CaseState
    opportunity_type: OpportunityType
    company_name: str
    company_domain: str | None = None
    company_id: int | None = None
    role_title: str
    job_url: str | None = None
    location: str | None = None
    contact: Contact | None = None
    why_company: str = ""
    why_now: str = ""
    why_me: str = ""
    why_person: str = ""
    evidence: list[Evidence] = Field(default_factory=list)
    intro: Intro | None = None
    score: Score = Field(default_factory=Score)
    next_action: str = ""
    hold_reasons: list[str] = Field(default_factory=list)
    recipient_email: str | None = None
    recipient_source: str | None = None
    candidate_name: str = ""
    timeline: list[TimelineEvent] = Field(default_factory=list)
    created_at: str
    updated_at: str
    related_roles: list[str] = Field(default_factory=list)


class Mandate(BaseModel):
    saved: bool = False
    recipient_email: str = ""
    allow_send: bool = False
    daily_cap: int = 1
    candidate_name: str = ""


class Intake(BaseModel):
    linkedin_url: str = ""
    resume_text: str = ""
    target_titles: list[str] = Field(default_factory=list)
    geography: str = "India"
    portfolio_links: list[str] = Field(default_factory=list)
    mandate: Mandate = Field(default_factory=Mandate)


class JobHit(BaseModel):
    title: str
    url: str | None = None
    company_name: str
    company_domain: str | None = None
    company_id: int | None = None
    location: str | None = None
    category: str | None = None
    date_added: str | None = None
    description_excerpt: str = ""
    score: Score = Field(default_factory=Score)
