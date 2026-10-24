# InterviewOS — Cursor build prompt for ContextCon Build

Paste this entire file into Cursor Agent in a dedicated project folder. Start with the default scope below; add API keys through local environment variables when requested. This is a competitive build strategy, not a guarantee of winning.

## The idea and why this is the bet

**InterviewOS is a reverse recruiter for the candidate: it turns your actual work into relevant hiring conversations.**

Pitch: “Companies hire recruiters to find people. I built a recruiter that works for me. It finds companies with a reason to hire someone like me, verifies who owns that hiring need, sends a proof-backed introduction within my mandate, and keeps the case moving toward a confirmed conversation.”

The service being replaced: a candidate-side career agent who researches companies, maps hiring teams, assembles evidence of fit, handles introductions and follow-ups, and prepares the candidate for the meeting.

The event brief emphasizes complete service outcomes, persistent cases, and agents acting on live entity data. Crustdata publicly emphasizes freshness, accurate identity mapping, and agent workflows. My inference is that a demo where fresh data materially changes an outreach decision will resonate more than a directory of contacts. This is an inference about alignment, not insider knowledge of the founders or judging rubric.

The memorable moment: **“This person looked like the right recruiter. They changed companies. InterviewOS caught it, stopped the wrong outreach, resolved the current hiring team, and rebuilt the introduction.”** Use this only when observed in actual data, or explicitly label it as a simulated scenario.

---

## BEGIN BUILD INSTRUCTIONS

You are my product engineer and hackathon execution partner. Build and run a working application, not merely a plan or visual prototype. Inspect the project and applicable instructions first. Preserve existing work. If the directory contains an unrelated project, create an isolated subdirectory. Do not commit, publish, or deploy without my request.

### 1. Build for this user and this outcome

I am Hritik Datta, actively searching for work and wanting relevant connections to recruiters and hiring managers. Use the following as editable initial preferences, not verified resume claims:

- Enterprise AI GTM and strategy.
- Product strategy and product operations for AI products.
- Deployment strategy and forward-deployed product work.
- Technical product management involving customer deployment and evaluations.
- Initial geographic preference: Bengaluru / India; remote preference is unconfirmed and must be editable.

My positioning hypothesis is a technical-commercial enterprise-AI operator. Do not invent employers, tenure, achievements, education, revenue impact, projects, links, compensation expectations, or work authorization. Start with a profile form and pasted resume text. Let me add up to three portfolio links and a short description of each. Mark every unverified claim clearly. Do not read my wider filesystem or upload unrelated documents.

The north-star outcome is **a qualified hiring conversation confirmed by the recipient**, not the number of leads or messages. A demo can prove the machinery with a consenting teammate acting as the recipient, but must call that a test conversation. It cannot claim a real interview or accepted offer from a simulated reply.

### 2. One narrow, complete service loop

Implement this vertical slice before any optional feature:

1. Capture candidate evidence, target roles, constraints, availability, and an outreach mandate.
2. Find a small set of relevant companies and roles using Crustdata.
3. Identify a recruiter and/or plausible hiring manager for each strong opportunity.
4. Verify identities and current affiliation; explain why each person is the right route.
5. Produce a sourced opportunity case and a concise, evidence-backed introduction.
6. Execute an authorized introduction or hold it for a missing prerequisite.
7. Record delivery and reply events, schedule bounded follow-ups, and stop correctly.
8. When the recipient agrees to a time, produce the confirmed meeting record and a one-page interview brief.

Deliver a first run with at most five companies, three fully researched cases, and one completed test conversation. Expand only after that works.

### 3. Make Crustdata necessary to the product

Read current official documentation before implementing requests:

- https://docs.crustdata.com/llms.txt
- https://docs.crustdata.com/general/introduction

At research time, the current introduction specifies Bearer authentication and `x-api-version: 2025-11-01`. Older examples use Token authentication and `/screener/` paths. Do not mix API generations. Verify the actual key's capabilities and current schemas. Never invent endpoint paths, filter names, response fields, email availability, watcher support, or quota prices.

