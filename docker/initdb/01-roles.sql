-- Runs once, when the database volume is created. Local test passwords only.
-- refund_owner runs migrations and loads order data; refund_app is the role the application uses.
CREATE ROLE refund_owner LOGIN PASSWORD 'refund_owner' CREATEDB;
CREATE ROLE refund_app LOGIN PASSWORD 'refund_app';
