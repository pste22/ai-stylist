"""Unit tests for daily try-on spend guardrails."""
from gen_spend import check, is_cap_message, is_demo_email, parse_demo_emails, SPEND_MSG


def test_parse_demo_emails_default_founder():
    emails = parse_demo_emails("pste22@gmail.com")
    assert is_demo_email("pste22@gmail.com", emails)
    assert is_demo_email("PSTE22@Gmail.com", emails)
    assert not is_demo_email("someone@else.com", emails)
    assert not is_demo_email(None, emails)
    assert not is_demo_email("", emails)


def test_parse_demo_emails_csv_and_whitespace():
    emails = parse_demo_emails(" a@x.com, b@y.com ,")
    assert emails == frozenset({"a@x.com", "b@y.com"})
    assert parse_demo_emails("") == frozenset()
    assert parse_demo_emails(None) == frozenset()


def test_user_cap_blocks_regular_account():
    reason = check(
        disabled=False,
        total=1.07,
        user_spent=1.07,
        est=0.44,
        global_cap=15.0,
        user_cap=1.5,
        enforce_user_cap=True,
    )
    assert reason == "user_cap"
    assert "see you tomorrow" in SPEND_MSG[reason]


def test_demo_account_skips_user_cap_not_global():
    under_global = check(
        disabled=False,
        total=1.07,
        user_spent=1.07,
        est=0.44,
        global_cap=15.0,
        user_cap=1.5,
        enforce_user_cap=False,  # demo email
    )
    assert under_global is None

    over_global = check(
        disabled=False,
        total=14.80,
        user_spent=14.80,
        est=0.44,
        global_cap=15.0,
        user_cap=1.5,
        enforce_user_cap=False,
    )
    assert over_global == "global_cap"


def test_kill_switch_wins():
    assert check(
        disabled=True,
        total=0.0,
        user_spent=0.0,
        est=0.04,
        global_cap=15.0,
        user_cap=1.5,
        enforce_user_cap=True,
    ) == "disabled"


def test_anonymous_has_no_user_cap():
    # Matches live_server: no user_id → do not enforce the per-user ledger.
    reason = check(
        disabled=False,
        total=0.0,
        user_spent=0.0,
        est=2.0,
        global_cap=15.0,
        user_cap=1.5,
        enforce_user_cap=False,
    )
    assert reason is None


def test_is_cap_message_hides_retry():
    assert is_cap_message(SPEND_MSG["user_cap"])
    assert is_cap_message(SPEND_MSG["global_cap"])
    assert is_cap_message(SPEND_MSG["disabled"])
    assert not is_cap_message("Something went wrong generating the video")
    assert not is_cap_message(None)