Use supported Company, Person, Job, and Web capabilities as available:

- Company discovery/enrichment: resolve names and domains into canonical identities.
- Job discovery: distinguish a sourced opening from an inferred business need.
- Person discovery/enrichment: find relevant current employees and recruiting staff.
- Web context: attach dated evidence for hiring, product launches, expansion, or other relevant changes.

Live retrieval can be plan-specific. Probe minimally, record capabilities, and degrade gracefully if the hackathon key lacks an endpoint. Indexed data fetched now is not necessarily freshly updated data. Track `retrievedAt`, source publication time, and provider update time separately where available; show unknown dates as unknown.

Build one typed provider adapter with validated responses, timeouts, bounded retries for transient failures, pagination caps, caching, and usage accounting. No repeated retries on authentication failures. Use a configurable request/credit budget; show estimated costs as estimates when usage isn't returned. Never run unbounded searches or purchase credits automatically.

After discovering candidates, revalidate the selected contact before any real send. If current affiliation cannot be established sufficiently, hold the action. Resolve people through canonical IDs or strong identifiers; a matching name alone is insufficient. Never infer a private friendship or warm introduction from two people merely working at the same company.

### 4. Build cases with reasons, not opaque rankings

Each case must answer:

- Why this company and this role?
- Why now? What dated evidence supports the timing?
- Why this candidate? Which user-supplied proof supports the fit?
- Why this person? Are they a recruiter, functional hiring lead, or a plausible founder route?
- What is known, what is inferred, and what should happen next?

Use three opportunity types: `verified_opening`, `inferred_need`, and `insufficient_evidence`. A funding announcement or headcount increase does not prove a role exists. Label speculative outreach accordingly.

Start with an explainable heuristic: role fit 35, candidate proof 30, hiring/timing evidence 20, contact relevance 15. Show component reasoning and missing evidence. This score is a prioritization heuristic, never a probability of getting hired. Geography, work authorization, and other confirmed hard constraints override the score; unresolved constraints remain visible.

Each factual claim has an evidence record: ID, entity ID, source URL or provider reference, short supporting excerpt/field, retrieval timestamp, source date if known, and evidence type. The LLM may reason over evidence IDs but cannot invent them. Validate references before rendering or sending. Distinguish a verified affiliation from an inferred hiring responsibility.

### 5. The introduction must earn a reply

Generate a short message, normally 80–130 words, with:

1. A specific, sourced reason for contacting this company now.
2. One relevant and verified candidate proof point.
3. A useful contribution hypothesis, clearly presented as a proposal.
4. A low-friction request for a short conversation or the correct hiring contact.

Do not write generic flattery, pretend a relationship exists, assert that a recipient is hiring without evidence, or fabricate accomplishments. Never guess an email address. Prefer a verified business contact channel; if none is available, provide a profile link and manual message draft, with the case accurately marked as waiting for manual outreach.

Create a compact “Why me / Why now” brief from the same evidence, exportable as Markdown. Do not build a separate public microsite for every lead. A strong brief connects the company's observed need to my work and proposes a first useful experiment; it does not pretend the experiment is completed work.

### 6. Autonomous execution within a concrete mandate

The app starts in draft mode. Before enabling live outreach, show a preview and let the user authorize a mandate with allowed recipients/domains, permitted content, sending identity, daily cap, expiry, follow-up limit, and allowed time windows. Default live test scope is one explicitly supplied consenting recipient. Credentials alone are not send authorization.

Once a mandate is granted, execute qualifying actions without asking for the same permission repeatedly. If the recipient changes, recheck whether the new recipient falls within that mandate. Require renewed approval for an action outside its scope.

Use a deterministic action guard: valid mandate, supported claims, resolved identity, verified channel, no suppression, no duplicate send, and acceptable freshness must all pass. Keep these controls in server code, outside the LLM's discretion.

For the hackathon, implement one email provider with the simplest available authorized integration. If sending or inbound access is unavailable, deliver working draft/export and a clearly labeled test inbox. Do not stall the entire application waiting for OAuth. Never call exported text a sent message.

