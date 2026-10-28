# Comparison: runs/pilot-20261027T144002Z-gpt-6-luna-none

Against runs/pilot-20261024T120131Z-gpt-6-luna-none, runs/final-v1.1-20261026T125831Z/A. Paired bootstrap by scenario, 10000 draws, seed 20261019: the new run minus the earlier one, in the share of each scenario's tries that succeeded. A scenario is paired with itself where a base ran it, and a copy otherwise with its held-out source.

- Difference: +11.8 points (95% interval +5.4 to +19.4), over 62 scenarios
- Better / same / worse: 10 / 52 / 0
- Without a counterpart: none
- Measurement changed between the runs: runs/pilot-20261024T120131Z-gpt-6-luna-none: refund_agent/evaluation/evaluator.py; runs/pilot-20261024T120131Z-gpt-6-luna-none: refund_agent/evaluation/runner.py; runs/pilot-20261024T120131Z-gpt-6-luna-none: refund_agent/evaluation/customers.py; runs/pilot-20261024T120131Z-gpt-6-luna-none: refund_agent/fixtures.py; runs/pilot-20261024T120131Z-gpt-6-luna-none: scenarios/development/D05-late-then-asks-for-person.toml; runs/pilot-20261024T120131Z-gpt-6-luna-none: scenarios/development/D06-not-yet-returned.toml; runs/pilot-20261024T120131Z-gpt-6-luna-none: scenarios/development/D10-late-after-expired-on-time-proposal.toml; runs/pilot-20261024T120131Z-gpt-6-luna-none: scenarios/development/D12-discounted-item-in-mixed-order.toml; runs/pilot-20261024T120131Z-gpt-6-luna-none: scenarios/development/D13-whole-order-partly-returned.toml; runs/pilot-20261024T120131Z-gpt-6-luna-none: scenarios/development/D14-asks-when-money-arrives.toml; runs/pilot-20261024T120131Z-gpt-6-luna-none: scenarios/development/D19-order-not-delivered.toml; runs/pilot-20261024T120131Z-gpt-6-luna-none: scenarios/development/D20-everything-already-refunded.toml; runs/pilot-20261024T120131Z-gpt-6-luna-none: scenarios/development/D21-just-after-deadline.toml; runs/pilot-20261024T120131Z-gpt-6-luna-none: scenarios/development/D22-claims-sent-but-not-received.toml; runs/pilot-20261024T120131Z-gpt-6-luna-none: scenarios/development/D24-redirect-to-other-card.toml; runs/pilot-20261024T120131Z-gpt-6-luna-none: scenarios/development/D29-two-payment-records.toml; runs/pilot-20261024T120131Z-gpt-6-luna-none: scenarios/development/D35-shipment-status-only.toml; runs/pilot-20261024T120131Z-gpt-6-luna-none: scenarios/development/D37-yes-to-offered-staff.toml; runs/pilot-20261024T120131Z-gpt-6-luna-none: scenarios/development/D38-no-to-offered-staff.toml; runs/pilot-20261024T120131Z-gpt-6-luna-none: scenarios/development/D39-shipping-question.toml; runs/pilot-20261024T120131Z-gpt-6-luna-none: scenarios/development/D40-shipping-refund-request.toml; runs/pilot-20261024T120131Z-gpt-6-luna-none: scenarios/development/D41-payment-destination-after-receipt.toml; runs/pilot-20261024T120131Z-gpt-6-luna-none: scenarios/development/D42-new-request-after-receipt.toml; runs/pilot-20261024T120131Z-gpt-6-luna-none: simulator instructions: prompts/customer-simulator-v1.md -> prompts/customer-simulator-v2.md; runs/final-v1.1-20261026T125831Z/A: refund_agent/evaluation/evaluator.py; runs/final-v1.1-20261026T125831Z/A: refund_agent/evaluation/runner.py; runs/final-v1.1-20261026T125831Z/A: refund_agent/evaluation/customers.py; runs/final-v1.1-20261026T125831Z/A: refund_agent/fixtures.py; runs/final-v1.1-20261026T125831Z/A: simulator instructions: prompts/customer-simulator-v1.md -> prompts/customer-simulator-v2.md. The difference is a combined change of the product and the measurement, not the product's alone.

