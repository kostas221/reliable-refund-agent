"""The local database is published to this computer only (review of 2026-10-19, R11): its passwords are known test
values, so a port open on every network interface would offer them to the whole network."""

import re

from refund_agent.policy import REPO_ROOT


def test_every_published_port_is_bound_to_this_computer_only():
    compose = (REPO_ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    published = re.findall(r'^\s*-\s*"([^"]+:\d+)"\s*$', compose, flags=re.MULTILINE)
    assert published, "no published port found; the check would pass for nothing"
    assert all(port.startswith("127.0.0.1:") for port in published), published


def test_the_code_connects_where_the_database_listens():
    # "localhost" first tried IPv6, where the database does not listen: three seconds lost on every connection.
    source = (REPO_ROOT / "refund_agent" / "db.py").read_text(encoding="utf-8")
    assert 'HOST = os.environ.get("REFUND_DB_HOST", "127.0.0.1")' in source
