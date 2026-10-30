from weedlab.api.clientip import client_key


def test_ignores_header_when_no_proxy_is_trusted() -> None:
    headers = {"x-forwarded-for": "6.6.6.6"}
    assert client_key("10.0.0.1", headers, 0) == "10.0.0.1"


def test_uses_last_entry_for_one_trusted_proxy() -> None:
    headers = {"x-forwarded-for": "1.1.1.1, 203.0.113.9"}
    assert client_key("10.0.0.1", headers, 1) == "203.0.113.9"


def test_forged_entries_on_the_left_do_not_change_the_key() -> None:
    real = {"x-forwarded-for": "203.0.113.9"}
    forged = {"x-forwarded-for": "6.6.6.6, 7.7.7.7, 203.0.113.9"}
    assert client_key("10.0.0.1", real, 1) == client_key("10.0.0.1", forged, 1)


def test_two_trusted_proxies_use_second_from_right() -> None:
    headers = {"x-forwarded-for": "203.0.113.9, 172.16.0.5"}
    assert client_key("10.0.0.1", headers, 2) == "203.0.113.9"


def test_falls_back_when_header_is_missing_or_short() -> None:
    assert client_key("10.0.0.1", {}, 1) == "10.0.0.1"
    assert client_key("10.0.0.1", {"x-forwarded-for": "203.0.113.9"}, 2) == "10.0.0.1"
    assert client_key(None, {}, 1) == "unknown"


def test_long_values_are_cut_down() -> None:
    headers = {"x-forwarded-for": "x" * 500}
    assert len(client_key("10.0.0.1", headers, 1)) == 64