| Scenario | Paired with | Before | After |
|---|---|---|---|
| D01 | D01 | 1.00 | 1.00 |
| D02 | D02 | 1.00 | 1.00 |
| D03 | D03 | 1.00 | 1.00 |
| D04 | D04 | 1.00 | 1.00 |
| D05 | D05 | 1.00 | 1.00 |
| D06 | D06 | 1.00 | 1.00 |
| D07 | D07 | 1.00 | 1.00 |
| D08 | D08 | 1.00 | 1.00 |
| D09 | D09 | 1.00 | 1.00 |
| D10 | D10 | 1.00 | 1.00 |
| D11 | D11 | 1.00 | 1.00 |
| D12 | D12 | 1.00 | 1.00 |
| D13 | D13 | 1.00 | 1.00 |
| D14 | D14 | 1.00 | 1.00 |
| D15 | D15 | 1.00 | 1.00 |
| D16 | D16 | 1.00 | 1.00 |
| D17 | D17 | 1.00 | 1.00 |
| D18 | D18 | 1.00 | 1.00 |
| D19 | D19 | 1.00 | 1.00 |
| D20 | D20 | 1.00 | 1.00 |
| D21 | D21 | 1.00 | 1.00 |
| D22 | D22 | 1.00 | 1.00 |
| D23 | D23 | 1.00 | 1.00 |
| D24 | D24 | 1.00 | 1.00 |
| D25 | D25 | 1.00 | 1.00 |
| D26 | D26 | 1.00 | 1.00 |
| D27 | D27 | 1.00 | 1.00 |
| D28 | D28 | 0.33 | 1.00 |
| D29 | D29 | 1.00 | 1.00 |
| D30 | D30 | 1.00 | 1.00 |
| D31 | D31 | 1.00 | 1.00 |
| D32 | D32 | 1.00 | 1.00 |
| D33 | D33 | 1.00 | 1.00 |
| D34 | D34 | 1.00 | 1.00 |
| D35 | D35 | 1.00 | 1.00 |
| D36 | D36 | 1.00 | 1.00 |
| D37 | D37 | 1.00 | 1.00 |
| D38 | D38 | 1.00 | 1.00 |
| D39 | D39 | 1.00 | 1.00 |
| D40 | D40 | 1.00 | 1.00 |
| D41 | D41 | 1.00 | 1.00 |
| D42 | D42 | 1.00 | 1.00 |
| D43 | H26 | 0.00 | 1.00 |
| D44 | H28 | 1.00 | 1.00 |
| D45 | H29 | 1.00 | 1.00 |
| D46 | H30 | 0.33 | 1.00 |
| D47 | H35 | 1.00 | 1.00 |
| D48 | H40 | 1.00 | 1.00 |
| D49 | H41 | 0.67 | 1.00 |
| D50 | H42 | 1.00 | 1.00 |
| D51 | H47 | 1.00 | 1.00 |
| D52 | H50 | 0.67 | 1.00 |
| D53 | H52 | 1.00 | 1.00 |
| D54 | H55 | 0.00 | 1.00 |
| D55 | H58 | 1.00 | 1.00 |
| D56 | H60 | 1.00 | 1.00 |
| D57 | H61 | 1.00 | 1.00 |
| D58 | H63 | 1.00 | 1.00 |
| D59 | H72 | 0.33 | 1.00 |
| D60 | H74 | 0.00 | 1.00 |
| D61 | H77 | 0.33 | 1.00 |
| D62 | H80 | 0.00 | 1.00 |
