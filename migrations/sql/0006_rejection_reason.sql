-- The staff member's reason for a rejection (dialogue audit of 2026-10-18). The product contract promises the
-- customer the final state and its reason, but a rejection stored none: the customer and the agent learned only that
-- the request was rejected. A rejection now carries the reason the staff member writes for the customer, and an
-- approval carries none. The decision and its reason commit together, and the runtime role still cannot change
-- either afterwards. NOT VALID: decisions stored before this rule keep their place; every new one is checked.
ALTER TABLE staff_decisions ADD COLUMN reason text;
ALTER TABLE staff_decisions ADD CONSTRAINT staff_decisions_reason CHECK (
    (decision = 'approved' AND reason IS NULL)
    OR (decision = 'rejected' AND reason IS NOT NULL AND char_length(btrim(reason)) BETWEEN 1 AND 500)
) NOT VALID;
