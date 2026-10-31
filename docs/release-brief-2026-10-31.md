# Release completion brief (2026-10-31)

For the project owner and anyone checking how the release was closed. The brief below was given by the owner on
2026-10-31, written with another AI model, and adopted the same day as the plan for closing the release, in this
order (plan change log, 2026-10-31):

1. The full test suite, a commit, and the registered confirmation run of v1.3's two repairs.
2. Closing v1.2: the owner's reading of the 73 selected conversations and the results narrative.
3. A local live-model mode in the application (section 3 below), alongside step 2.
4. The qualitative trial with five people (section 5), after the handoff checks of section 4.
5. The release presentation (section 6). No MCP in this release (section 7).

Claude checked the brief against the repository before adoption, with free probes:

- The v1.2 numbers in section 1 match the reports of `runs/final-v1.2-20261030T170445Z` and
  `runs/stress-v1.2-20261030T174734Z`.
- Section 2's checks of the selection repair found two defects: "the wrist strap, not the pouch" let a proposal for
  the pouch through, and "the pouch instead of the strap" one for the strap. Both were fixed with failing-first
  tests before the confirmation run (plan change log, 2026-10-31).
- Section 3's premise holds: `refund_agent/api/__main__.py` serves the chat with `ScriptedModel` only, so the
  application never reaches the evaluated agent, and a trial with people would test a script.
- Section 4 is largely covered by existing tests (a restart with a pending approval, a notice delivered twice applied
  once, a delivery that keeps failing stops after three attempts, no change by the agent after a handoff); what the
  customer understands while waiting, and how staff continue outside the application, are left to the trial.

The brief follows as given.

---

Reliable Refund Agent — Release Completion Brief
Objective
Complete the current release, validate its usefulness with real people, and publish an honest portfolio presentation.
Follow the frozen plan and the existing v1.3 implementation sequence. This brief consolidates the remaining work; it does not reopen architecture planning or authorize paid runs, commits, pushes, or production deployment.
Preserve customer ownership checks, explicit confirmation, staff approval bound to the exact proposal, transactional balance checks, and protection against duplicate execution.
1. Close the v1.2 evaluation
The saved v1.2 results are:

* Configuration A: 50/57 successful conversations, or 87.7%.
* A passed all three attempts on 16/19 scenarios, or 84.2%.
* Configuration B: 54/57 successful conversations.
* Separate stress evaluation: 23/24 successful conversations per configuration.
* No unauthorized or duplicate committed refund observed in the 162 conversations of A and B across both sets.

Both predefined quality targets were met. A’s reported 95% success interval is 71.9%–100.0%.
Complete the owner’s prescribed review of 73 selected conversations and write the final v1.2 results narrative. Preserve disagreements, failures, invalid simulations, and limitations.
Explicitly disclose:

* The held-out set contains 19 scenarios with three attempts each.
* Neither the held-out nor stress set requires a successful handoff.
* Zero observed violations do not establish zero risk.
* Current v1.3 changes are not covered by the v1.2 result.
* Runs on development copies of those scenarios are development evidence.

Keep the original scenarios, frozen files, and run artifacts unchanged.
2. Finish and validate the two existing v1.3 repairs
Review the current implementations before making further changes. Do not rebuild repairs already present.
Repair A: trustworthy deadline information
Ensure the order data the agent reads exposes the deadline calculated by the backend and whether it has passed.
Verify that:

* An expired window plus a missing return never produces a promise that arrival alone will permit a refund.
* An earlier on-time proposal still receives its policy-defined treatment.
* Missing or implausible delivery dates are not presented as reliable deadlines.
* Order reads and eligibility decisions use the same policy calculation.

Repair B: ambiguous item selection
Verify the extended selection check against both ambiguous and explicit requests.
It must distinguish a request for one item, both items, an exclusion, and a changed selection. Check for unnecessary refusals of previously valid requests.
Treat the language check as a bounded safeguard with known limitations. If it requires an expanding collection of phrase exceptions, record that limitation and consider an explicit item picker only when measured user difficulty justifies it.
Confirmation measurement
Follow the existing registered development measurement and predictions, using the selected Luna `low` configuration.
Before the owner runs it:

1. Complete the required free checks.
2. Run mock end to end.
3. Inspect one complete logged model request.
4. Verify the question, predictions, acceptance criteria, and enforced budget cap.

