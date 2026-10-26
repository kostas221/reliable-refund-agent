# Held-out evaluation of v1.1: protocol

For the project owner and anyone who checks the final results of v1.1: how the 20 new held-out scenarios are written,
checked and frozen, and what may change once they exist. Written on 2026-10-25, before any of them exists.

The point: v1.1 was built and repaired on 42 development scenarios, so its results there (124 of 126 on 2026-10-24)
show only that the cases its rules were built on are solved. The question this evaluation answers is whether the
improvement holds on cases written by someone who has not seen the system's history, and which of the two models,
Luna none (A) or Sol low (B), resolves more of them, at what cost.

## 1. The system is frozen first

| What | Frozen as |
|---|---|
| Code, policy, agent instructions, tools, backend, migrations, evaluator and runner | commit `1a46a3c`, file fingerprint `c3416bd96a6e9996ab6832cadd6e10b0dfbcef0ba44b299978565e3f5ea3691c` (the manifest of `runs/pilot-20261024T164827Z-gpt-6-luna-none`) |
| Policy | `refund-policy/v2` (`policies/refund-policy-v2.toml`) |
| Agent instructions | `prompts/agent-v8.md` |
| Configuration A | gpt-6-luna, reasoning none, all backend checks |
| Configuration B | gpt-6.1-sol, reasoning low, all backend checks |
| Configuration C | gpt-6-luna, reasoning none, the lab configuration of plan section 10.5 |
| Simulated customer | gpt-6-luna, reasoning low, `prompts/customer-simulator-v1.md` |

After the scenarios exist, nothing in the first two rows of configurations or in the agent's code, instructions,
tools or policy changes. Two kinds of change are allowed, each recorded in the plan's change log with its reason:

- **The harness that selects and proves the scenario set** (section 5): a new, versioned set and its freeze check.
  It changes what is run, not how the agent behaves.
- **A real defect of the product**, found by the technical checks of section 4, may be fixed. The scenario that
  revealed it then becomes a development scenario and is replaced by a spare (section 3), since the system was
  changed for it.

## 2. What the author sees

The author is a language model in a new conversation, with no access to this repository: not the Claude Code
session of this project, whose instructions carry the whole history. It receives one file,
[author-package.md](author-package.md), and nothing else.

| The author gets | The author does not get |
|---|---|
| What the product must do; the whole policy v2; what each agent tool can do; what the test harness does (simulated customer, scripted buttons, scripted staff member); the scenario format; the success criteria and the forbidden events; the composition | Any conversation, run, result or failure; the development or old held-out scenarios, or a list of their situations; the agent's instructions; the backend's internal checks and the word rules some of them use; the plan's change log; which model is which |

The project owner opens the conversation, pastes the package, and saves the author's answer unchanged as
`docs/held-out-v1.1/author-output.md`, with the model's name and the date. If the answer is cut short, the owner asks
the same conversation to continue; nothing else is said to the author.

## 3. Composition and spares

The plan's composition (section 10.2): 8 eligible requests, 4 ineligible, 4 attacks and foreign data, 4
clarification and handoff. The author writes **28 candidates**, two spares per group (10, 6, 6, 6), in an order it
fixes itself, with IDs H21 to H48.

A candidate is **set aside** when, read next to the closest development scenario, it is the same situation: the same
deciding policy rule and the same shape of conversation (what the customer asks, in what order, with what the
records show), so that only names, products, amounts, dates or wording differ. The project owner and Claude read each
candidate against the development set and write the verdict and the closest scenario in a table before anything else
happens; disagreements are settled by the owner. A candidate is also set aside if its expectations do not follow from
the policy (section 4). The author is told neither.

The **20 kept** are, in each group, the first candidates in the author's order that are not set aside, up to the
group's count. If a group has too few, the owner asks the same conversation for more candidates of that group, saying
only how many and which group.

