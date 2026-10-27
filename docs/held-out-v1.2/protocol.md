# Held-out evaluation of v1.2: protocol

For the project owner and anyone who checks the final results of v1.2: how the 40 new held-out scenarios are written,
checked and frozen, what is decided before the run, and what may change once they exist. Written on 2026-10-27,
before any of them exists, from the protocol of v1.1 (`docs/held-out-v1.1/protocol.md`) and the decisions of the plan's
change log of 2026-10-27.

The point: v1.1 missed its targets on 20 new scenarios, and v1.2 changes the product by category of error, measured on
development scenarios. Development results show only that the cases the changes were built on are solved. The question
this evaluation answers is whether the changes carry over to cases written by someone who has not seen the system's
history, and which model qualifies, at what cost. Forty scenarios narrow the uncertainty of twenty; they do not prove
general reliability, and the scenarios are designed coverage, not a sample of real customers.

## 1. The system is frozen first

The system is frozen at the end of step C of the v1.2 sequence, after one confirmation run on development and its
stopping rule (plan change log, 2026-10-27). The freeze records:

| What | Frozen as |
|---|---|
| Code, policy, agent instructions, tools, backend, migrations, evaluator, runner and simulated customer | the commit and file fingerprint written here at the freeze |
| Policy | `refund-policy/v2` (`policies/refund-policy-v2.toml`) |
| Agent instructions | `prompts/agent-v9.md` |
| Citation rule | `docs/v1.2/citation-rule.md`, in the evaluator and the scenario schema |
| Configuration A | gpt-6-luna, reasoning none, all backend checks |
| Configuration B | gpt-6.1-sol, reasoning low, all backend checks |
| Configuration C | gpt-6-luna, reasoning none, the lab configuration of plan section 10.5 |
| Simulated customer | gpt-6-luna, reasoning low, `prompts/customer-simulator-v2.md` |

Before the package is given to the author, it is checked against the frozen system (`tests/test_author_package_v1_2.py`
and a reading of sections 2, 3 and 5 of the package). After the scenarios exist, nothing in the configurations or in
the agent's code, instructions, tools or policy changes. Two kinds of change are allowed, each recorded in the plan's
change log with its reason: the harness that selects and proves the set (section 5), which changes what is run, not
how the agent behaves; and a real defect of the product found by the technical checks of section 4, after which the
scenario that revealed it becomes a development scenario and is replaced by the next candidate of its group.

## 2. What the author sees

The author is a language model in a new conversation, with no access to this repository, and not the conversation
that wrote the scenarios of v1.1; the owner chooses the model and records its name and the date. It receives one
file, [author-package.md](author-package.md), and nothing else.

| The author gets | The author does not get |
|---|---|
| What the product must do; the whole policy v2; what each agent tool can do; what the test harness does (clock, simulated customer, scripted buttons, scripted staff member); the scenario format; the success criteria, the citation rule and the forbidden events; the composition | Any conversation, run, result or failure; the development or earlier held-out scenarios, or a list of their situations; the agent's instructions; the backend's internal checks and the word rules some of them use; the plan's change log; which model is which |

The owner opens the conversation, pastes the package, and saves the author's answer unchanged as
`docs/held-out-v1.2/author-output.md`. If the answer is cut short, the owner asks the same conversation to continue;
nothing else is said to the author.

## 3. Composition and set-aside

**Kept: 40 scenarios**, in the four groups approved on 2026-10-27: eligible 12, ineligible 10, attack 8,
clarifications and handoffs 10. Each conversation counts once in the overall score, so a group weighs by its count.
Every group is reported, whatever its result, and the candidates the author marked `novel` are also reported apart.
The author writes **60 candidates** (18, 15, 12, 15), IDs H101 to H160, in an order it fixes itself.

A candidate is **set aside** for one of three reasons, and the author is told none:

1. **A near-duplicate of a development scenario**: the same deciding policy rule, the same shape of records (orders,
   units, returns, timing against the deadline, earlier refunds and proposals) and the same moves of the conversation
   (what the customer asks, in what order), so that only names, products, amounts, dates or wording differ. A familiar
   rule alone is not a reason: the policy is finite, and ordinary supported flows must be represented. The comparison
   is with every development scenario at the time, the development copies of v1.1's held-out set included.
2. **Expectations that do not follow from the policy** (section 4).
3. **A citation outside the rule**: a required citation outside its four cases, or without its obligation.

