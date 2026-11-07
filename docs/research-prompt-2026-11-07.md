# Research prompt: making the refund agent as strong as one person can

For the owner, to give to a research model with web search (a "deep research" mode) in a fresh conversation. Copy
everything below the line. The answer comes back to this repository and Claude checks it point by point against the
code and the sources before anything is adopted (the same rule as for every outside review).

---

You are a senior research analyst helping a solo developer turn a working portfolio project into a system that
could run for a real small online shop. Research how large companies and mature open-source projects handle
customer refunds and returns with AI assistants, and find what a single developer can adopt. I need concrete,
sourced, practical findings, not a general overview.

## The system today

- **What it does:** a customer-support assistant for refunds. A customer writes in a chat; the assistant looks up
  the customer's orders, explains the shop's refund policy with citations, and proposes a refund. The customer
  confirms with a button (typing "yes" does not count), a staff member approves in a console, and the backend pays
  at most once per approval. Staff can take over a conversation; a case the policy gives to a person is handed off.
- **Principle that must not change:** the backend is the authority. The language model only proposes; the backend
  checks the customer's identity and ownership, the policy, the amount, the state, and an approval bound to the exact
  proposal, and executes in one database transaction with an idempotency key and the remaining refundable balance
  checked together. A retry returns the same receipt.
- **Stack:** Python, FastAPI, LangGraph (conversation state and routing only), PostgreSQL (orders, proposals,
  approvals, a simulated payment ledger, an audit log), React and TypeScript screens for the customer and staff. Model
  providers behind one adapter: OpenAI Responses API (GPT-6.1 Sol, reasoning low) and Anthropic (Claude Sonnet 5.5).
  Runs locally with Docker; money is simulated; one fictional shop in BRL built on a public Brazilian e-commerce
  dataset (Olist); English only.
- **Evaluation so far:** simulated customers on scripted scenarios, a rule-based evaluator plus human reading,
  development and held-out (unseen) scenario sets, pass^3 (success in all three tries), paired bootstrap intervals,
  predictions written before each paid run. On 39 unseen scenarios the main model succeeded in 109 of 117
  conversations; every failure was a missing policy citation. No unauthorized or duplicate refund in any run.
- **Constraints:** one developer, part time; a small budget for model calls (dollars, not hundreds); open-source or
  free tiers preferred; must stay runnable locally; no public deployment until it is safe.

## Known gaps (what to research)

1. **Human handoff:** after a handoff the staff member continues by email outside the app; no reply in the same
   conversation, no alert for the customer's new messages, no list of taken cases, no expected reply time.
2. **Returns process:** the shop counts only the receipt of a returned item, and the refund request must come before
   the deadline; there is no return registration inside the window, no return label, no refund at the carrier's first
   scan, no exchanges or store credit.
3. **Staff effort:** every refund needs a staff approval; there are no approval tiers by amount and risk, and no
   fraud or abuse signals (serial returners, mismatched addresses, high-risk orders).
4. **Language understanding at the edges:** the backend checks some decisions against the customer's own words (which
   item among look-alikes, a request for a person). A typo ("oliv" for "olive") made it refuse a correct proposal, and
   an ambiguous "i send them back" led to a handoff for a return the customer had not yet sent.
5. **Presentation:** the chat shows Markdown marks, internal IDs and policy citation codes; times in UTC.
6. **Production:** simulated payments; fixtures instead of the shop's own order, return and tracking data; no
   helpdesk integration; one language; no live quality metrics; no legal review of the policy (Brazilian consumer law
   gives 7 days to withdraw from an online purchase; the EU gives 14 days and counts the sending of the goods); data
   protection (LGPD, GDPR) and what the model provider receives; the EU AI Act's disclosure duty for chatbots.
7. **Evaluation against the outside world:** no run on a public benchmark such as τ-bench or τ²-bench retail; no
   production monitoring of resolution, repeat contacts, escalations and satisfaction.

## What to find, for each gap

1. **How large companies do it**, from primary sources where possible: official documentation, engineering blogs,
   conference talks, papers, API references. Candidates to examine include Intercom Fin, Sierra, Decagon, Gorgias,
   Zendesk AI agents, Salesforce Agentforce, Ada, Amazon and Shopify returns, Loop Returns, Happy Returns, Narvar and
   AfterShip Returns. Describe the mechanism (what is checked, by what, when a person is involved), not the marketing.
2. **What a solo developer can adopt:** open-source projects, libraries, free tiers, test modes and public standards,
   with licence, cost, maturity and the effort in days. Examples worth checking, without assuming any claim about
   them: an open-source helpdesk for staff replies in the same conversation (such as Chatwoot, Zammad or FreeScout);
   the refunds APIs of Stripe and of Brazilian payment providers (such as Mercado Pago or Pagar.me) in test mode, with
   idempotency and asynchronous refund status; return data models in Shopify's Admin API or open-source commerce
   platforms (such as Medusa or Saleor); LangGraph's human-in-the-loop features; LLM observability and tracing (such
   as Langfuse, Arize Phoenix, the OpenTelemetry generative-AI conventions); evaluation tools (such as τ²-bench,
   Inspect, promptfoo); fuzzy matching for product names; MCP security guidance.
3. **How it fits the principle above:** where the check lives, what the model may and may not do, what is recorded,
   and how a retry or an uncertain outcome is handled without a duplicate effect.
4. **How to show it worked:** the measurement or test that would fail without it.

## Rules for the answer

- Cite every factual claim with a link and the date of the source. Mark each source as primary (official docs, law,
  paper, code), secondary (independent analysis) or vendor marketing.
- Say "not documented" when a company's mechanism is not public; do not infer features from marketing.
- Prefer mechanisms that are simple and verifiable over impressive ones. Say plainly what is overkill for one person.
- Do not recommend anything that lets the model grant refunds, change amounts or bypass the approval and execution
  checks.
- If a source contradicts another, show both.

## Output format

1. A one-page summary: the ten changes with the most value for the effort, ranked, each with effort (days), cost,
   risk and the gap it closes.
2. One section per gap above: how companies do it; what to adopt (with links, licence, cost); how it fits the
   backend-authority design; how to measure it; what not to do.
3. A table of every tool or project named: what it is, licence, cost, maturity (release history, maintainers),
   and the link.
4. A list of open questions you could not answer from public sources.
5. The sources, grouped by type.
