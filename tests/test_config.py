import os
from unittest.mock import patch

from jumpcloud_wazuh_bridge.config import load_settings


def test_load_defaults():
    """Settings fall back to defaults when no env vars set."""
    with patch.dict(os.environ, {}, clear=True), patch(
        "jumpcloud_wazuh_bridge.config._doppler_secrets", return_value={}
    ):
        s = load_settings()
        assert s.api_key == ""
        assert s.base_url == "https://api.jumpcloud.com"
        assert s.poll_seconds == 300
        assert s.services == ["all"]
        assert s.page_limit == 1000


def test_load_from_env():
    env = {
        "JUMPCLOUD_API_KEY": "test-key",
        "JUMPCLOUD_ORG_ID": "org-123",
        "JUMPCLOUD_SERVICES": "directory,sso,radius",
        "JUMPCLOUD_POLL_SECONDS": "60",
    }
    with patch.dict(os.environ, env, clear=True), patch(
        "jumpcloud_wazuh_bridge.config._doppler_secrets", return_value={}
    ):
        s = load_settings()
        assert s.api_key == "test-key"
        assert s.org_id == "org-123"
        assert s.services == ["directory", "sso", "radius"]
        assert s.poll_seconds == 60


def test_services_stripped_and_empties_dropped():
    env = {"JUMPCLOUD_SERVICES": " directory , sso ,,"}
    with patch.dict(os.environ, env, clear=True), patch(
        "jumpcloud_wazuh_bridge.config._doppler_secrets", return_value={}
    ):
        s = load_settings()
        assert s.services == ["directory", "sso"]


def test_services_empty_string_yields_empty_list():
    env = {"JUMPCLOUD_SERVICES": ""}
    with patch.dict(os.environ, env, clear=True), patch(
        "jumpcloud_wazuh_bridge.config._doppler_secrets", return_value={}
    ):
        s = load_settings()
        assert s.services == []