Report overall success, targeted repair outcomes, new false refusals, simulator faults, interaction problems, latency, and cost.
Do not describe this as a new held-out evaluation. Do not continue tuning until every known example passes.
3. Enable a controlled live-model UI trial
The documented application entry point currently uses `ScriptedModel`. Add an explicit local live-model mode using the existing adapter and the same backend, tools, approvals, and database.
Requirements:

* Mock remains the default and requires no API key.
* The interface clearly identifies the active mode and simulated payments.
* Live mode has bounded usage and an enforced budget, including calls triggered by staff decisions.
* The owner starts every paid session.
* Provider failure leaves the request in a recoverable, truthful state.
* No real payment provider or public deployment is introduced.

This completes the connection between the evaluated agent and the user-facing application.
4. Validate human handoff and recovery
Exercise the complete handoff path, including:

* A customer explicitly requesting a person.
* A policy case requiring staff intervention.
* A staff decision whose delivery to the agent repeatedly fails.
* Restart while a decision or handoff remains pending.

Verify that the customer understands what is waiting, staff can identify and take the case, and the agent cannot continue making changes after takeover.
For the local trial, document how staff continue communication outside the application. Do not present takeover as completed resolution.
5. Run the planned qualitative user trial
Recruit five people using their own English, and, if available, one person with customer-support experience.
Observe:

* Where users need help or repeat information.
* Whether they understand proposal confirmation and approval.
* Whether refusals and next steps are clear.
* Whether ambiguous selections are resolved naturally.
* Whether staff receive enough information to act.
* Whether the workflow reduces staff effort compared with their usual process.

Report concrete observations and participant counts. Do not turn this small convenience sample into a general success-rate claim.
Fix reproducible safety or correctness defects and material usability blockers. Record other suggestions for later.
6. Complete the release presentation

* Update the README to distinguish v1, v1.2, and v1.3 evidence.
* Publish the final v1.2 narrative after the owner’s review.
* Complete and verify Docker startup for backend, frontend, and database.
* Verify the documented quickstart from a clean setup.
* Confirm required CI checks pass on the release candidate.
* Choose and add the code licence; retain separate dataset provenance and licensing information.
* Record the planned short demonstration: proposal, confirmation, staff approval, restart, receipt, safe retry, and one refused unauthorized action.
* Explain what is synthetic, scripted, model-driven, and simulated.

The LinkedIn presentation should describe a locally runnable refund workflow with human approval and measured reliability. Avoid claims of production readiness, universal accuracy, or zero risk.
7. MCP decision
Do not add MCP to the current release.
MCP is a useful integration mechanism when an actual external system or another client needs access. It does not itself improve reasoning, policy enforcement, or transaction correctness.
After identifying a participating shop, evaluate one connection to the helpdesk it already uses. Gorgias MCP is a relevant candidate for transferring case context, adding internal notes, and tracking staff handling.
Choose MCP only if its supported capabilities, access model, and maintenance benefits justify it compared with a direct API integration.
Any future integration must:

* Preserve the backend as the authority.
* Expose only the capabilities needed by the workflow.
* Enforce customer and shop boundaries.
* Handle retries and uncertain outcomes without duplicate effects.
* Keep staff approval separate from permission to access the external service.

Do not expose an independent refund tool that bypasses the existing approval and execution services.
References:

* [Fin MCP connectors](https://fin.ai/help/en/articles/13976067-add-mcp-connectors-for-popular-apps-or-custom-mcps)
* [Zendesk MCP client](https://support.zendesk.com/hc/en-us/articles/11105393853210-Announcing-the-general-availability-of-the-MCP-client)
* [Gorgias MCP tools](https://helpcenter.gorgias.com/en-US/explore-gorgias-mcp-tools-9131180)
* [OWASP MCP security guidance](https://cheatsheetseries.owasp.org/cheatsheets/MCP_Security_Cheat_Sheet.html)

Completion rule
Finish the bounded repair and confirmation cycle, close the evaluation record, complete the user trial and packaging, and publish.
A critical safety defect or a correctness regression reopens the necessary repair. Other weaknesses are documented for a later version.
Do not delay the release solely to add MCP, more models, more agents, or a perfect score on familiar scenarios.
