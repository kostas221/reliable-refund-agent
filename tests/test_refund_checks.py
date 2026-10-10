"""Every check the state machine declares for execute has exactly one implementation, run in the declared order."""

from refund_agent.refunds import EXECUTE_CHECKS
from refund_agent.states import LAB_TRANSITIONS, TRANSITIONS


def test_every_declared_execute_check_is_implemented():
    (execute,) = [t for t in TRANSITIONS if t.event == "execute"]
    assert set(EXECUTE_CHECKS) == set(execute.checks)
    assert set(LAB_TRANSITIONS[0].checks) <= set(EXECUTE_CHECKS)
