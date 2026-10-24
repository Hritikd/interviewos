from __future__ import annotations

import os

import streamlit as st

from interviewos.config import load_settings
from interviewos.crust import ProviderError
from interviewos.gmail import GmailConnector
from interviewos.models import Intake, Mandate
from interviewos.profile import extract_pdf
from interviewos.pipeline import Pipeline
from interviewos.store import Store

st.set_page_config(page_title="InterviewOS", page_icon="◆", layout="wide")

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,560;9..144,650&family=Outfit:wght@380;500;600&display=swap');
html, body, [class*="css"] { font-family: Outfit, sans-serif; }
h1, h2, h3 { font-family: Fraunces, serif !important; letter-spacing: -0.03em; }
.block-container { padding-top: 1.4rem; max-width: 1080px; }
.ios-kicker { letter-spacing: 0.16em; text-transform: uppercase; font-size: 0.72rem; color: #6d655b; }
.ios-mode { display: inline-block; border: 1px solid #1a1814; padding: 0.15rem 0.45rem; font-size: 0.72rem; letter-spacing: 0.08em; }
.ios-card { background: #faf7f1; border: 1px solid #d9d1c3; border-radius: 14px; padding: 1rem 1.1rem; margin-bottom: 0.8rem; }
.ios-hold { color: #8c3a2f; }
div[data-testid="stSidebar"] { background: #ebe4d6; }
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)


def _seed(name: str, default: str) -> None:
    if name not in st.session_state:
        st.session_state[name] = default


def settings():
    current = load_settings()
    for name, field in (
        ("CRUSTDATA_API_KEY", "crustdata_api_key"),
        ("GEMINI_API_KEY", "gemini_api_key"),
        ("COMPOSIO_API_KEY", "composio_api_key"),
    ):
        override = st.session_state.get(field, "")
        if override:
            os.environ[name] = override
            setattr(current, field, override)
    return current


def pipeline() -> Pipeline:
    cfg = settings()
    store = Store(cfg.data_dir / "interviewos.db")
    return Pipeline(cfg, store)


def mandate_from_form() -> Mandate:
    return Mandate(
        saved=bool(st.session_state.get("mandate_saved")),
        recipient_email=st.session_state.get("recipient_email", ""),
        allow_send=bool(st.session_state.get("allow_send")),
        daily_cap=1,
        candidate_name=st.session_state.get("candidate_name", ""),
    )


def intake_from_form() -> Intake:
    titles = [part.strip() for part in st.session_state.get("titles", "").split(",") if part.strip()]
    links = [part.strip() for part in st.session_state.get("portfolio", "").splitlines() if part.strip()]
    return Intake(
        linkedin_url=st.session_state.get("linkedin_url", ""),
        resume_text=st.session_state.get("resume_text", ""),
        target_titles=titles,
        geography=st.session_state.get("geography", "India"),
        portfolio_links=links[:3],
        mandate=mandate_from_form(),
    )


def main() -> None:
    cfg = settings()
    with st.sidebar:
        st.markdown("<div class='ios-kicker'>InterviewOS</div>", unsafe_allow_html=True)
        st.header("A recruiter that works for you")
        page = st.radio("View", ["Mission", "Cases", "Case"], key="page", label_visibility="collapsed")
        st.divider()
        counts = pipeline().store.counts()
        case_word = "case" if counts["cases"] == 1 else "cases"
        reply_word = "reply" if counts["replies"] == 1 else "replies"
        st.caption(
            f"{counts['cases']} {case_word} · {counts['replies']} {reply_word} · {counts['conversations']} confirmed"
        )
        with st.expander("Keys for this session"):
            if not st.session_state.get("crustdata_api_key") and cfg.crustdata_api_key:
                st.session_state["crustdata_api_key"] = cfg.crustdata_api_key
            elif "crustdata_api_key" not in st.session_state:
                st.session_state["crustdata_api_key"] = cfg.crustdata_api_key
            st.text_input("Crustdata", key="crustdata_api_key", type="password")
            if not st.session_state.get("gemini_api_key") and cfg.gemini_api_key:
                st.session_state["gemini_api_key"] = cfg.gemini_api_key
            elif "gemini_api_key" not in st.session_state:
                st.session_state["gemini_api_key"] = cfg.gemini_api_key
            st.text_input("Gemini", key="gemini_api_key", type="password")
            st.caption("Keys stay in this browser session. They are not written into the case file.")
        if st.button("Connect Gmail"):
            cfg = settings()
            try:
                st.session_state["gmail_url"] = GmailConnector(cfg.composio_api_key, cfg.composio_user_id).connect_url()
            except ProviderError as exc:
                st.error(str(exc))
        if st.session_state.get("gmail_url"):
            st.link_button("Open the Gmail login", st.session_state["gmail_url"])
        st.caption("The note is the application. Send it from Gmail only after you connect.")

    if page == "Mission":
        render_mission()
    elif page == "Cases":
        render_cases()
    else:
        render_case()


def render_mission() -> None:
    st.markdown("<div class='ios-kicker'>Mission</div>", unsafe_allow_html=True)
    st.title("Find roles that match the person, not just the job title.")
    st.write(
        "Applications disappear into a portal. Paste a LinkedIn URL and upload the resume PDF. "
        "Crustdata reads who you are, then keeps only live openings that match that background, "
        "and names a person who works at that company now."
    )
    left, right = st.columns(2)
    with left:
        st.text_input("LinkedIn URL", key="linkedin_url", placeholder="https://www.linkedin.com/in/…")
        st.file_uploader("Resume PDF", type=["pdf"], key="resume_pdf")
    with right:
        st.text_input("Your name", key="candidate_name")
        if "titles" not in st.session_state:
            st.session_state["titles"] = "Product Strategy, GTM, Deployment, Product Manager"
        if "geography" not in st.session_state:
            st.session_state["geography"] = "Bengaluru, India"
        st.text_input("Roles you want, comma separated", key="titles")
        st.text_input("Geography", key="geography")

    status = settings()
    st.caption(
        "Crustdata key "
        + ("ready" if status.crustdata_api_key else "missing")
        + " · Gemini key "
        + ("ready" if status.gemini_api_key else "missing")
    )
    resume_preview = _resume_from_session()
    if resume_preview:
        st.caption(f"Resume read, {len(resume_preview.split())} words.")

    error = st.session_state.pop("flash_error", None)
    if error:
        st.error(error)
    flash = st.session_state.pop("flash", None)
    if flash:
        st.success(flash)

    if st.button("Find matching roles", type="primary", on_click=_start_search):
        pass

    with st.expander("Demo, about two minutes"):
        st.markdown(
            """
1. Paste your LinkedIn URL and upload the resume PDF.
2. Find matching roles. Open one from the list.
3. Read the opening, the person who works there now, and the note.
4. The note is the application. Every claim points at a source.
            """
        )


def _open_case(case_id: str) -> None:
    st.session_state["active_case"] = case_id
    st.session_state["page"] = "Case"


def _resume_from_session() -> str:
    upload = st.session_state.get("resume_pdf")
    if upload is not None:
        try:
            text = extract_pdf(upload.getvalue())
        except Exception:
            st.session_state["flash_error"] = "That PDF could not be read. Export it as a text PDF and try again."
            return ""
        if text:
            st.session_state["resume_text"] = text
            return text
    return st.session_state.get("resume_text", "")


def _start_search() -> None:
    text = _resume_from_session()
    st.session_state["resume_text"] = text
    form = intake_from_form()
    try:
        ids = pipeline().find_roles(form)
    except (ProviderError, ValueError) as exc:
        st.session_state["flash_error"] = str(exc)
        return
    st.session_state["active_case"] = ids[0]
    st.session_state["page"] = "Cases"
    noun = "role" if len(ids) == 1 else "roles"
    st.session_state["flash"] = f"Found {len(ids)} {noun} that match the profile. Bank and credit-risk roles were dropped."


def render_cases() -> None:
    st.markdown("<div class='ios-kicker'>Cases</div>", unsafe_allow_html=True)
    st.title("Roles that match the profile")
    cases = pipeline().store.list_cases()
    if not cases:
        st.info("No cases yet. Start from Mission.")
        return
    profile = next(
        (note.removeprefix("Profile: ") for case in cases for note in case.score.notes if note.startswith("Profile: ")),
        "",
    )
    if profile:
        st.write(profile)
    for case in cases:
        person = case.contact.name if case.contact and case.contact.name else "No person yet"
        with st.container(border=True):
            top = st.columns([4, 2, 2])
            top[0].markdown(f"**{case.role_title}**  \n{case.company_name}")
            top[1].markdown(f"score {case.score.total}  \n{person}")
            top[2].markdown(f"{case.state}  \n{case.next_action}")
            st.caption(case.mode)
            if st.button("Open", key=f"open-{case.id}", on_click=_open_case, args=(case.id,)):
                pass


def render_case() -> None:
    case_id = st.session_state.get("active_case")
    store = pipeline().store
    case = store.get(case_id) if case_id else None
    if case is None:
        st.info("Open a case from the pipeline, or run a search.")
        return
    flash = st.session_state.pop("flash", None)
    if flash:
        st.success(flash)
    st.markdown(f"<span class='ios-mode'>{case.mode}</span>", unsafe_allow_html=True)
    st.title(case.role_title)
    st.subheader(case.company_name)
    meta = " · ".join(bit for bit in [case.location, case.state.replace("_", " "), f"score {case.score.total}"] if bit)
    st.caption(meta)
    if case.job_url:
        st.link_button("Open the posting", case.job_url)
    st.caption("Crustdata: read the profile, found this opening, resolved who works there now.")

    if case.hold_reasons:
        for reason in case.hold_reasons:
            st.error(reason)

    columns = st.columns(2)
    columns[0].markdown("**Why this company**")
    columns[0].write(case.why_company or "—")
    columns[1].markdown("**Why now**")
    columns[1].write(case.why_now or "—")
    columns = st.columns(2)
    columns[0].markdown("**Why you**")
    columns[0].write(case.why_me or "—")
    columns[1].markdown("**Why this person**")
    columns[1].write(case.why_person or "—")

    score = case.score
    st.caption(
        f"Heuristic, not a hiring probability. Role {score.role_fit}/35 · proof {score.proof}/30 · "
        f"timing {score.timing}/20 · contact {score.contact}/15."
    )
    for note in score.notes:
        st.caption(note)

    if case.intro:
        st.markdown("**Introduction**")
        st.write(case.intro.subject)
        st.code(case.intro.body, language=None)
        st.caption("Evidence in this note: " + ", ".join(case.intro.evidence_ids))

    with st.expander("Sources"):
        for item in case.evidence:
            date = item.source_date or "date unknown"
            st.markdown(f"**{item.id}** · {item.source} · `{item.field}` · {date}")
            st.write(item.excerpt)

    if st.button("Copy this note", type="primary"):
        try:
            updated = pipeline().apply(case.id, mandate_from_form())
        except ProviderError as exc:
            st.error(str(exc))
        else:
            st.session_state["active_case"] = updated.id
            st.success(updated.next_action)
            st.rerun()
    provider_email = case.contact.provider_email if case.contact else ""
    if not st.session_state.get("send_to") and provider_email:
        st.session_state["send_to"] = provider_email
    st.text_input(
        "Send the note to",
        key="send_to",
        placeholder="Only if Crustdata returned an email, or you already know the address",
    )
    if st.button("Send from Gmail"):
        address = st.session_state.get("send_to", "").strip()
        mandate = Mandate(
            saved=True,
            allow_send=True,
            recipient_email=address,
            daily_cap=1,
            candidate_name=case.candidate_name,
        )
        try:
            updated = pipeline().apply(case.id, mandate)
        except ProviderError as exc:
            st.error(str(exc))
        else:
            st.session_state["active_case"] = updated.id
            if updated.state == "outreach_sent":
                st.success(updated.next_action)
            else:
                st.error(updated.next_action)
            st.rerun()


if __name__ == "__main__":
    main()
else:
    main()
