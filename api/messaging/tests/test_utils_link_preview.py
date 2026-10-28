"""
test_utils_link_preview.py
===========================
Full coverage for messaging/utils/link_preview.py
Functions: extract_urls, fetch_link_preview, check_safe_browsing
Place in: messaging/tests/test_utils_link_preview.py
"""
from __future__ import annotations
import socket
from unittest.mock import patch, MagicMock
from django.test import TestCase, override_settings
from ..utils.link_preview import extract_urls, fetch_link_preview, check_safe_browsing, _is_unsafe_host


def _fake_getaddrinfo(ip: str):
    """Build a return value shaped like socket.getaddrinfo()'s real output."""
    return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, 0))]


class TestExtractUrls(TestCase):
    def test_extracts_single_https_url(self):
        urls = extract_urls("Check this out https://example.com")
        self.assertIn("https://example.com", urls)

    def test_extracts_single_http_url(self):
        urls = extract_urls("Visit http://example.com for more info")
        self.assertIn("http://example.com", urls)

    def test_extracts_multiple_urls(self):
        text = "Go to https://one.com and https://two.com and https://three.com"
        urls = extract_urls(text)
        self.assertGreaterEqual(len(urls), 2)

    def test_deduplicates_same_url(self):
        text = "https://example.com and https://example.com again"
        urls = extract_urls(text)
        self.assertEqual(urls.count("https://example.com"), 1)

    def test_caps_at_5_urls(self):
        links = " ".join(f"https://site{i}.com" for i in range(10))
        urls = extract_urls(links)
        self.assertLessEqual(len(urls), 5)

    def test_returns_empty_for_no_urls(self):
        urls = extract_urls("Just plain text, no links here!")
        self.assertEqual(urls, [])

    def test_returns_empty_for_empty_string(self):
        urls = extract_urls("")
        self.assertEqual(urls, [])

    def test_returns_empty_for_none(self):
        urls = extract_urls(None)
        self.assertEqual(urls, [])

    def test_ignores_partial_urls(self):
        urls = extract_urls("not a url: ftp://example.com or just example.com")
        self.assertEqual(urls, [])

    def test_handles_url_with_path_and_query(self):
        text = "See https://example.com/path?query=value&other=123 for details"
        urls = extract_urls(text)
        self.assertGreaterEqual(len(urls), 1)
        self.assertTrue(any("example.com" in u for u in urls))

    def test_handles_url_with_fragment(self):
        urls = extract_urls("Go to https://docs.example.com/guide#section-2 now")
        self.assertGreaterEqual(len(urls), 1)


