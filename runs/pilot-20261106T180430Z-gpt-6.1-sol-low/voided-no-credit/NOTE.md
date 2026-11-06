# Voided tries: the provider account ran out of credit

At D92 try 2 the provider refused the agent's request with HTTP 429 `insufficient_quota`
(`credit_balance_exhausted`), and the runner stopped; nothing later ran. D92 try 1 completed, but D92 is voided whole
so that each scenario's three tries come from one run, as on 2026-11-01. The rule was given to the owner before the
second part ran and before any try was read.

The run counts D01 to D91 (273 conversations). D92 to D128 ran again, at the same commit and with the same settings,
in `runs/pilot-20261106T194322Z-gpt-6.1-sol-low`; the two are read and reported together in
`runs/pilot-20261106T194322Z-gpt-6.1-sol-low-joined`.
