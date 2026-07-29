# Problem Statement: Weekly Mobile-Store Review Pulse

## Goal

Turn raw App Store and Play Store feedback into a **weekly pulse** the team can scan in minutes: what users care about, what they actually said, and what to do next.

Reviews are already public. The system aggregates, themes, summarizes with **Groq LLM** (final report + email copy), and delivers insight through familiar surfaces:

- **Google Docs** — Groq-written weekly pulse (via MCP)
- **Gmail** — Groq-written draft email you can send yourself (via MCP)

Google credentials/REST wiring are handled via MCP—not custom OAuth/HTTP clients. **`GROQ_API_KEY`** is provided via environment only.

---

## End-to-End Flow (“Done”)

1. Pull recent App Store and Play Store reviews for the product (within constraints below).
2. Cluster reviews into a small set of themes and build a validated fact pack.
3. Use **Groq** to write the final one-page report and the final draft email (verbatim quotes; ≤250 words).
4. Publish that report where stakeholders can read it (**Google Docs** via MCP).
5. Create a **draft email** to yourself (or an alias) from the Groq email copy (**Gmail** via MCP).

---

## Deliverables

### Weekly one-page pulse must include

| Element | Requirement |
|--------|-------------|
| Top themes | What people are talking about most |
| Real user quotes | Verbatim snippets from reviews — no invented wording |
| Action ideas | Three concrete next steps grounded in the themes |
| Email draft | Draft to yourself containing the weekly note (or a clear pointer to it) |

### Pulse content checklist

- Top **3** themes (from at most **5** clustered themes)
- **3** user quotes
- **3** action ideas
- Draft email with the note to yourself or an alias

---

## Who This Helps

| Audience | Why |
|----------|-----|
| Product / Growth | Prioritize fixes and improvements from real signals |
| Support | Align messaging with what users are actually saying |
| Leadership | One-page health check without drowning in raw reviews |

---

## What You Must Build

1. **Import reviews** from roughly the last **8–12 weeks** (fields such as rating, title, text, date—whatever the export provides).
2. **Group reviews** into at most **5 themes** (examples: onboarding, KYC, payments, statements, withdrawals—pick what fits the product).
3. **Generate** a weekly one-page note with top 3 themes, 3 quotes, and 3 action ideas — **final wording via Groq LLM**.
4. **Draft** an email with the note to yourself or an alias — **final email copy via Groq LLM**, then Gmail draft via MCP.
5. Do **not** publish Docs or create the Gmail draft until Groq final copy succeeds.

---

## Integrations: Groq + Google Docs & Gmail via MCP

**Copy:** Use **Groq** to write the final report and final email from a validated fact pack (verbatim quotes; no PII; ≤250 words).

**Delivery:** Use **MCP** servers for Google Docs and Gmail—creating/updating the pulse document and creating the draft message—rather than integrating Google APIs directly.

- No bespoke Google OAuth client + REST client code as the primary integration path.
- MCP servers expose tools the agent or app can call.
- `GROQ_API_KEY` via environment only; Google auth stays in MCP host config.
- Requirement is **Groq-before-delivery** + **MCP-first** for Google surfaces.

---

## Key Constraints

| Area | Rule |
|------|------|
| Reviews | Public review exports only — no scraping behind store logins or ToS-violating automation |
| Themes | Maximum **5** themes for clustering; the written pulse highlights the top **3** |
| Length | Keep the note scannable and **≤250 words** where applicable |
| Privacy | No PII — no usernames, emails, device IDs, or other identifiable reviewer data; quotes must be anonymous / stripped as needed |
| LLM copy | Groq writes final report + email before Docs/Gmail; quotes must stay verbatim |

---

## Success Criteria Summary

- [ ] Reviews imported for last 8–12 weeks (App Store + Play Store, public exports)
- [ ] ≤5 themes clustered; pulse shows top 3
- [ ] 3 verbatim anonymous quotes
- [ ] 3 action ideas grounded in themes
- [ ] Groq wrote final report + final email before delivery
- [ ] Pulse published to Google Docs via MCP
- [ ] Gmail draft created via MCP
- [ ] Note ≤250 words and scannable
- [ ] No PII in any artifact