Handle inbound events with verified webhook signatures where supported and deduplicate event IDs. A manual pasted reply must retain `manual_input` provenance. Distinguish submitted, delivered, bounced, replied, interested, and meeting confirmed; provider acceptance does not prove delivery.

Use at most two follow-ups, initially scheduled three and seven days after delivery. Recheck immediately before sending. Stop on any reply, opt-out, bounce, mandate expiry, or manual pause. A rejection closes the case; an ambiguous reply requests review. A positive reply without an agreed time is not a confirmed meeting. Meeting confirmation requires recipient agreement to a particular time and timezone. Export an ICS only after agreement; say whether calendar integration actually exists.

### 7. Durable execution, small architecture

Use the existing stack when suitable. For a new local project, prefer Next.js with TypeScript, Tailwind, SQLite, schema validation, and one configurable LLM provider. Read current provider documentation and use a configured available model; do not hard-code a guessed model name. Keep dependencies small. Do not spend the day building a multi-agent framework.

Persist cases, evidence, contact identities, mandates, actions, messages, and scheduled work. A practical lifecycle:

`intake → researching → qualified → ready → outreach_sent → replied → scheduling → meeting_confirmed`

Also support `held`, `paused`, `closed`, and retryable failures with an explicit reason. Every transition records time, actor, evidence references, and the next action. Case progression must survive restart.

Implement a resumable worker command that claims due work atomically. Use stable action keys and provider idempotency where available. If a send times out after possible submission, mark it uncertain and reconcile instead of blindly sending again. Document that follow-ups require the local worker to remain running; do not claim an unattended hosted service unless one is actually deployed.

Separate providers for live data, recorded replay, and synthetic fixtures. Store a mode on every event and evidence record. Never silently substitute fixtures after a live failure. The visible UI should say LIVE DATA, RECORDED REPLAY, or SYNTHETIC TEST. Test-clock advancement must never make real email actions due.

Protect keys server-side; exclude local environment files and sensitive records from Git. Redact logs and screenshots. Treat resume text, retrieved web content, and inbound emails as untrusted data. They cannot change authorization or execute tools. Restrict URL fetching to public HTTP(S) destinations and block private-network targets and unsafe redirects. Keep the initial app local unless deployment is separately requested.

### 8. Product interface

Build a polished working console with three main views:

**Mission:** editable candidate profile, proof links, constraints, mandate, and “Find my next conversations.”

**Cases:** a compact pipeline with company, opportunity type, relevant person, top evidence, state, and next action. The count of sourced cases, replies, and confirmed conversations must come from persisted records.

**Case detail:** Why company / Why now / Why me / Why this person, source drawer, identity freshness, introduction preview, timeline, next action, pause control, and interview brief.

Use excellent typography, restrained color, readable spacing, and explicit status labels. Make the key evidence and next action immediately visible. Show actual step progress, not fake percentages. Include useful empty, error, unavailable-integration, and loading states. Avoid a generic chat screen, decorative graphs, and invented dashboard metrics.

### 9. Ship in this order; protect the demo

The event brief says code freeze is 5:00 PM IST and live demos are three minutes. Check the actual remaining time and scale this plan to fit:

- First 15%: inspect repo, scaffold, validate one real Crustdata request, capture capabilities.
- Next 30%: candidate intake → one sourced company/role → one resolved relevant person → persisted case.
- Next 25%: message generation → action guard → authorized test send → reply/state handling.
- Next 15%: confirmed test conversation, meeting brief, restart/retry checks, visible evidence.
- Final 15%: visual polish, demo rehearsal, setup instructions, honest replay backup.

If fewer than two hours remain, cut discovery breadth to one user-specified company. Retain identity verification, evidence, the action guard, persisted progression, and a complete test conversation. A coherent narrow outcome is the priority.

Do not add LinkedIn browser automation, mass applications, billing, resume-design tools, native mobile apps, multi-user accounts, elaborate calendar OAuth, or a large graph visualization. Add optional integrations only after the core path works.