class TestFetchLinkPreview(TestCase):
    def setUp(self):
        # Default: hostnames resolve to a public IP, so tests that only
        # care about HTML-parsing behavior don't need their own DNS mock.
        # Tests that specifically exercise the SSRF check override this.
        patcher = patch("messaging.utils.link_preview.socket.getaddrinfo")
        self.mock_getaddrinfo = patcher.start()
        self.mock_getaddrinfo.return_value = _fake_getaddrinfo("93.184.216.34")
        self.addCleanup(patcher.stop)

    def test_blocked_domain_returns_unsafe(self):
        result = fetch_link_preview("http://localhost/secret")
        self.assertFalse(result.get("is_safe", True))

    def test_127_0_0_1_blocked(self):
        result = fetch_link_preview("http://127.0.0.1/admin")
        self.assertFalse(result.get("is_safe", True))

    def test_127_0_0_1_with_port_still_blocked(self):
        """
        Regression test (Part 6 SSRF audit): the old blocklist checked
        parsed.netloc, which includes the port ("127.0.0.1:9200" != the
        blocklist's "127.0.0.1"), so appending any port bypassed it
        entirely. This must stay blocked regardless of port.
        """
        result = fetch_link_preview("http://127.0.0.1:9200/_cluster/health")
        self.assertFalse(result.get("is_safe", True))

    def test_localhost_with_port_still_blocked(self):
        result = fetch_link_preview("http://localhost:8000/internal")
        self.assertFalse(result.get("is_safe", True))

    def test_other_loopback_addresses_blocked(self):
        """127.0.0.0/8 is entirely loopback, not just 127.0.0.1."""
        result = fetch_link_preview("http://127.5.5.5/")
        self.assertFalse(result.get("is_safe", True))

    def test_private_rfc1918_ip_blocked(self):
        for host in ("http://10.0.0.5/", "http://172.16.0.1/", "http://192.168.1.1/"):
            with self.subTest(host=host):
                result = fetch_link_preview(host)
                self.assertFalse(result.get("is_safe", True))

    def test_cloud_metadata_endpoint_blocked(self):
        """169.254.169.254 is the AWS/GCP/Azure instance metadata IP - a
        classic SSRF target for stealing cloud IAM credentials."""
        result = fetch_link_preview("http://169.254.169.254/latest/meta-data/")
        self.assertFalse(result.get("is_safe", True))

    def test_ipv6_loopback_blocked(self):
        result = fetch_link_preview("http://[::1]/admin")
        self.assertFalse(result.get("is_safe", True))

    def test_hostname_resolving_to_private_ip_blocked(self):
        """A public-looking hostname that resolves to a private IP (the
        DNS-side of SSRF, as opposed to a literal IP in the URL) must
        still be blocked - the check has to inspect the resolved address,
        not just pattern-match the URL string."""
        self.mock_getaddrinfo.return_value = _fake_getaddrinfo("192.168.50.50")
        result = fetch_link_preview("http://internal.example.com/")
        self.assertFalse(result.get("is_safe", True))

    def test_unresolvable_hostname_fails_closed(self):
        self.mock_getaddrinfo.side_effect = socket.gaierror("Name or service not known")
        result = fetch_link_preview("http://this-does-not-resolve.example/")
        self.assertFalse(result.get("is_safe", True))

    def test_non_http_scheme_blocked(self):
        result = fetch_link_preview("ftp://files.example.com/file.zip")
        self.assertFalse(result.get("is_safe", True))

    @patch("messaging.utils.link_preview.requests")
    def test_returns_og_metadata_on_success(self, mock_requests):
        html = """
        <html>
        <head>
          <meta property="og:title" content="Test Title"/>
          <meta property="og:description" content="Test description for preview"/>
          <meta property="og:image" content="https://example.com/image.jpg"/>
          <meta property="og:site_name" content="Example"/>
        </head>
        <body><h1>Hello</h1></body>
        </html>
        """
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.headers = {"Content-Type": "text/html; charset=utf-8"}
        mock_resp.text = html
        mock_resp.status_code = 200
        mock_requests.get.return_value = mock_resp
        result = fetch_link_preview("https://example.com/article")
        self.assertEqual(result["title"], "Test Title")
        self.assertEqual(result["description"], "Test description for preview")
        self.assertEqual(result["image_url"], "https://example.com/image.jpg")
        self.assertEqual(result["site_name"], "Example")
        self.assertTrue(result["is_safe"])

    @patch("messaging.utils.link_preview.requests")
    def test_falls_back_to_title_tag(self, mock_requests):
        html = "<html><head><title>Fallback Title</title></head><body></body></html>"
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.headers = {"Content-Type": "text/html"}
        mock_resp.text = html
        mock_requests.get.return_value = mock_resp
        result = fetch_link_preview("https://example.com")
        self.assertEqual(result["title"], "Fallback Title")

    @patch("messaging.utils.link_preview.requests")
    def test_falls_back_to_twitter_cards(self, mock_requests):
        html = """
        <html><head>
          <meta name="twitter:title" content="Twitter Title"/>
          <meta name="twitter:description" content="Twitter Desc"/>
        </head></html>
        """
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.headers = {"Content-Type": "text/html"}
        mock_resp.text = html
        mock_requests.get.return_value = mock_resp
        result = fetch_link_preview("https://example.com")
        self.assertEqual(result["title"], "Twitter Title")

    @patch("messaging.utils.link_preview.requests")
    def test_non_html_content_type_returns_early(self, mock_requests):
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.headers = {"Content-Type": "application/pdf"}
        mock_requests.get.return_value = mock_resp
        result = fetch_link_preview("https://example.com/file.pdf")
        self.assertIn("content_type", result)
        self.assertEqual(result["content_type"], "application/pdf")

    @patch("messaging.utils.link_preview.requests")
    def test_timeout_returns_error_info(self, mock_requests):
        import requests as req_lib
        mock_requests.get.side_effect = req_lib.exceptions.Timeout()
        mock_requests.exceptions = req_lib.exceptions
        result = fetch_link_preview("https://slow.example.com")
        self.assertIn("fetch_error", result)
        self.assertEqual(result["fetch_error"], "timeout")

    @patch("messaging.utils.link_preview.requests")
    def test_ssl_error_marks_unsafe(self, mock_requests):
        import requests as req_lib
        mock_requests.get.side_effect = req_lib.exceptions.SSLError()
        mock_requests.exceptions = req_lib.exceptions
        result = fetch_link_preview("https://bad-ssl.example.com")
        self.assertFalse(result["is_safe"])

    @patch("messaging.utils.link_preview.requests")
    def test_request_exception_returns_error(self, mock_requests):
        import requests as req_lib
        mock_requests.get.side_effect = req_lib.exceptions.RequestException("connection error")
        mock_requests.exceptions = req_lib.exceptions
        result = fetch_link_preview("https://broken.example.com")
        self.assertIn("fetch_error", result)

    @patch("messaging.utils.link_preview.requests")
    def test_domain_extracted_correctly(self, mock_requests):
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.headers = {"Content-Type": "text/html"}
        mock_resp.text = "<html><head><title>T</title></head></html>"
        mock_requests.get.return_value = mock_resp
        result = fetch_link_preview("https://www.example.com/path")
        self.assertEqual(result["domain"], "example.com")

    @patch("messaging.utils.link_preview.requests")
    def test_favicon_extracted(self, mock_requests):
        html = """
        <html><head>
          <link rel="icon" href="/favicon.ico"/>
          <title>T</title>
        </head></html>
        """
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.headers = {"Content-Type": "text/html"}
        mock_resp.text = html
        mock_requests.get.return_value = mock_resp
        result = fetch_link_preview("https://example.com")
        self.assertIsNotNone(result.get("favicon_url"))

    @patch("messaging.utils.link_preview.requests")
    def test_favicon_absolute_url_used_as_is(self, mock_requests):
        html = """
        <html><head>
          <link rel="shortcut icon" href="https://cdn.example.com/icon.png"/>
          <title>T</title>
        </head></html>
        """
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.headers = {"Content-Type": "text/html"}
        mock_resp.text = html
        mock_requests.get.return_value = mock_resp
        result = fetch_link_preview("https://example.com")
        self.assertEqual(result["favicon_url"], "https://cdn.example.com/icon.png")

    @patch("messaging.utils.link_preview.requests")
    def test_favicon_protocol_relative_url_gets_https_prefix(self, mock_requests):
        html = """
        <html><head>
          <link rel="icon" href="//cdn.example.com/icon.png"/>
          <title>T</title>
        </head></html>
        """
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.headers = {"Content-Type": "text/html"}
        mock_resp.text = html
        mock_requests.get.return_value = mock_resp
        result = fetch_link_preview("https://example.com")
        self.assertEqual(result["favicon_url"], "https://cdn.example.com/icon.png")

    @patch("messaging.utils.link_preview.requests")
    def test_unexpected_exception_returns_error_info(self, mock_requests):
        import requests as req_lib
        mock_requests.exceptions = req_lib.exceptions
        mock_requests.get.side_effect = ValueError("something unexpected broke")
        result = fetch_link_preview("https://example.com")
        self.assertTrue(result["is_safe"])
        self.assertIn("something unexpected broke", result["fetch_error"])


