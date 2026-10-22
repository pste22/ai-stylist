"""Admin auth + funnel snapshot — no Supabase, no live_server import."""
import base64
import html as html_lib
import os

import admin_portal as admin
import ops_metrics


def setup_function():
    ops_metrics.reset_for_tests()
    admin._login_fails.clear()


def _set_pw(value: str | None) -> str | None:
    prev = os.environ.get("MIRA_ADMIN_PASSWORD")
    if value is None:
        os.environ.pop("MIRA_ADMIN_PASSWORD", None)
    else:
        os.environ["MIRA_ADMIN_PASSWORD"] = value
    return prev


def _restore_pw(prev: str | None) -> None:
    if prev is None:
        os.environ.pop("MIRA_ADMIN_PASSWORD", None)
    else:
        os.environ["MIRA_ADMIN_PASSWORD"] = prev


def test_unconfigured_is_404():
    prev = _set_pw(None)
    try:
        status, _hdrs, body = admin.handle_request("/admin", {}, "1.1.1.1")
        assert status == 404
        assert "not found" in body
    finally:
        _restore_pw(prev)


def test_login_form_then_cookie():
    prev = _set_pw("secret-pass")
    try:
        status, hdrs, body = admin.handle_request("/admin", {}, "9.9.9.9")
        assert status == 200
        assert "type=\"password\"" in body
        assert "Mira admin" in body

        status, _h, _b = admin.handle_request(
            "/admin/session", {"X-Mira-Admin": "nope"}, "9.9.9.9"
        )
        assert status == 401

        status, hdrs, body = admin.handle_request(
            "/admin/session", {"X-Mira-Admin": "secret-pass"}, "9.9.9.9"
        )
        assert status == 200
        assert "mira_admin=" in hdrs.get("Set-Cookie", "")

        cookie = hdrs["Set-Cookie"].split(";")[0]
        status, hdrs, body = admin.handle_request(
            "/admin", {"Cookie": cookie}, "9.9.9.9",
            health={"status": "ok", "commit": "abc", "uptime_s": 90},
        )
        assert status == 200
        assert "Activity" in body
        assert "live" in body
    finally:
        _restore_pw(prev)


def test_http_basic_unlocks_json():
    prev = _set_pw("ops-pw")
    try:
        token = base64.b64encode(b"mira:ops-pw").decode()
        status, hdrs, body = admin.handle_request(
            "/api/admin/activity",
            {"Authorization": f"Basic {token}"},
            "8.8.8.8",
            health={"status": "ok"},
        )
        assert status == 200
        assert hdrs["Content-Type"].startswith("application/json")
        assert "funnel" in body
    finally:
        _restore_pw(prev)


def test_login_throttle():
    prev = _set_pw("x")
    try:
        ip = "2.2.2.2"
        for _ in range(admin.LOGIN_MAX_FAILS):
            admin.handle_request("/admin/session", {"X-Mira-Admin": "bad"}, ip)
        status, _h, body = admin.handle_request(
            "/admin/session", {"X-Mira-Admin": "x"}, ip
        )
        assert status == 429
        assert "too many" in body
    finally:
        _restore_pw(prev)


def test_funnel_and_top_products():
    events = [
        {"ts": 1_700_000_000, "session_id": "s1", "event": "session_start", "user_id": "u1"},
        {"ts": 1_700_000_010, "session_id": "s1", "event": "would_buy",
         "user_id": "u1", "product_id": "p1", "product_name": "Silk dress"},
        {"ts": 1_700_000_020, "session_id": "s1", "event": "buy_click",
         "user_id": "u1", "product_id": "p1", "product_name": "Silk dress"},
        {"ts": 1_700_000_030, "session_id": "s2", "event": "session_start"},
    ]
    history = [
        {"ts": 1_700_000_005, "user_id": "u1", "product_id": "p1",
         "product_name": "Silk dress", "action": "shown"},
        {"ts": 1_700_000_006, "user_id": "u1", "product_id": "p2",
         "product_name": "Quiet top", "action": "shown"},
        {"ts": 1_700_000_007, "user_id": "u1", "product_id": "p2",
         "product_name": "Quiet top", "action": "shown"},
        {"ts": 1_700_000_008, "user_id": "u1", "product_id": "p2",
         "product_name": "Quiet top", "action": "shown"},
        {"ts": 1_700_000_011, "user_id": "u1", "product_id": "p1",
         "product_name": "Silk dress", "action": "would_buy"},
        {"ts": 1_700_000_021, "user_id": "u1", "product_id": "p1",
         "product_name": "Silk dress", "action": "buy_click"},
    ]
    users = [{"user_id": "u1", "name": "Asha", "last_seen": 1_700_000_021, "first_seen": 1_700_000_000}]
    catalog = {
        "p1": {"name": "Silk dress", "price": 100, "retailer": "myntra"},
        "p2": {"name": "Quiet top", "price": 40, "retailer": "amazon"},
    }
    snap = admin.build_snapshot(
        events=events,
        history=history,
        users=users,
        health={"status": "ok", "commit": "deadbeef"},
        errors=[],
        catalog=catalog,
        days=30,
        now=1_700_000_100,
    )
    assert snap["funnel"]["sessions"] == 2
    assert snap["funnel"]["shown"] == 4
    assert snap["funnel"]["saves"] == 1  # event + history collapsed
    assert snap["funnel"]["buy_clicks"] == 1
    assert snap["funnel"]["est_revenue_usd"] == 8.0  # 100 * 8% myntra
    assert snap["top_products"][0]["product_id"] == "p1"
    assert snap["users"]["recent"][0]["name"] == "Asha"
    page = admin.render_dashboard(snap, days=30, platform="")
    assert "Silk dress" in page
    assert "$8.00" in page
    assert "Asha" in page
    dirty = admin.build_snapshot(
        events=[{"ts": 1_700_000_000, "session_id": "s", "event": "buy_click",
                 "product_id": "x", "product_name": "<script>alert(1)</script>"}],
        history=[],
        users=[],
        health={},
        errors=[],
        now=1_700_000_100,
        days=7,
    )
    html_page = admin.render_dashboard(dirty, days=7, platform="")
    assert "<script>alert(1)</script>" not in html_page
    assert html_lib.escape("<script>alert(1)</script>") in html_page


def test_platform_filter_drops_other_retailers():
    events = [
        {"ts": 1, "session_id": "s", "event": "buy_click", "product_id": "p1"},
        {"ts": 1, "session_id": "s", "event": "buy_click", "product_id": "p2"},
    ]
    catalog = {
        "p1": {"name": "A", "price": 50, "retailer": "amazon"},
        "p2": {"name": "B", "price": 50, "retailer": "myntra"},
    }
    snap = admin.build_snapshot(
        events=events, history=[], users=[], health={}, errors=[],
        catalog=catalog, platform="amazon", days=30, now=10,
    )
    assert snap["funnel"]["buy_clicks"] == 1
    assert snap["funnel"]["est_revenue_usd"] == 2.0  # 50 * 4%
