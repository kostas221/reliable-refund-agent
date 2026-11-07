# Portfolio finish checklist

Date: 2026-11-07

## Objective and boundary

Finish a locally runnable, clearly explained portfolio release for junior Applied AI / GenAI interviews.
This is an execution checklist for the existing release brief, not a new architecture plan or a production roadmap.
The owner explicitly wants bounded polishing instead of building a real-shop service.

Read `docs/plan.md` and its latest dated entries, `docs/release-brief-2026-10-31.md`, and
`docs/trial/rehearsal-2026-11-07.md` before implementing. Older phase/model labels must be checked against the
latest recorded decisions. Inspect the current implementation before assuming that work is missing.

Target: 12-18 focused hours, approximately 2-3 six-hour workdays, excluding participant scheduling.
This is an estimate, not a verified completion promise. Required release checks remain required. If a prerequisite
exceeds the budget, report the concrete blocker and remaining estimate; do not silently extend polishing or mark
an incomplete release complete.

## Ordered work

| Step | Work and evidence of completion | Time budget |
|---|---|---|
| 1. Establish the release baseline | Identify the current code revision, agent instructions, existing checks and remaining packaging work. Preserve other uncommitted work. List the exact missing release items; do not repeat completed model comparisons. | 1 hour |
| 2. Polish presentation | Render supported Markdown safely; present policy references with readable titles while preserving traceability; format UI timestamps with an explicit timezone. Keep raw audit data intact. Check customer and staff screens in mock mode. Do not strip identifiers from authoritative cards or alter financial values. | 2-3 hours |
| 3. Run the existing trial | Use the five-person protocol and task cards already written. Freeze the tested revision after presentation changes. Owner runs paid sessions with the existing budget cap and prerequisites; record assistance, confusion and handoff expectations. Report actual participant counts and limitations, never a general customer success rate. | 4-5 hours plus scheduling |
| 4. Repair material findings | Address reproducible safety/correctness defects and material usability blockers. Follow the trial's stop rules and existing decision thresholds; investigate ambiguous dispatch language and item-selection friction only when evidence warrants a repair. Prefer the existing explicit item choice over expanding fuzzy matching. Record the failure, minimal repair and relevant verification. Target at most two noncritical repairs. | 0-2 hours |
| 5. Finish release packaging | Update README status and evidence by version. Verify the documented clean mock startup and required Docker/CI checks; complete genuinely missing packaging. Resolve code licensing and retain separate data provenance/licensing. Link concise known limitations and evaluation reports. | 3-4 hours |
| 6. Record and explain | Prepare a 2-3 minute demo, three useful screenshots and a short interview explanation. Draft the portfolio/LinkedIn description from verified evidence. Owner controls recording participation and publication. | 2-3 hours |

Presentation-only changes may precede the trial as discussed in the latest plan entry. Do not silently change agent
instructions or behavior before its first participant. If a trial defect requires a change between sessions, record
the revision and separate observations before and after the repair, following the protocol.

## Demo storyboard

1. Briefly show the customer and staff roles and the simulated-payment label.
2. Customer requests a refund; the backend computes the proposal; customer explicitly confirms.
3. Staff approves the exact proposal; the test ledger records one refund and the UI shows its receipt.
4. Demonstrate restart/retry recovery using a reproducible existing path; the refund count remains one.
5. Show one refused unauthorized action through the existing test/demo path and explain the backend check.

Use mock mode for repeatable recording and label it accurately. If showing the live model, the owner starts the
paid session. Do not present scripted dialogue as live model behavior or a test-ledger entry as a real payment.

## README and interview evidence

- Lead with the problem, a screenshot/video, architecture, and a short tested quickstart.
- Explain that the model proposes and backend services enforce ownership, amount, confirmation and staff approval.
- Distinguish historical held-out results by evaluated version from current development results and human-trial
  observations. Check original reports before copying numbers. Preserve denominators, uncertainty, simulator faults,
  missed targets and omitted owner review where applicable.
- Keep known limits visible: fictional policy, simulated payments, English-only operation, and handoff continuing
  outside the chat. No production-readiness or zero-risk claim.
- Prepare answers to five questions: why an LLM; why backend authority; how exact approval works; what happens on
  retry/restart; what evaluation failed and what was learned.

## Stop rule

Finish when required checks pass, the documented mock quickstart works from a clean setup, the planned trial has
an honest report, material release blockers are resolved, and README/licence/demo accurately describe the release.
If participants are unavailable, packaging and recording preparation can continue, but the trial remains pending.
Do not substitute the owner's rehearsal for five independent participants.

Defer cosmetic suggestions after the bounded pass. A safety or correctness blocker is not waived by the time cap.
Do not add payment providers, Shopify, Chatwoot, a return-shipping lifecycle, automatic refund approval, languages,
MCP, more agents or new benchmark campaigns to this finish pass.

This checklist does not authorize paid API calls by the implementation agent, commits, pushes or publication.
No held-out reruns or tuning against spent held-out cases. Use targeted free checks during repairs and the required
full checks on the release candidate. Log substantive behavior changes with evidence in the existing plan history.
