"""Keep the suite hermetic: a developer's .env may hold a real OpenAQ key, and
without this a test that touches the live-data path would call the network
(slow, flaky, and different on every machine). Tests that exercise the live
path set the key and fake the HTTP call themselves."""
import pytest


@pytest.fixture(autouse=True)
def _no_live_network(monkeypatch):
    monkeypatch.delenv("OPENAQ_API_KEY", raising=False)