**Correction of the package (added 2026-10-25).** Where a reading shows the package itself wrong or incomplete,
the owner may send the author a correction that states only facts about the package, the test harness and the
product's records, never about the development set, the runs or the verdicts, and ask it to correct its own
affected candidates. A corrected candidate replaces its earlier version; Claude still changes no expectation. Used
twice, on 2026-10-25: [author-correction.md](author-correction.md), answered by `author-output-2.md`, and
[author-correction-2.md](author-correction-2.md), answered by `author-output-4.md`; the reading of every answer is
in [set-aside.md](set-aside.md).

## 4. From the author's specification to scenario files

1. **Real orders by lot.** Each candidate states the shape of the orders it needs (status, number of items, distinct
   products, sellers, payment methods, and ties between orders). `refund_agent/olist.py` draws a matching Olist order
   for each by a fixed lot (the SHA-256 of the scenario ID and the order ID), never an order of the old held-out set:
   the same rule as for v1 ([data/olist/README.md](../../data/olist/README.md)). Nobody picks an order.
2. **Scenario files.** Claude writes each kept candidate as a scenario file in the project's format: the author's
   situation, roles, staff decision and expectations, unchanged; the Olist numbers in place of the author's symbolic
   amounts (`paid(u1)`), with the arithmetic in a comment; dates moved to 2026 as one block, keeping the order's
   intervals. Every place where the format needs something the author did not state (an e-mail address, an ID) is
   listed in `conversion-log.md`, with what was chosen. Claude adds no behaviour, fact or expectation.
3. **Technical checks**, free, before the freeze:
   - every file loads under the strict schema, and each `policy_checks` entry agrees with the policy code
     (`refund_agent.eligibility`);
   - each expected outcome follows from the policy text: Claude writes, per scenario, the sections that decide it and
     why; the owner reads it;
   - the simulated customer can reach its goal: its facts and behaviour cover what the agent may ask, and it never
     needs a fact it was not given;
   - the evaluator accepts a correct conversation and rejects wrong ones: for each scenario a scripted correct run
     passes in mock mode, and scripted wrong outcomes fail on the items they break (a wrong unit or amount, a refund
     without approval, a forbidden handoff, a missing required one);
   - success does not hang on a phrase or on one order of tools: the communication criteria describe what must be
     true, and the outcome is read from the database.
   A candidate whose expectations contradict the policy, or that cannot be reached, is set aside (section 3), and the
   reason recorded. A defect of the evaluator is fixed with a test and recorded; a defect of the product follows
   section 1.
4. **Approval.** The owner reads the twenty files with their decision notes and approves them.

## 5. The freeze

- The twenty files go to a new set, `scenarios/held-out-v1.1/`, apart from the old held-out set and the development
  set, with a `FROZEN` file holding the SHA-256 of each file and the date, written once and committed.
- The final runner selects the set by name, refuses to start unless every file matches `FROZEN`, and records the set,
  its `FROZEN` hash and the system commit in the run manifest, so a run of the old, known scenarios can never be
  reported as this evaluation.
- The author's output, the set-aside table, the conversion log and the decision notes are committed with the set.

## 6. Predictions, then one run

Before the run, written and committed: the quality targets of the plan for A; the decision rule already used
(qualify on safety and the targets, then the lower agent cost per resolved case); and the wording of the comparison of
A and B, chosen now:

- if the paired 95% interval of B minus A lies wholly above zero: "On new scenarios, Sol resolved X points more than
  Luna, at Y times the agent cost per resolved case";
- if it lies wholly below zero: the same sentence the other way;
- otherwise: "On 20 new scenarios no difference between Sol and Luna could be shown (X points, 95% interval ...)",
  with the note that 20 scenarios show only differences of about ten points or more.

The run: 20 scenarios x 3 tries x A, B, C = 180 conversations, the same simulated customer and evaluator, with a
budget cap. Claude reads all 180; the owner reads the conversations whose outcome a reader's judgment can change, and
every one Claude fails or notes. The simulated customer's adherence to its role is checked in every conversation and
counted apart; a conversation it broke is not a test of the agent, and nothing unread is presented as a success.

The whole result is published, whatever it is: successes, failures, intervals, cost, the set-aside table, and the
limits (one author, one run, 20 scenarios). Nothing is tuned on it. A defect it reveals is fixed in a later version,
and a new claim then needs new scenarios.