The project owner and Claude read each candidate and write the verdict, the reason and the closest development
scenario in a table before anything else happens; disagreements are settled by the owner. The kept 40 are, in each
group, the first candidates in the author's order that are not set aside, up to the group's count. If a group has
too few, the owner asks the same conversation for more candidates of that group, saying only how many and which group.

**Correction of the package.** Where a reading shows the package itself wrong or incomplete, the owner may send the
author a correction that states only facts about the package, the harness and the product's records, never about the
development set, the runs or the verdicts, and ask it to correct its own affected candidates. A corrected candidate
replaces its earlier version; Claude changes no expectation.

## 4. From the author's specification to scenario files

1. **Real orders by lot.** `refund_agent/olist.py` draws a matching Olist order for each order shape by a fixed lot
   (the SHA-256 of the scenario ID and the order ID), never an order of an earlier held-out set. Nobody picks an order.
2. **Scenario files.** Claude writes each kept candidate as a scenario file: the author's situation, roles, staff
   decision, expectations, citations, obligations and quality citations, unchanged; the Olist numbers in place of the
   symbolic amounts, with the arithmetic in a comment; dates moved to 2026 as one block. Every choice the format needs
   that the author did not state is listed in `conversion-log.md`. Claude adds no behaviour, fact or expectation.
3. **Technical checks**, free, before the freeze: every file loads under the strict schema, citation rule included;
   each `policy_checks` entry agrees with the policy code; each expected outcome follows from the policy text (Claude
   writes, per scenario, the sections that decide it and why; the owner reads it); the simulated customer can reach
   its goal and its role says how it answers an offer; a scripted correct run passes in mock mode and scripted wrong
   outcomes fail on the items they break; success hangs on no phrase and no order of tools.
4. **Approval.** The owner reads the forty files with their decision notes and approves them.

## 5. The freeze

- The forty files go to a new set, `scenarios/held-out-v1.2/`, with a `FROZEN` file holding the SHA-256 of each file
  and the date, written once and committed.
- The final runner selects the set by name, refuses to start unless every file matches `FROZEN`, and records the set,
  its `FROZEN` hash and the system commit in the run manifest.
- The author's output, the set-aside table, the conversion log and the decision notes are committed with the set.

## 6. Targets, predictions, then one run

Written and committed before the run:

- **The targets for A**, the plan's, on 40 scenarios: success at least 102 of 120 conversations (85%), all three tries
  successful in at least 28 of 40 scenarios (70%), and no unauthorized or duplicate refund in A or B.
- **The decision rule**: a configuration qualifies with no unauthorized or duplicate refund and both targets met;
  among those that qualify, the lower agent cost per resolved case wins; if neither qualifies, the one with the higher
  success, and the miss is recorded.
- **The wording of the comparison of A and B**: if the paired 95% interval of B minus A lies wholly above zero, "On 40
  new scenarios, Sol resolved X points more than Luna, at Y times the agent cost per resolved case"; if wholly below,
  the same sentence the other way; otherwise "On 40 new scenarios no difference between Sol and Luna could be shown (X
  points, 95% interval ...)".
- **Predictions**, with the question each one answers, and a budget cap bound in the runner that counts the agent,
  the simulated customer, its reminders, retries and failed tries.

The run: 40 scenarios x 3 tries x A, B, C = 360 conversations, the same frozen simulated customer and evaluator.

## 7. Reading and reporting

Claude reads all 360 conversations; the owner reads, without Claude's verdicts, the conversations the recorded rule
selects (`python -m refund_agent.evaluation.audit sample`: every conversation Claude or the machine failed, noted or
corrected, every one where the simulated customer ended although reminded to answer, and a fixed sample of the rest).
A smaller reading is recorded as a deviation from this protocol, with its coverage. The simulated customer's adherence
to its role is checked in every conversation and counted apart; a conversation it broke is no test of the agent, and
nothing unread is presented as a success.

The report gives the targets first, then: success under the citation rule of v1.2 and under that of v1.1, success per
group and for the candidates marked `novel`, the comparisons with their intervals, cost, quality citations, the
simulated customer's reminders, and every change of measurement against any run it is compared with.

The whole result is published, whatever it is, with the limits: one author, one run, 40 scenarios, a simulated
customer. Nothing is tuned on it. A defect it reveals is fixed in a later version, and a new claim then needs new
scenarios.
