"""Tests for API Manager."""

import os
from unittest.mock import patch

from src.api_manager import APIManager, SERVICES, mask_key


class TestAPIManager:
    """Test API Manager functionality."""

    def test_init(self):
        mgr = APIManager()
        assert mgr is not None

    def test_get_status(self):
        mgr = APIManager()
        status = mgr.get_status()
        assert "services" in status
        assert "total" in status
        assert "connected" in status
        assert status["total"] == 7

    def test_services_defined(self):
        assert "supabase" in SERVICES
        assert "firebase" in SERVICES
        assert "clickhouse" in SERVICES
        assert "r2" in SERVICES
        assert "redis" in SERVICES
        assert "numerai" in SERVICES
        assert "quantconnect" in SERVICES

    def test_each_service_has_keys(self):
        for svc_id, svc in SERVICES.items():
            assert "name" in svc, f"{svc_id} missing name"
            assert "keys" in svc, f"{svc_id} missing keys"
            assert "key_labels" in svc, f"{svc_id} missing key_labels"
            assert "setup_steps" in svc, f"{svc_id} missing setup_steps"
            assert "signup_url" in svc, f"{svc_id} missing signup_url"
            for key in svc["keys"]:
                assert key in svc["key_labels"], f"{svc_id} key {key} not in labels"

    def test_get_saved_keys_no_env(self):
        mgr = APIManager()
        keys = mgr.get_saved_keys("supabase")
        assert "SUPABASE_URL" in keys
        assert "SUPABASE_KEY" in keys

    @patch.dict(os.environ, {"SUPABASE_URL": "https://test.supabase.co", "SUPABASE_KEY": "test_key"})
    def test_get_saved_keys_with_env(self):
        mgr = APIManager()
        keys = mgr.get_saved_keys("supabase")
        assert keys["SUPABASE_URL"] == "https://test.supabase.co"
        assert keys["SUPABASE_KEY"] == "test_key"

    def test_test_connection_no_keys(self):
        mgr = APIManager()
        result = mgr.test_connection("supabase")
        assert result["connected"] is False
        assert "Missing" in result["message"] or "No keys" in result["message"]

    def test_test_connection_unknown_service(self):
        mgr = APIManager()
        result = mgr.test_connection("nonexistent")
        assert result["connected"] is False

    def test_test_all_no_keys(self):
        mgr = APIManager()
        results = mgr.test_all()
        for svc_id, result in results.items():
            assert "connected" in result
            assert "message" in result


class TestMaskKey:
    """Test key masking utility."""

    def test_mask_empty(self):
        assert mask_key("") == ""

    def test_mask_short(self):
        assert mask_key("abc") == "***"

    def test_mask_long(self):
        masked = mask_key("abcdefghijklmnop")
        assert masked.startswith("abcd")
        assert masked.endswith("mnop")
        assert "*" in masked

    def test_mask_custom_chars(self):
        masked = mask_key("abcdefghijklmnop", show_chars=2)
        assert masked.startswith("ab")
        assert masked.endswith("op")


class TestSaveKeys:
    """Test key persistence."""

    def test_save_keys_creates_env(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        from src import api_manager
        monkeypatch.setattr(api_manager, "ENV_PATH", tmp_path / ".env")

        mgr = APIManager()
        result = mgr.save_keys("supabase", {"SUPABASE_URL": "https://x.supabase.co"})
        assert result is True
        assert (tmp_path / ".env").exists()
        content = (tmp_path / ".env").read_text()
        assert "https://x.supabase.co" in content