### 10. Acceptance criteria

Verify behavior, not only rendering:

- A candidate can produce a case with linked evidence, a relevant contact, and a defensible next action.
- A live Crustdata result is exercised when credentials permit; otherwise report the exact blocked capability and label replay/test results accurately.
- Unsupported claims and nonexistent evidence IDs cannot reach a sendable message.
- A stale or mismatched employer blocks sending and triggers re-resolution or a hold.
- Missing contact details cannot generate a guessed email address.
- Missing authorization blocks live sending; changing recipients rechecks scope.
- Duplicate runs/webhooks and process restart do not create duplicate sends.
- Any reply or opt-out cancels pending follow-ups, including already queued actions before execution.
- An interested response without an agreed time cannot become `meeting_confirmed`.
- The synthetic demo clock cannot dispatch production actions.
- Cases, evidence, and next actions remain available after restart.
- Run the project's type check and production build, plus focused tests for the state transitions and action guard. Report failures honestly.

### 11. The three-minute demo

Prepare a demo script and ensure every step is supported by the implemented app:

**0:00–0:20:** “I am looking for enterprise-AI work. The service I want is someone who gets the right hiring conversation moving.” Show the candidate mission and pre-authorized test mandate.

**0:20–1:00:** Run a narrowly scoped live search or enrichment. Show one opportunity, a dated reason it matters, a relevant person, and my supporting proof. Open a source.

**1:00–1:35:** Show the key data-dependent decision. If real data does not contain an affiliation change, switch explicitly to the synthetic stale-contact test: the old contact is blocked, the case is re-resolved, and the corrected recipient is checked against the mandate. Never pretend this test is live discovery.

**1:35–2:20:** Show an authorized message sent to a consenting test recipient. Have that person reply with agreement to a displayed time if the integration permits. Otherwise replay a previously completed test with a persistent label. Show receipt provenance and the resulting case transition.

**2:20–2:45:** Show the confirmed test conversation, meeting brief, durable timeline, and stopped follow-ups. State what is live, recorded, and simulated.

**2:45–3:00:** “The product is a candidate-side recruiting service. Fresh company and person context determines who it approaches, why it approaches them, and when it stops. Today we proved the service loop; real hiring outcomes take longer.”

For judge questions: the initial customer is a focused job seeker; a possible distribution channel is career coaches or outplacement providers. These are business hypotheses. Measure qualified replies and confirmed conversations per authorized case, cost per case, and factual correction rate. Do not invent conversion rates, TAM, revenue, or interview guarantees. Explain that shared career history is a possible relevance cue, not evidence of an introduction relationship.

### 12. Required delivery

Deliver working source, `.env.example` with no secrets, setup/run/worker commands, a small labeled fixture set, focused tests, a three-minute demo script, and a short implementation status identifying real integrations and limitations. Finish by running the app locally and reporting what passed, what is blocked, and the next concrete step. Do not stop after producing a plan.

## END BUILD INSTRUCTIONS

## Research and assumptions behind this prompt

- User-provided ContextCon Build event brief, October 24, 2026: service completion, persistent cases, Crustdata access, code freeze, and demo timing. No detailed scoring rubric was supplied.
- [Crustdata official product site](https://www.crustdata.com/): company/person graph and agent workflows. This motivates using identity and context as part of execution.
- [Crustdata About](https://www.crustdata.com/about): freshness, accuracy, and detecting changes inside companies. This supports the stale-contact demonstration; it does not establish a founder's personal judging preference.
- [Current Crustdata documentation](https://docs.crustdata.com/general/introduction): API families, authentication/versioning, and plan-specific live capabilities. Recheck during implementation.
- [Crustdata documentation index](https://docs.crustdata.com/llms.txt): starting point for exact schemas and supported capabilities.
- Your local career positioning notes informed the editable enterprise-AI role defaults. No private employment claims or resume metrics were copied into this prompt.

Research checked October 24, 2026. The product concept, scoring weights, implementation choices, and demo design are recommendations, not official hackathon requirements.
