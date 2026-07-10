"""Tes services/bigmoney/idx_client — retry, paginasi, hari non-bursa.

Seluruh HTTP di-mock. Tidak ada tes yang menyentuh jaringan.
"""
from datetime import date

import pytest

from services.bigmoney import idx_client
from services.bigmoney.idx_client import IdxFetchError, fetch_stock_summary

TARGET = date(2026, 7, 9)


class _Resp:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload if payload is not None else {}

    def json(self):
        return self._payload


@pytest.fixture(autouse=True)
def no_sleep(mocker):
    """Backoff nyata bikin tes lambat; matikan."""
    mocker.patch("services.bigmoney.idx_client.time.sleep")


def test_get_json_retries_network_error_then_succeeds(mocker):
    session = mocker.Mock()
    session.get.side_effect = [
        ConnectionError("reset"),
        ConnectionError("reset"),
        _Resp(200, {"data": [{"StockCode": "BBCA"}]}),
    ]

    payload = idx_client._get_json(session, "http://x")

    assert payload["data"][0]["StockCode"] == "BBCA"
    assert session.get.call_count == 3


def test_get_json_retries_server_error(mocker):
    session = mocker.Mock()
    session.get.side_effect = [_Resp(503), _Resp(200, {"data": []})]

    assert idx_client._get_json(session, "http://x") == {"data": []}
    assert session.get.call_count == 2


def test_get_json_gives_up_after_max_retries(mocker):
    session = mocker.Mock()
    session.get.side_effect = ConnectionError("reset")

    with pytest.raises(IdxFetchError, match="jaringan"):
        idx_client._get_json(session, "http://x")

    assert session.get.call_count == 3


def test_get_json_client_error_does_not_retry(mocker):
    session = mocker.Mock()
    session.get.return_value = _Resp(404)

    with pytest.raises(IdxFetchError, match="404"):
        idx_client._get_json(session, "http://x")

    assert session.get.call_count == 1


def test_fetch_stock_summary_non_trading_day_returns_empty(mocker):
    """Sabtu/libur: IDX balas HTTP 200 dengan nol baris, bukan error."""
    mocker.patch("services.bigmoney.idx_client._new_session")
    mocker.patch("services.bigmoney.idx_client._get_json",
                 return_value={"data": [], "recordsTotal": 0})

    assert fetch_stock_summary(date(2026, 7, 4)) == []


def test_fetch_stock_summary_single_page(mocker):
    mocker.patch("services.bigmoney.idx_client._new_session")
    mocker.patch("services.bigmoney.idx_client._get_json",
                 return_value={"data": [{"StockCode": "BBCA"}], "recordsTotal": 1})

    rows = fetch_stock_summary(TARGET)

    assert len(rows) == 1
    assert rows[0]["StockCode"] == "BBCA"


def test_fetch_stock_summary_paginates(mocker):
    """recordsTotal melebihi satu halaman → ambil halaman berikutnya."""
    mocker.patch("services.bigmoney.idx_client._new_session")
    mocker.patch.object(idx_client, "_PAGE_SIZE", 2)
    get_json = mocker.patch(
        "services.bigmoney.idx_client._get_json",
        side_effect=[
            {"data": [{"StockCode": "A"}, {"StockCode": "B"}], "recordsTotal": 3},
            {"data": [{"StockCode": "C"}], "recordsTotal": 3},
        ],
    )

    rows = fetch_stock_summary(TARGET)

    assert [r["StockCode"] for r in rows] == ["A", "B", "C"]
    assert get_json.call_count == 2
    assert "start=0" in get_json.call_args_list[0].args[1]
    assert "start=2" in get_json.call_args_list[1].args[1]


def test_fetch_stock_summary_sends_target_date(mocker):
    mocker.patch("services.bigmoney.idx_client._new_session")
    get_json = mocker.patch("services.bigmoney.idx_client._get_json",
                            return_value={"data": [], "recordsTotal": 0})

    fetch_stock_summary(TARGET)

    assert "date=2026-07-09" in get_json.call_args.args[1]


def test_new_session_retries_failing_homepage_get(mocker):
    """_new_session retries homepage GET if it fails."""
    session_class = mocker.patch("services.bigmoney.idx_client.cffi_requests.Session")
    session_instance = mocker.Mock()
    session_class.return_value = session_instance

    # First two GETs fail with network error, third succeeds
    session_instance.get.side_effect = [
        ConnectionError("timeout"),
        ConnectionError("timeout"),
        _Resp(200),  # successful response
    ]

    result = idx_client._new_session()

    assert result is session_instance
    assert session_instance.get.call_count == 3


def test_new_session_exhausts_retries_on_network_error(mocker):
    """_new_session raises IdxFetchError after 3 failed attempts."""
    session_class = mocker.patch("services.bigmoney.idx_client.cffi_requests.Session")
    session_instance = mocker.Mock()
    session_class.return_value = session_instance
    session_instance.get.side_effect = ConnectionError("timeout")

    with pytest.raises(IdxFetchError, match="jaringan"):
        idx_client._new_session()

    assert session_instance.get.call_count == 3


def test_new_session_no_retry_on_client_error(mocker):
    """_new_session raises immediately on 4xx (no retry)."""
    session_class = mocker.patch("services.bigmoney.idx_client.cffi_requests.Session")
    session_instance = mocker.Mock()
    session_class.return_value = session_instance
    session_instance.get.return_value = _Resp(403)

    with pytest.raises(IdxFetchError, match="403"):
        idx_client._new_session()

    assert session_instance.get.call_count == 1


def test_client_error_classified_by_type_not_message(mocker):
    """Exception type (not message text) determines whether errors are retried.

    4xx responses raise _NonRetryable without retry, regardless of message wording.
    """
    session = mocker.Mock()
    session.get.return_value = _Resp(400)

    with pytest.raises(idx_client._NonRetryable):
        idx_client._get_json(session, "http://x")

    # Verify no retries occurred
    assert session.get.call_count == 1
