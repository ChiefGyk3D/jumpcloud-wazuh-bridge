import json
import logging
import os
import subprocess
from unittest.mock import MagicMock, patch

import pytest
import requests

from jumpcloud_wazuh_bridge.config import _doppler_secrets, load_settings


def _load(env, doppler=None):
    with patch.dict(os.environ, env, clear=True), patch(
        "jumpcloud_wazuh_bridge.config._doppler_secrets", return_value=doppler or {}
    ):
        return load_settings()


def test_load_defaults():
    """Settings fall back to defaults when no env vars set."""
    s = _load({})
    assert s.api_key == ""
    assert s.base_url == "https://api.jumpcloud.com"
    assert s.poll_seconds == 300
    assert s.services == ["all"]
    assert s.page_limit == 1000


def test_load_from_env():
    s = _load(
        {
            "JUMPCLOUD_API_KEY": "test-key",
            "JUMPCLOUD_ORG_ID": "org-123",
            "JUMPCLOUD_SERVICES": "directory,sso,radius",
            "JUMPCLOUD_POLL_SECONDS": "60",
        }
    )
    assert s.api_key == "test-key"
    assert s.org_id == "org-123"
    assert s.services == ["directory", "sso", "radius"]
    assert s.poll_seconds == 60


def test_doppler_values_take_precedence_over_env():
    s = _load(
        {"JUMPCLOUD_API_KEY": "env-key"},
        doppler={"JUMPCLOUD_API_KEY": "doppler-key"},
    )
    assert s.api_key == "doppler-key"


def test_services_stripped_and_empties_dropped():
    s = _load({"JUMPCLOUD_SERVICES": " directory , sso ,,"})
    assert s.services == ["directory", "sso"]


def test_services_empty_string_yields_empty_list():
    s = _load({"JUMPCLOUD_SERVICES": ""})
    assert s.services == []


# ---------------------------------------------------------------- validation


def test_poll_seconds_zero_rejected():
    with pytest.raises(ValueError, match="JUMPCLOUD_POLL_SECONDS.*greater than 0"):
        _load({"JUMPCLOUD_POLL_SECONDS": "0"})


def test_poll_seconds_negative_rejected():
    with pytest.raises(ValueError, match="JUMPCLOUD_POLL_SECONDS"):
        _load({"JUMPCLOUD_POLL_SECONDS": "-5"})


def test_poll_seconds_non_numeric_names_variable():
    with pytest.raises(ValueError, match="JUMPCLOUD_POLL_SECONDS.*'abc'"):
        _load({"JUMPCLOUD_POLL_SECONDS": "abc"})


def test_page_limit_non_numeric_names_variable():
    with pytest.raises(ValueError, match="JUMPCLOUD_PAGE_LIMIT"):
        _load({"JUMPCLOUD_PAGE_LIMIT": "lots"})


def test_lookback_non_numeric_names_variable():
    with pytest.raises(ValueError, match="JUMPCLOUD_LOOKBACK_MINUTES"):
        _load({"JUMPCLOUD_LOOKBACK_MINUTES": "x"})


def test_page_limit_clamped_high(caplog):
    with caplog.at_level(logging.WARNING):
        s = _load({"JUMPCLOUD_PAGE_LIMIT": "20000"})
    assert s.page_limit == 10_000
    assert any("clamping" in r.message for r in caplog.records)


def test_page_limit_clamped_low(caplog):
    with caplog.at_level(logging.WARNING):
        s = _load({"JUMPCLOUD_PAGE_LIMIT": "0"})
    assert s.page_limit == 1


def test_page_limit_in_range_no_warning(caplog):
    with caplog.at_level(logging.WARNING):
        s = _load({"JUMPCLOUD_PAGE_LIMIT": "500"})
    assert s.page_limit == 500
    assert not any("clamping" in r.message for r in caplog.records)


def test_unknown_service_warns(caplog):
    with caplog.at_level(logging.WARNING):
        s = _load({"JUMPCLOUD_SERVICES": "directory,frobnicator"})
    assert s.services == ["directory", "frobnicator"]
    warnings = [r.message for r in caplog.records if "frobnicator" in r.getMessage()]
    assert warnings, "expected a warning naming the unknown service"


def test_known_services_no_warning(caplog):
    with caplog.at_level(logging.WARNING):
        _load({"JUMPCLOUD_SERVICES": "directory,sso,mdm,password_manager"})
    assert not any("Unknown" in r.getMessage() for r in caplog.records)


# ------------------------------------------------------- Doppler fallback


def test_doppler_http_token_success():
    """Method 1: DOPPLER_TOKEN present and HTTP API succeeds — no CLI call."""
    resp = MagicMock(status_code=200)
    resp.json.return_value = {"JUMPCLOUD_API_KEY": "from-http"}
    with patch.dict(os.environ, {"DOPPLER_TOKEN": "dp.st.x"}, clear=True), patch(
        "jumpcloud_wazuh_bridge.config._requests.get", return_value=resp
    ) as get, patch("jumpcloud_wazuh_bridge.config.subprocess.run") as run:
        secrets = _doppler_secrets()
    assert secrets == {"JUMPCLOUD_API_KEY": "from-http"}
    get.assert_called_once()
    run.assert_not_called()


def test_doppler_http_failure_falls_back_to_cli():
    """Method 1 fails (non-200) → method 2 (CLI) is tried and wins."""
    resp = MagicMock(status_code=401)
    cli = MagicMock(returncode=0, stdout=json.dumps({"JUMPCLOUD_API_KEY": "from-cli"}))
    with patch.dict(os.environ, {"DOPPLER_TOKEN": "dp.st.x"}, clear=True), patch(
        "jumpcloud_wazuh_bridge.config._requests.get", return_value=resp
    ), patch("jumpcloud_wazuh_bridge.config.subprocess.run", return_value=cli):
        secrets = _doppler_secrets()
    assert secrets == {"JUMPCLOUD_API_KEY": "from-cli"}


def test_doppler_no_token_cli_success():
    """No DOPPLER_TOKEN → HTTP skipped, CLI used directly."""
    cli = MagicMock(returncode=0, stdout=json.dumps({"K": "v"}))
    with patch.dict(os.environ, {}, clear=True), patch(
        "jumpcloud_wazuh_bridge.config._requests.get"
    ) as get, patch("jumpcloud_wazuh_bridge.config.subprocess.run", return_value=cli):
        secrets = _doppler_secrets()
    assert secrets == {"K": "v"}
    get.assert_not_called()


def test_doppler_all_paths_fail_returns_empty():
    """HTTP error + CLI missing → empty dict, so env vars take over."""
    with patch.dict(os.environ, {"DOPPLER_TOKEN": "dp.st.x"}, clear=True), patch(
        "jumpcloud_wazuh_bridge.config._requests.get",
        side_effect=requests.RequestException("boom"),
    ), patch(
        "jumpcloud_wazuh_bridge.config.subprocess.run",
        side_effect=FileNotFoundError,
    ):
        assert _doppler_secrets() == {}


def test_doppler_cli_timeout_returns_empty():
    with patch.dict(os.environ, {}, clear=True), patch(
        "jumpcloud_wazuh_bridge.config.subprocess.run",
        side_effect=subprocess.TimeoutExpired(cmd="doppler", timeout=10),
    ):
        assert _doppler_secrets() == {}


def test_doppler_empty_falls_back_to_env():
    """End-to-end: Doppler returns nothing, env var is used."""
    s = _load({"JUMPCLOUD_API_KEY": "env-key"})
    assert s.api_key == "env-key"
