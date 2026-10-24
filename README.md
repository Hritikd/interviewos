# InterviewOS

**The recruiter that works for the candidate.**

Give it your LinkedIn URL and your resume PDF. It reads who you are on Crustdata's live graph, finds the one or two open roles that match the work you have actually done, finds a recruiter or hiring manager who works at that company today with a verified work email, and hands you a ready-to-send note where every claim is traced to a source.

Built in one day at ContextCon Build, the Crustdata Agentic Services Hackathon (Bengaluru, 24 October 2026). The brief was software that does a whole service job itself. The service job here is recruiting, pointed at the job seeker instead of the employer.

---

## Contents

1. [Why this exists](#why-this-exists)
2. [What it does in the demo](#what-it-does-in-the-demo)
3. [How Crustdata is used](#how-crustdata-is-used)
4. [Architecture](#architecture)
5. [Rules the system will not break](#rules-the-system-will-not-break)
6. [Evals: how we fixed the bank bias](#evals-how-we-fixed-the-bank-bias)
7. [Setup](#setup)
8. [Running and testing](#running-and-testing)
9. [Project layout](#project-layout)
10. [Approaches considered and what we learned](#approaches-considered-and-what-we-learned)
11. [Known limits](#known-limits)

---

## Why this exists

Every recruiting tool sells to employers. The candidate side is a portal: upload a resume, answer 40 fields, hear nothing. A good recruiter does something different. They read your background, pick the few roles you can really get, find the person hiring, and write a short note that lands. InterviewOS does that job for you, with a hard cap of two roles, no guessed emails, and nothing sent without your review.

## What it does in the demo

The whole flow runs on one Streamlit page in under two minutes.

1. **Mission.** Paste a LinkedIn URL, upload a resume PDF, optionally add target titles and a city. Click **Find matching roles**.
2. **Profile.** Crustdata enriches the LinkedIn profile (current employer, title, history). The PDF is read locally. A one-sentence profile summary is produced and shown at the top of the results.
3. **Roles.** Crustdata's job index is searched one title at a time, India first, then unscoped. Bank, NBFC, and credit-risk postings are dropped unless the candidate's own background is finance. Gemini is asked to keep at most two postings that match the background; if it keeps none, the best remaining non-bank postings are shown rather than an empty screen.
4. **Person.** For each kept role, Crustdata person search finds someone who works at that company **now**, preferring Recruiter and Talent Acquisition titles, then Hiring Manager and Head of Talent. Current employment is verified by company id, domain, or name across all of the person's current roles.
5. **Email.** Crustdata person enrich returns the business email when one exists. If none exists, the case says so. No address is ever constructed.
6. **Note.** A short template note is built from stored evidence: the opening, the resume line that proves fit (an exact substring of the resume), and the contact. Each sentence carries an evidence id you can inspect under **Sources**.
7. **Send.** Copy the note, or connect Gmail through Composio and place it as a draft. Sending requires an explicit click and a recipient that matches the verified contact. Daily cap is one.

## How Crustdata is used

Crustdata is the only data vendor. Four endpoints carry the product.

| Step | Endpoint | What we ask for | Why it matters |
|---|---|---|---|
| Understand the candidate | `POST /person/enrich` with `professional_network_profile_urls` | current and past employment, title, location | the profile drives the search, not a keyword box |
| Find live openings | `POST /job/search` | `job_details.title`, `job_details.url`, `content.description`, `company.basic_info.name`, `company.basic_info.primary_domain`, `location.*`, `metadata.date_added` | a posting is the only thing that counts as a verified opening |
| Find the person hiring | `POST /person/search` filtered on `current.company_website_domain` (or `current.company_id` / `current.company_name`) and exact title `[.]` | people employed at the company today | a name match is not enough; affiliation must be current |
| Get a real address | `POST /person/enrich` with `fields=["contact.business_emails"]` | `person_data.contact.business_emails` | the email comes from Crustdata or it does not exist |

Implementation notes that cost us time, kept here so they do not cost you time:

- API header `x-api-version: 2025-11-01`. One retry on 429/502/503, none on 401.
- Title filter `[.]` is an exact phrase. `(.)` is typo-tolerant and matched "Project Manager" for "Product Manager".
- `company.basic_info.crustdata_company_id` is a locked return field on hackathon keys (403). `company.basic_info.company_id` is a valid *filter* but not a valid *return* field. Use `primary_domain` to join companies.
- `job_details.description` is not returnable; use `content.description`.
- Company enrich by domain can return a different company. We only accept an enrich result when the names agree, and we never overwrite the posting's company name.
- `/person/contact/enrich` is 403 on hackathon keys. Business emails are available on `/person/enrich` with the `contact.business_emails` field.
- A person can hold several current roles. The first role may be a different employer. Walk all of them.

## Architecture

```
app.py (Streamlit)
  └─ interviewos/pipeline.py        orchestrates one search → cases
       ├─ profile.py                 PDF text, proof lines, profile terms, work brief
       ├─ crust.py                   Crustdata client (person, job, company, email)
       ├─ gemini.py                  plan_search (titles + focus), select_jobs (keep ≤2)
       ├─ match.py                   parse_job, score_job, finance gate
       ├─ narrative.py               template note built only from stored evidence
       ├─ guard.py                   send guard: mandate, evidence, affiliation, recipient
       ├─ gmail.py                   Composio Gmail: draft / send, never auto-send
       ├─ store.py                   SQLite, case lifecycle, allowed transitions
       └─ models.py                  Intake, Case, Evidence, Score, Mandate
```

**Score** is a heuristic to order cases, not a hiring probability: role fit 35, resume proof 30, timing 20, contact 15. A role fit of 35 needs a title match plus at least two distinctive profile terms, so generic words like "data" and "work" cannot carry a bank posting to the top.

**Case lifecycle** lives in `store.py`. Three modes: LIVE DATA, RECORDED REPLAY, SYNTHETIC TEST. A failed live call surfaces an error; it never swaps in a fixture silently. Synthetic cases cannot send real email.

## Rules the system will not break

- Nothing is invented: no employers, tenure, metrics, or resume claims. A resume line used as proof must be a substring of the uploaded text.
- A job posting is the only path to `verified_opening`. Funding or headcount is timing context, not proof of a role.
- A contact is resolved by company id or domain plus **current** employment. Stale affiliation blocks send.
- The email address comes from Crustdata or the case stops. No pattern guessing.
- Maximum two roles per search, one send per day, and nothing is sent without an explicit click.
- No Easy Apply, no Greenhouse or Lever applications, no bulk outreach.

## Evals: how we fixed the bank bias

The first live run returned Canara Bank UPI, CSB Bank cash management, JPMorgan wholesale credit risk, and Barclays for an enterprise-AI GTM profile. The scorer loved them because "data", "market", and "work" overlapped.

We followed the error-analysis method Hamel Husain and Shreya Shankar describe: read the real traces, name the failure mode, write binary pass/fail checks from those traces, and iterate until they pass. No 1–5 rubric.

- Failure mode named: `finance_mismatch`.
- `tests/test_fit.py` holds the real postings as fixtures. Canara, CSB, JPMorgan, Barclays, Citi, and Cognizant BFS Consulting must fail `passes_domain` for a non-finance profile. An Optum AI product-marketing role must pass. A credit-risk profile may keep Canara.
- Fixes that came out of the traces: a company-level finance gate (name and domain, not words in a job description), the exact-phrase title operator, one title per search so a generic title cannot fill the result window, a wider stopword list so two generic words cannot score 35, and sharper fallback titles (AI Product Manager, GTM Lead, Forward Deployed, Product Marketing).
- Second failure found by the same method: the gate was too strict and the page showed an empty error while postings existed. Fixed by always surfacing the best non-bank postings when the model keeps none.

Run the suite with `uv run pytest`. Eleven tests, all binary.

## Setup

Requirements: Python 3.12+, [uv](https://github.com/astral-sh/uv).

```bash
git clone https://github.com/Hritikd/interviewos.git
cd interviewos
uv sync --group dev
cp .env.example .env
```

Fill `.env`:

| Variable | Required | Where to get it |
|---|---|---|
| `CRUSTDATA_API_KEY` | yes | Crustdata dashboard. Hackathon keys work; see the locked fields above. |
| `GEMINI_API_KEY` | recommended | Google AI Studio, free tier. Used only to choose search titles and keep/reject postings. Without it, titles come from the resume headline and the heuristic ranker alone. Model: `gemini-3.8-flash`. |
| `COMPOSIO_API_KEY` | optional | Composio. Only needed to place the draft inside Gmail. Without it the note stays on the case page. |

Keys can also be entered in the sidebar for the session. Never commit `.env`.

## Running and testing

```bash
uv run streamlit run app.py          # http://localhost:8501
uv run pytest -q                     # 11 binary tests
```

Demo path: Mission → paste LinkedIn URL → upload PDF → Find matching roles → open a case → read the profile sentence, the role, the person, the note → Copy this note, or Connect Gmail → Send from Gmail.

Data is stored in `data/interviewos.db` (gitignored). Old cases from previous searches stay in the list, newest first.

## Project layout

```
.
├── app.py                       Streamlit UI: Mission, Cases, Case
├── interviewos/
│   ├── config.py                Settings, .env loading
│   ├── crust.py                 Crustdata API client
│   ├── gemini.py                Gemini JSON calls
│   ├── gmail.py                 Composio Gmail session, draft, send
│   ├── guard.py                 Send guard
│   ├── match.py                 Parsing, scoring, finance gate
│   ├── models.py                Pydantic models
│   ├── narrative.py             Note builder
│   ├── pipeline.py              find_roles, research, draft placement
│   ├── profile.py               Resume and LinkedIn understanding
│   ├── store.py                 SQLite store and lifecycle
│   ├── synthetic.py             Synthetic test cases (cannot send)
│   └── textutil.py              Text helpers
├── tests/
│   ├── test_fit.py              Binary evals from real traces
│   └── test_guard.py            Lifecycle, guard, scoring
├── InterviewOS_Cursor_Hackathon_Prompt.md   original spec
├── .env.example
└── pyproject.toml
```

## Approaches considered and what we learned

**Employer-side reference checks (Reference Desk).** Crustdata is strong at verifying people, so the first idea was an agent that runs reference checks for hiring teams. Dropped: the room was full of employer-side tools, and it did not match a problem the builder faces every week.

**Keyword job search plus auto-apply through connectors.** Paste a title, pull postings, push applications through Greenhouse, Lever, or LinkedIn via Composio. Dropped: Greenhouse and Lever write-tools need the *employer's* recruiter credentials, LinkedIn has no Easy Apply tool, and spraying applications is the exact behaviour that makes portals useless. What worked from this branch: Composio for Gmail, used only to place a reviewed draft.

**Profile-first search with a frontier model doing the matching.** Enrich the person, let the model write the search and the note. Partly kept: Gemini plans titles and keeps or rejects postings. Rejected for writing the note: the model's prose mixed evidence from two companies in one paragraph (CSB Bank and Canara Bank). The note is now a template over stored evidence, with ids.

**Paid enrichment stack (Crustdata + Crunchbase + OpenAI).** Dropped early. Crunchbase added a second vendor for timing data Crustdata already has, and the product needed to run free. One vendor also makes the Crustdata use case legible in a three-minute demo.

**WhatsApp as the candidate channel.** Attractive for adoption in India, but a multi-candidate WhatsApp product needs Meta's Business Platform and was not buildable before code freeze. Noted as the next step, not built.

**What we chose:** profile-first, Crustdata-only data, a binary finance gate tested from real traces, a hard cap of two roles, a current employee with a Crustdata email, and an unsent draft.

## Known limits

- The India job index is heavy on BFSI for product titles. The gate handles this; sharper titles do the rest.
- `/person/contact/enrich` is locked on hackathon keys; email coverage depends on `business_emails` being present on `/person/enrich`.
- Gemini responses can take up to 30 seconds. The pipeline tolerates a missing or empty answer.
- The Gmail step depends on a valid Composio key. Without it the case still saves and the note is on screen.
- One city and one country at a time. Remote-only filtering is not implemented.
