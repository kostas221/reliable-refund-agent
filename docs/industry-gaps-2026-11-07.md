# How the system compares with large companies' refund handling (2026-11-07)

For the owner, deciding what to change after the release, and for a reviewer asking how far this portfolio project
is from what companies run. Written after the owner's rehearsal ([trial/rehearsal-2026-11-07.md](trial/rehearsal-2026-11-07.md))
and a web search the same day. Most public material on these products is vendor marketing or competitors' guides;
the sources are listed at the end and should be checked before any claim is repeated.

## The short answer

The refund itself, meaning who may pay what and whether it is paid at most once, is already held to a stricter
standard than the public descriptions of commercial AI agents show. Those products describe guardrails as prompts,
second-model checks and approval thresholds; here the backend checks every rule in one transaction and an approval is
bound to the exact proposal. The distance to a company product is elsewhere:

1. **The human side.** A handed-off customer waits for an email; companies continue in the same conversation, with
   the staff member alerted and the context attached.
2. **The returns process.** Companies register a return inside the window and refund when it arrives or at the
   carrier's first scan; this shop counts only the receipt, and the request must come before the deadline.
3. **Staff effort.** Every refund here needs a staff approval; companies auto-approve low-risk refunds and send only
   large or risky ones to people.
4. **Production.** Real payments, the shop's own order and tracking data, a helpdesk, more than one language, live
   metrics, and a legal review of the policy.

No system in this market is perfect: a third-party guide cites one helpdesk vendor as automating up to 30% of
live-chat volume, and
Klarna, after moving most chats to an AI assistant, said quality had dropped and hired people again. "A score of 10"
is not a measurable target; the targets below are.

## Where the system already stands