class TestIsUnsafeHost(TestCase):
    def test_empty_hostname_is_unsafe(self):
        self.assertTrue(_is_unsafe_host(""))
        self.assertTrue(_is_unsafe_host(None))

    def test_localhost_is_unsafe(self):
        self.assertTrue(_is_unsafe_host("localhost"))
        self.assertTrue(_is_unsafe_host("LOCALHOST"))

    def test_literal_public_ip_is_safe(self):
        self.assertFalse(_is_unsafe_host("8.8.8.8"))

    def test_literal_private_ip_is_unsafe(self):
        self.assertTrue(_is_unsafe_host("10.1.2.3"))
        self.assertTrue(_is_unsafe_host("172.31.0.1"))
        self.assertTrue(_is_unsafe_host("192.168.0.1"))

    def test_literal_link_local_ip_is_unsafe(self):
        self.assertTrue(_is_unsafe_host("169.254.169.254"))

    @patch("messaging.utils.link_preview.socket.getaddrinfo")
    def test_hostname_resolving_to_public_ip_is_safe(self, mock_getaddrinfo):
        mock_getaddrinfo.return_value = _fake_getaddrinfo("93.184.216.34")
        self.assertFalse(_is_unsafe_host("example.com"))

    @patch("messaging.utils.link_preview.socket.getaddrinfo")
    def test_hostname_resolving_to_private_ip_is_unsafe(self, mock_getaddrinfo):
        mock_getaddrinfo.return_value = _fake_getaddrinfo("10.0.0.1")
        self.assertTrue(_is_unsafe_host("sneaky.example.com"))

    @patch("messaging.utils.link_preview.socket.getaddrinfo")
    def test_dns_failure_is_unsafe(self, mock_getaddrinfo):
        mock_getaddrinfo.side_effect = socket.gaierror("nope")
        self.assertTrue(_is_unsafe_host("does-not-resolve.example"))

    @patch("messaging.utils.link_preview.socket.getaddrinfo")
    def test_empty_resolution_result_is_unsafe(self, mock_getaddrinfo):
        mock_getaddrinfo.return_value = []
        self.assertTrue(_is_unsafe_host("weird.example"))


