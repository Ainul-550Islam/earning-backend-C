"""Tests for third-party integrations."""
from unittest.mock import patch, MagicMock
from ..integrations.abuseipdb_integration import AbuseIPDBIntegration
from ..integrations.ipqualityscore_integration import IPQualityScoreIntegration


class TestAbuseIPDBIntegration:
    def test_no_api_key_returns_empty(self):
        integration = AbuseIPDBIntegration()
        integration.api_key = None
        result = integration.check("1.2.3.4")
        assert result["abuse_confidence_score"] == 0
        assert "error" in result

    def test_rate_limited_returns_empty(self):
        integration = AbuseIPDBIntegration()
        integration.api_key = "test_key"
        mock_resp = MagicMock()
        mock_resp.status_code = 429
        with patch("requests.get", return_value=mock_resp):
            result = integration.check("5.6.7.8")
            assert result["abuse_confidence_score"] == 0

    def test_successful_response_parsed(self):
        integration = AbuseIPDBIntegration()
        integration.api_key = "test_key"
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "data": {
                "abuseConfidenceScore": 85,
                "totalReports": 42,
                "countryCode": "RU",
                "isp": "Bad ISP",
            }
        }
        with patch("requests.get", return_value=mock_resp):
            result = integration.check("9.9.9.9")
            assert result["abuse_confidence_score"] == 85
            assert result["total_reports"] == 42
            assert result["country_code"] == "RU"


class TestIPQSIntegration:
    def test_no_api_key_returns_empty(self):
        integration = IPQualityScoreIntegration()
        integration.api_key = None
        result = integration.check("1.2.3.4")
        assert result["success"] is False
        assert "error" in result