| Practice described by companies | This system |
|---|---|
| Refund rules written as plain-language procedures that call the store's API (Intercom Fin), or skills and actions (Gorgias) | The policy is code in the backend; the model can only propose, and the backend refuses what the policy, the records or the approval do not allow |
| Guardrails: a second model's confidence check, approval for refunds above a threshold, a human for fraud signals | Customer confirmation and staff approval for every refund, bound to the exact proposal; the idempotency key and the refundable balance checked in the same transaction; at most one payment per approval |
| Simulations before going live: a simulated customer, the agent and an evaluator (Sierra, Intercom) | Simulated customers, rule-based evaluation, a human reading, development and unseen held-out sets, predictions written before each paid run |
| Reliability over repeated tries: pass^k, from τ-bench (Sierra's research team) | pass^3 on every set |
| Handoff with context: transcript, customer, issue and collected data (Zendesk practice) | A structured handoff: reason, origin, the customer's goal, facts, the request it closed, earlier actions, the customer's name and email |
| Telling the customer they talk to an AI (EU AI Act, Article 50, from 2 August 2026) | Live mode says on every screen that a language model answers |

Measured so far: on the 39 unseen scenarios of v1.3, Sol `low` succeeded in 109 of 117 conversations, and every
failure was a missing policy citation; instructions v12 repaired those on development copies (no missed citation in
117), which has not been measured on unseen scenarios. No unauthorized or duplicate refund in any run.

## What companies have that this system lacks

Ordered within each group by what it would change for customers and staff.

### Small, display only (no change to the agent)

| Gap | Seen in | What it would take |
|---|---|---|
| The chat shows Markdown marks and citation IDs such as `(refund-policy/v2/return)` | Rehearsal finding 2 | The screen renders bold text and shows each citation as the section's title ("Items must be returned first"); the stored text, and so the evaluation, is unchanged |
| Times in UTC | Rehearsal, D06 | The screen shows times on the customer's clock; the model's own words stay as written |

Internal IDs and "BRL 99.90" are in the model's own words and would need an instructions change and a new
measurement.

### After the release: the product

| Gap | How companies do it | What it would take here |
|---|---|---|
| No staff reply in the conversation, no alert for new messages, no list of taken cases | The handoff becomes a ticket; the person replies in the same messaging thread; the customer is told when to expect an answer (Zendesk) | A staff reply in the chat (the backend records it as the staff member's message), an unread marker, a "my cases" list, an expected reply time; or the helpdesk integration below |
| Returns count only when received | A return is registered inside the window; the refund follows at receipt or at the carrier's first scan (Loop). For the EU's 14-day withdrawal right, the law counts the sending (Directive 2011/83/EU, Article 14) | A return registration recorded by the backend with its time (never the customer's word), a policy v3 that counts it, and the refund at receipt; then a new measurement |
| Every refund needs a staff member | Auto-approve, review or block, by amount and risk signals (serial returners, mismatched addresses, high-risk orders) | Approval tiers in the policy, a risk score from the shop's records, and evidence that tiers keep unauthorized refunds at zero; it changes v1's rule that every refund is approved by a person, so it is a decision of the owner |
| A handoff can rest on the model's reading of an ambiguous answer | Low-confidence cases go to a person (Gorgias) | Rehearsal finding 5: require the customer's own words for `return_disputed`, as for a request for a person, if the trial shows the problem |
| Simulated money | Refunds through the payment provider's API with idempotency keys and asynchronous status | A payment provider in test mode; a refund that is pending, succeeded or failed, shown as such |
| English only | Many languages | Portuguese first: the shop's data and currency are Brazilian; a new evaluation set |
| Quality is measured offline | Resolution rate (not deflection), repeat contacts, escalations, satisfaction, cost per resolution, and a regular reading of sampled conversations | The same counts from the live database, and the reading habit kept from the evaluation |
| No external benchmark | τ-bench and τ²-bench retail tasks (returns and exchanges under a written policy) are the public reference | A τ²-bench retail run of this agent's design, for comparability |

### Only with a real shop

- The shop's helpdesk (Gorgias, Zendesk) through its API or MCP, with the backend still the authority (release
  brief, section 7).
- The shop's order, return and carrier-tracking data instead of fixtures; in the rehearsal's D22 the console showed
  no tracking for the staff member to check.
- A legal review of the policy. This shop's policy is fictional. A real shop selling to Brazilian consumers online
  must also honour the 7-day right of withdrawal (Código de Defesa do Consumidor, Article 49), with all amounts paid
  returned, which sources read as including shipping; this policy refunds shipping only through a staff member. In the EU the
  withdrawal period is 14 days and counts the sending.
- Data protection (LGPD, GDPR): what the model provider receives, how long request logs are kept, and redaction of
  personal data.
- Load, security and availability reviews, and a measured response time under real traffic.

## What "better" can be measured as

| Measure | Now | How it would be shown |
|---|---|---|
| Unauthorized or duplicate refunds | 0 in every run | Stays 0 in every new run and in the live database |
| Success on unseen scenarios | 109 of 117 (Sol `low`, v1.3, instructions v10) | A new unseen set, its author independent, with intervals |
| Consistency | pass^3 35 of 39 on that set | The same |
| Real people | The trial (in progress) | Counts out of five per question, problems fixed or recorded |
| Staff effort | Not measured | Time and steps per case in the staff session, against the participant's usual process |

## Recommended order

1. Run the five-person trial on the system as it is. My recommendation: make the display-only fixes before it. They
   appear in every conversation and would cost each participant attention, they leave the evaluated agent
   unchanged, and the stored text the evaluation reads stays the same.
2. Fix what the trial shows, by its evidence: rehearsal findings 1, 4, 5 and 7 are the candidates.
3. Release v1 with these limits stated in the README.
4. After the release, in this order: the staff reply channel, the return registration (policy v3), approval tiers,
   Portuguese, a payment provider in test mode, the τ²-bench run. Each is measured on new unseen scenarios before it
   is claimed.

## Sources

Vendor and third-party pages, read on 2026-11-07:

- Intercom Fin: [eesel.ai, refunds with Custom Actions](https://www.eesel.ai/blog/intercom-fin-ai-to-trigger-refunds-with-custom-actions); [releases.sh, human in the loop for Fin Procedures](https://releases.sh/release/rel_3pOFD1BdMBYQONowg_GXJ-human-in-the-loop-for-fin-procedures-fin-product-updates); [getmacha.com, refunds in Intercom](https://www.getmacha.com/blog/how-to-automate-refunds-in-intercom)
- Sierra: [simulations](https://sierra.ai/blog/simulations-the-secret-behind-every-great-agent); [confidence in every conversation](https://sierra.ai/blog/confidence-in-every-conversation)
- Gorgias: [eesel.ai, AI Agent actions](https://www.eesel.ai/blog/gorgias-ai-agent-actions-and-automated-tasks); [eesel.ai, Gorgias and Shopify](https://www.eesel.ai/blog/gorgias-ai-shopify-integration); [robylon.ai, refund guardrails](https://www.robylon.ai/blog/shopify-refund-automation-policy-guardrails)
- Zendesk handoff: [eesel.ai, handoff context](https://www.eesel.ai/blog/zendesk-handoff-context); [eesel.ai, bot-to-agent messaging](https://eesel.ai/blog/zendesk-bot-to-agent-handoff-messaging)
- Loop Returns: [MasonHub, Loop integration guide](https://support.masonhub.co/hc/en-us/articles/36481714664724-Loop-Returns-Integration-Guide); [AfterShip, Loop vs Returnly](https://www.aftership.com/blog/loop-vs-returnly-returns-credit); [refund on first scan](https://racklify.com/encyclopedia/query/refund-on-first-scan/)
- τ-bench: [arXiv 2406.12045](https://arxiv.org/abs/2406.12045)
- Klarna: [Entrepreneur](https://www.entrepreneur.com/business-news/klarna-ceo-reverses-course-by-hiring-more-humans-not-ai/491396); [Customer Experience Dive](https://www.customerexperiencedive.com/news/klarna-says-ai-agent-work-853-employees/)
- Metrics: [Zendesk, deflection vs resolution](https://www.zendesk.com/au/blog/ai/workflow-automation/ticket-deflection-vs-resolution/); [twig.so, deflection as a vanity metric](https://twig.so/blog/deflection-rate-vanity-metric-cx-numbers-that-matter)
- Law: [Directive 2011/83/EU, Article 14](https://www.legislation.gov.uk/eudr/2011/83/article/14); [Art. 49 CDC](https://www.peticoesonline.com.br/art-49-cdc); [EU AI Act Article 50 (secondary)](https://jorijn.com/en/blog/eu-ai-act-website-chatbot-disclosure-august-2026/)