class TestCheckSafeBrowsing(TestCase):
    @override_settings(GOOGLE_SAFE_BROWSING_KEY=None)
    def test_returns_true_when_not_configured(self):
        result = check_safe_browsing("https://example.com")
        self.assertTrue(result)

    @override_settings(GOOGLE_SAFE_BROWSING_KEY="fake-api-key")
    @patch("messaging.utils.link_preview.requests")
    def test_returns_true_when_no_threats_found(self, mock_requests):
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {"matches": []}
        mock_requests.post.return_value = mock_resp
        result = check_safe_browsing("https://safe.example.com")
        self.assertTrue(result)

    @override_settings(GOOGLE_SAFE_BROWSING_KEY="fake-api-key")
    @patch("messaging.utils.link_preview.requests")
    def test_returns_false_when_malware_detected(self, mock_requests):
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {
            "matches": [{"threatType": "MALWARE", "platformType": "ANY_PLATFORM"}]
        }
        mock_requests.post.return_value = mock_resp
        result = check_safe_browsing("https://malware.example.com")
        self.assertFalse(result)

    @override_settings(GOOGLE_SAFE_BROWSING_KEY="fake-api-key")
    @patch("messaging.utils.link_preview.requests")
    def test_returns_true_on_request_exception(self, mock_requests):
        mock_requests.post.side_effect = Exception("API error")
        result = check_safe_browsing("https://example.com")
        self.assertTrue(result)

    @override_settings(GOOGLE_SAFE_BROWSING_KEY="fake-api-key")
    @patch("messaging.utils.link_preview.requests")
    def test_request_includes_correct_threat_types(self, mock_requests):
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {"matches": []}
        mock_requests.post.return_value = mock_resp
        check_safe_browsing("https://example.com")
        payload = mock_requests.post.call_args[1]["json"]
        threat_types = payload["threatInfo"]["threatTypes"]
        self.assertIn("MALWARE", threat_types)
        self.assertIn("SOCIAL_ENGINEERING", threat_types)
