"""In-process uptime / glitch counters."""
import ops_metrics as m


def setup_function():
    m.reset_for_tests()


def test_record_error_and_snapshot():
    m.record_error("live_session", "gemini 429")
    m.record_error("circuit_open", "upstream")
    snap = m.snapshot()
    assert snap["errors_total"] == 2
    assert snap["errors_last_hour"] == 2
    assert snap["circuit_opens"] == 1
    assert snap["uptime_s"] >= 0
    recent = m.errors_since(60)
    assert recent[0]["kind"] == "circuit_open"


def test_session_open_close():
    m.session_open("abc", user_id="u1", name="Prashant")
    assert m.snapshot()["active_sessions"] == 1
    live = m.active_sessions()
    assert live[0]["name"] == "Prashant"
    m.session_close("abc")
    assert m.snapshot()["active_sessions"] == 0


def test_request_p95_and_5xx():
    for i in range(10):
        m.record_request("/api/browse", 200, 10 + i)
    m.record_request("/api/browse", 502, 80)
    snap = m.snapshot()
    assert snap["http_requests"] == 11
    assert snap["http_5xx"] == 1
    assert snap["http_p95_ms"] >= 10
