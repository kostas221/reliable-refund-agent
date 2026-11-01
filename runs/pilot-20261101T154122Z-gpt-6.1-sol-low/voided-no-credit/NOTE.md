# Voided tries: the provider account ran out of credit

From D51 try 2 on, every request of this run was refused by the provider with HTTP 429 `insufficient_quota`
(`credit_balance_exhausted`): first the simulated customer's (D51 try 2), then every agent request. No later try
tested the agent, so all are voided and kept here, unread for verdicts. D51 try 1 completed, but D51 is voided whole
so that each scenario's three tries come from one run; the rule was set before any try of this run was read (plan
change log, 2026-11-01).

The run counts D01 to D50 (150 conversations, $0.86 of agent cost). D51 to D89 are run again, at the same commit and
with the same settings, in a second pilot run; the two are read and reported together.
