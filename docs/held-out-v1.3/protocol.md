# Held-out comparison set of v1.3: protocol (draft)

For the project owner, who runs the authoring, and for anyone checking that the scenarios comparing two agent models
were written by someone who had not seen the system. Written on 2026-11-01, at the owner's request, before any
scenario exists. The comparison itself runs after the release (plan change log, 2026-11-01). Sections 3 to 5 are a
draft, completed before the freeze.

The point: v1.2's held-out set could not separate the two models it compared. B (GPT-6.1 Sol) succeeded in 54 of 57
conversations, so a better model could gain at most 3. This set is written to compare Sol with an Anthropic model
(Claude Sonnet) on situations that are new and, for the most part, harder: two or more rules in one conversation, and
conversations that change course.

## 1. Authoring, now

1. The owner gives [author-package.md](author-package.md), and nothing else, to a language model in a new
   conversation, with no memory of this project. A model of a third family is recommended: not OpenAI and not
   Anthropic, since the comparison is between one model of each.
2. If the answer is cut short, the owner writes only "Continue from the next candidate." The owner sends nothing else
   unless this protocol says so.
3. The owner saves the answer unchanged **outside this repository**, for example in a personal folder, and records
   the model's name, the product it ran in and the date.

Before the package is sent, `tests/test_author_package_v1_3.py` must pass. That test checks that the package states
the policy word for word, names the agent's real tools and the evaluator's criteria, lists the development set as it
is, recomputes the coverage counts, and names no model, run or earlier held-out scenario.

## 2. Sealed until the freeze

**Update, 2026-11-02, owner-requested early screening and selection:** the owner supplied the two author answers
for review before the comparison-system freeze and then requested a 40-case selection. A reviewer has now read
H401-H472. This is a recorded departure from the sealed process described below; do not claim that nobody on the
system side has seen the candidates. The review must not be used to tune the agent. A candidate that informs a
product change becomes development evidence and must be replaced for a fresh holdout claim. The review records and
provisional selection are under this directory; the original author text has not been edited.

**Update, 2026-11-02, where the author's answers are kept:** the two answers had been saved, uncommitted, over v1.2's
`docs/held-out-v1.2/author-output.md` and `author-output-2.md`, which are the record of v1.2's authoring. They are now
in this directory as `author-output.md` (H401-H460) and `author-output-2.md` (H461-H472), byte for byte (the
SHA-256 values of `selected-39-manifest.json`), and v1.2's two files are restored from Git. The source paths of the
manifest and of `selected-39-author-specifications.md` were changed to the new place. Since every candidate has been
read (above), keeping the answers outside the repository (section 1, step 3) no longer protects anything.

Claude does not read the answer until the system for the comparison is frozen. The freeze comes after the five-person
trial and its fixes, and after an adapter for the Anthropic model exists and passes its checks. Until then the owner
does not paste the answer into a conversation with Claude or into the repository.

The reason: v1.2's protocol froze the system before the author received the package. Here the package goes out
before the freeze, so that authoring can proceed while the release is finished. The same independence is kept a
different way. No change to the system can be shaped by candidates nobody on the system's side has read.

If the policy or an agent tool changes before the freeze, the statements of the package it affects are sent to the
author as facts only, as in v1.1 and v1.2, or the candidates it affects are set aside. Neither is expected: the
release brief's remaining work changes neither.

## 3. At the freeze (draft)

- **Appendix A is regenerated** from the development set as it is then (`scripts/development_catalogue.py`). A
  candidate that repeats a development scenario added after the package was sent is set aside too.
- **Screening.** Each candidate is read by the test of the package's section 1.2, against one development scenario
  at a time, with the author's `nearest` and `difference` as a starting point, not as the verdict. The facts of
  section 5.1 are checked, and the result goes to a set-aside table, as in v1.2.
- **Places (owner's updated decision of 2026-11-02).** 39 places after removing H463 from the initial 40-case
  selection, without replacement: eligible 14, ineligible 8, attack 8, clarification_handoff 9, split into
  6 required handoffs and 3 clarifications without handoff. Candidates are kept in the author's order within their
  group after screening. The provisional list is `selected-39-index.md`; `selected-39-manifest.json` records exact
  source hashes and the removal reason and marks it not ready for a paid run. Conversion and mock checks must be
  completed before the selection becomes an executable frozen set. Any replacement is recorded before runs,
  with its policy, feasibility, or novelty reason and the same composition; no model result informs selection.
- **Further requests.** Corrections and further requests to the author state only facts. A stopping rule is written
  before the first further request.

## 4. Conversion, freeze of the set, predictions and one run (draft)

**Update, 2026-11-03, the conversion:** the 39 selected candidates are converted to `scenarios/held-out-v1.3/` (split
`held_out_v1_3`) by `scripts/convert_held_out_v1_3.py`. The orders are drawn by `uv run python -m refund_agent.olist
v1.3`, with the author's ties, as `data/olist/subset-v1.3.json`. The conversion is recorded in
[conversion-log.md](conversion-log.md), and the choices that need the owner are in
[decision-notes.md](decision-notes.md). The free checks pass: the fidelity tests, the policy checks against the code,
a correct mocked conversation in all 39 while wrong ones fail, and 12 of 12 planted file errors caught. The set is not
frozen until the owner approves it.

As in v1.2's protocol, sections 4 to 7:

- the files are converted with a conversion log;
- the owner approves the set, and it is frozen;
- the targets, the predictions and the decision rule are written before the run;
- there is one run of each configuration, three tries per scenario, paired by scenario.

The configurations are Sol with reasoning `low` and the Anthropic model at a setting fixed before the run, both with
the agent of the freeze.

## 5. Known limits, to be decided before the run

- **The simulated customer is an OpenAI model** (GPT-6 Luna). It may suit an OpenAI agent better. Before the run,
  the choice of simulator for this comparison is decided and recorded, for example the same simulator for both
  configurations, or a simulator from a third family.
- **What 39 scenarios can show.** Thirty-nine scenarios with three tries each remain a small designed coverage set,
  not a sample of real customers. The repeated tries do not make 117 independent tasks. Report the paired interval
  by scenario and category results, without promising a detectable difference in advance merely from the case count.
