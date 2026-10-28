"""
verify_postback_config.py – Management command to test all network configurations.

This command provides comprehensive validation of postback network configurations
including webhook testing, signature validation, and integrity checks.
"""
import json
import logging
import hashlib
import hmac
from datetime import datetime, timedelta
from urllib.parse import urlencode

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.test import RequestFactory

from api.postback.models import NetworkPostbackConfig, PostbackLog
from api.postback.choices import ValidatorStatus, SignatureAlgorithm
from api.postback.utils.signature_validator import validate_full_request, generate_signature
from api.postback.utils.ip_checker import extract_client_ip, is_ip_in_whitelist

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """Management command to verify postback configurations."""

    help = "Test and validate all network postback configurations"

    def add_arguments(self, parser):
        """Add command line arguments."""
        parser.add_argument(
            '--network',
            type=str,
            help='Test specific network by key (optional, tests all if not provided)'
        )
        parser.add_argument(
            '--test-webhook',
            action='store_true',
            help='Perform actual webhook test calls (dry run by default)'
        )
        parser.add_argument(
            '--test-payload',
            type=str,
            help='Custom JSON payload for webhook testing'
        )
        parser.add_argument(
            '--skip-inactive',
            action='store_true',
            help='Skip inactive networks'
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Show detailed verification results'
        )
        parser.add_argument(
            '--output-format',
            type=str,
            choices=['table', 'json'],
            default='table',
            help='Output format: table or json (default: table)'
        )
        parser.add_argument(
            '--check-integrity',
            action='store_true',
            help='Verify integrity hashes of all configurations'
        )
        parser.add_argument(
            '--test-rate-limits',
            action='store_true',
            help='Test rate limit configurations'
        )
        parser.add_argument(
            '--timeout',
            type=int,
            default=30,
            help='Timeout for webhook tests in seconds (default: 30)'
        )

    def handle(self, *args, **options):
        """Handle the command execution."""
        # Set up logging
        logging.basicConfig(level=logging.INFO)
        
        # Get networks to test
        networks = self._get_networks(options)
        
        if not networks:
            self.stdout.write(
                self.style.WARNING("No networks found matching the criteria.")
            )
            return
        
        self.stdout.write(f"Testing {len(networks)} network configurations...")
        
        # Test each network
        results = []
        for network in networks:
            result = self._verify_network(network, options)
            results.append(result)
        
        # Output results
        self._output_results(results, options)
        
        # Summary
        self._print_summary(results)

    def _get_networks(self, options):
        """Get networks to test based on options."""
        queryset = NetworkPostbackConfig.objects.all()
        
        # Filter by network key
        if options['network']:
            queryset = queryset.filter(network_key=options['network'])
        
        # Skip inactive networks
        if options['skip_inactive']:
            queryset = queryset.filter(status=ValidatorStatus.ACTIVE)
        
        return list(queryset.order_by('network_key'))

    def _verify_network(self, network, options):
        """Verify a single network configuration."""
        result = {
            'network_key': network.network_key,
            'network_name': network.name,
            'status': network.get_status_display(),
            'tests': {},
            'overall_status': 'PASS',
            'issues': []
        }
        
        # Basic configuration tests
        self._test_basic_config(network, result)
        
        # Secret key tests
        self._test_secret_key(network, result)
        
        # Required fields tests
        self._test_required_fields(network, result)
        
        # IP whitelist tests
        self._test_ip_whitelist(network, result)
        
        # Signature algorithm tests
        self._test_signature_algorithm(network, result)
        
        # Rate limit tests
        if options['test_rate_limits']:
            self._test_rate_limits(network, result)
        
        # Integrity hash tests
        if options['check_integrity']:
            self._test_integrity_hash(network, result)
        
        # Webhook tests
        if options['test_webhook']:
            self._test_webhook_endpoint(network, result, options)
        
        # Determine overall status
        failed_tests = [test for test in result['tests'].values() if test['status'] == 'FAIL']
        if failed_tests:
            result['overall_status'] = 'FAIL'
            result['issues'] = [test['message'] for test in failed_tests]
        
        return result

    def _test_basic_config(self, network, result):
        """Test basic network configuration."""
        test_result = {'status': 'PASS', 'message': '', 'details': {}}
        
        # Check network key
        if not network.network_key:
            test_result['status'] = 'FAIL'
            test_result['message'] = 'Network key is required'
        else:
            test_result['details']['network_key'] = network.network_key
        
        # Check name
        if not network.name:
            test_result['status'] = 'FAIL'
            test_result['message'] = 'Network name is required'
        
        # Check status
        if network.status not in [ValidatorStatus.ACTIVE, ValidatorStatus.INACTIVE]:
            test_result['status'] = 'FAIL'
            test_result['message'] = f'Invalid status: {network.status}'
        
        test_result['details']['name'] = network.name
        test_result['details']['status'] = network.get_status_display()
        
        result['tests']['basic_config'] = test_result

    def _test_secret_key(self, network, result):
        """Test secret key configuration."""
        test_result = {'status': 'PASS', 'message': '', 'details': {}}
        
        if not network.secret_key:
            test_result['status'] = 'FAIL'
            test_result['message'] = 'Secret key is required'
            test_result['details']['secret_key'] = 'MISSING'
        else:
            test_result['details']['secret_key'] = 'PRESENT'
            test_result['details']['secret_key_length'] = len(network.secret_key)
            
            # Check key strength
            if len(network.secret_key) < 16:
                test_result['status'] = 'WARN'
                test_result['message'] = 'Secret key should be at least 16 characters'
            
            # Check for common weak keys
            weak_keys = ['secret', 'password', 'key', 'test', '123456']
            if network.secret_key.lower() in weak_keys:
                test_result['status'] = 'FAIL'
                test_result['message'] = 'Secret key is too weak/common'
        
        result['tests']['secret_key'] = test_result

    def _test_required_fields(self, network, result):
        """Test required fields configuration."""
        test_result = {'status': 'PASS', 'message': '', 'details': {}}
        
        if not network.required_fields:
            test_result['status'] = 'WARN'
            test_result['message'] = 'No required fields configured'
            test_result['details']['required_fields'] = []
        else:
            if not isinstance(network.required_fields, list):
                test_result['status'] = 'FAIL'
                test_result['message'] = 'Required fields must be a list'
            else:
                test_result['details']['required_fields'] = network.required_fields
                test_result['details']['field_count'] = len(network.required_fields)
                
                # Check for common required fields
                common_fields = ['lead_id', 'offer_id', 'payout']
                missing_common = [f for f in common_fields if f not in network.required_fields]
                if missing_common:
                    test_result['status'] = 'WARN'
                    test_result['message'] = f'Missing common fields: {", ".join(missing_common)}'
                    test_result['details']['missing_common_fields'] = missing_common
        
        result['tests']['required_fields'] = test_result

    def _test_ip_whitelist(self, network, result):
        """Test IP whitelist configuration."""
        test_result = {'status': 'PASS', 'message': '', 'details': {}}
        
        if not network.ip_whitelist:
            test_result['status'] = 'WARN'
            test_result['message'] = 'No IP whitelist configured (security risk)'
            test_result['details']['whitelist_type'] = 'NONE'
        else:
            if not isinstance(network.ip_whitelist, list):
                test_result['status'] = 'FAIL'
                test_result['message'] = 'IP whitelist must be a list'
            else:
                test_result['details']['whitelist_type'] = 'LIST'
                test_result['details']['whitelist_count'] = len(network.ip_whitelist)
                
                # Validate IP addresses
                invalid_ips = []
                valid_ips = []
                
                for ip_entry in network.ip_whitelist:
                    try:
                        if is_ip_in_whitelist('127.0.0.1', [ip_entry]):
                            valid_ips.append(ip_entry)
                        else:
                            invalid_ips.append(ip_entry)
                    except Exception:
                        invalid_ips.append(ip_entry)
                
                if invalid_ips:
                    test_result['status'] = 'FAIL'
                    test_result['message'] = f'Invalid IP addresses: {", ".join(invalid_ips)}'
                    test_result['details']['invalid_ips'] = invalid_ips
                
                test_result['details']['valid_ips'] = valid_ips
                test_result['details']['invalid_ips'] = invalid_ips
        
        result['tests']['ip_whitelist'] = test_result

    def _test_signature_algorithm(self, network, result):
        """Test signature algorithm configuration."""
        test_result = {'status': 'PASS', 'message': '', 'details': {}}
        
        if not network.signature_algorithm:
            test_result['status'] = 'FAIL'
            test_result['message'] = 'Signature algorithm is required'
            test_result['details']['algorithm'] = 'MISSING'
        else:
            test_result['details']['algorithm'] = network.signature_algorithm.value
            
            # Check algorithm support
            if network.signature_algorithm == SignatureAlgorithm.NONE:
                test_result['status'] = 'WARN'
                test_result['message'] = 'No signature verification (security risk)'
            elif network.signature_algorithm not in [SignatureAlgorithm.HMAC_SHA256, SignatureAlgorithm.HMAC_SHA1]:
                test_result['status'] = 'WARN'
                test_result['message'] = f'Algorithm {network.signature_algorithm.value} may not be fully supported'
        
        result['tests']['signature_algorithm'] = test_result

    def _test_rate_limits(self, network, result):
        """Test rate limit configuration."""
        from api.postback.models import PostbackRateLimit
        
        test_result = {'status': 'PASS', 'message': '', 'details': {}}
        
        rate_limits = PostbackRateLimit.objects.filter(network=network)
        
        if not rate_limits.exists():
            test_result['status'] = 'WARN'
            test_result['message'] = 'No rate limits configured'
            test_result['details']['rate_limits'] = []
        else:
            rate_limit_data = []
            for rl in rate_limits:
                rl_data = {
                    'name': rl.name,
                    'max_per_minute': rl.max_per_minute,
                    'max_per_hour': rl.max_per_hour,
                    'max_per_day': rl.max_per_day,
                    'is_active': rl.is_active,
                    'is_blocked': rl.is_blocked
                }
                rate_limit_data.append(rl_data)
                
                # Check for reasonable limits
                if rl.max_per_minute <= 0:
                    test_result['status'] = 'WARN'
                    test_result['message'] = 'Rate limit has invalid values'
            
            test_result['details']['rate_limits'] = rate_limit_data
            test_result['details']['rate_limit_count'] = rate_limits.count()
        
        result['tests']['rate_limits'] = test_result

    def _test_integrity_hash(self, network, result):
        """Test integrity hash of network configuration."""
        test_result = {'status': 'PASS', 'message': '', 'details': {}}
        
        # Generate hash of current configuration
        config_data = {
            'network_key': network.network_key,
            'name': network.name,
            'secret_key': network.secret_key,
            'signature_algorithm': network.signature_algorithm.value,
            'required_fields': network.required_fields,
            'ip_whitelist': network.ip_whitelist,
            'status': network.status.value
        }
        
        config_json = json.dumps(config_data, sort_keys=True)
        current_hash = hashlib.sha256(config_json.encode()).hexdigest()
        
        test_result['details']['current_hash'] = current_hash
        test_result['details']['config_size'] = len(config_json)
        
        # Note: NetworkPostbackConfig doesn't have integrity_hash field
        # This test shows what the hash would be for monitoring purposes
        test_result['message'] = 'Integrity hash generated (network model lacks integrity field)'
        
        result['tests']['integrity_hash'] = test_result

    def _test_webhook_endpoint(self, network, result, options):
        """Test webhook endpoint functionality."""
        test_result = {'status': 'PASS', 'message': '', 'details': {}}
        
        # Create test payload
        if options['test_payload']:
            try:
                test_payload = json.loads(options['test_payload'])
            except json.JSONDecodeError:
                test_result['status'] = 'FAIL'
                test_result['message'] = 'Invalid JSON payload'
                result['tests']['webhook_endpoint'] = test_result
                return
        else:
            test_payload = {
                'lead_id': 'TEST_LEAD_123',
                'offer_id': 'TEST_OFFER_456',
                'payout': '10.50',
                'currency': 'USD'
            }
        
        # Test signature generation
        try:
            payload_bytes = json.dumps(test_payload).encode('utf-8')
            signature = generate_signature(
                network.secret_key,
                payload_bytes,
                network.signature_algorithm
            )
            test_result['details']['signature_generated'] = True
            test_result['details']['signature_length'] = len(signature)
        except Exception as e:
            test_result['status'] = 'FAIL'
            test_result['message'] = f'Signature generation failed: {str(e)}'
            result['tests']['webhook_endpoint'] = test_result
            return
        
        # Test signature validation
        try:
            factory = RequestFactory()
            request = factory.post(
                f'/api/postback/receive/{network.network_key}/',
                data=test_payload,
                content_type='application/json',
                HTTP_X_SIGNATURE=signature,
                HTTP_X_TIMESTAMP=str(int(timezone.now().timestamp())),
                HTTP_X_NONCE='test_nonce'
            )
            
            is_valid = validate_full_request(
                network=network,
                signature=signature,
                timestamp_str=request.META.get('HTTP_X_TIMESTAMP'),
                nonce=request.META.get('HTTP_X_NONCE'),
                body_bytes=request.body,
                path=request.path,
                query_params={}
            )
            
            test_result['details']['signature_validation'] = is_valid
            
            if not is_valid:
                test_result['status'] = 'FAIL'
                test_result['message'] = 'Signature validation failed'
        
        except Exception as e:
            test_result['status'] = 'FAIL'
            test_result['message'] = f'Signature validation error: {str(e)}'
        
        test_result['details']['test_payload'] = test_payload
        test_result['details']['endpoint_path'] = f'/api/postback/receive/{network.network_key}/'
        
        result['tests']['webhook_endpoint'] = test_result

    def _output_results(self, results, options):
        """Output verification results."""
        if options['output_format'] == 'json':
            self._output_json(results, options)
        else:
            self._output_table(results, options)

    def _output_table(self, results, options):
        """Output results in table format."""
        self.stdout.write("\n" + "="*100)
        self.stdout.write("POSTBACK CONFIGURATION VERIFICATION RESULTS")
        self.stdout.write("="*100)
        
        for result in results:
            # Network header
            status_color = self.style.SUCCESS if result['overall_status'] == 'PASS' else self.style.ERROR
            self.stdout.write(
                f"\n{status_color}[{result['overall_status']}] "
                f"{result['network_key']} ({result['network_name']}) - {result['status']}"
            )
            
            # Test results
            for test_name, test_result in result['tests'].items():
                if options['verbose'] or test_result['status'] != 'PASS':
                    test_color = self.style.SUCCESS
                    if test_result['status'] == 'FAIL':
                        test_color = self.style.ERROR
                    elif test_result['status'] == 'WARN':
                        test_color = self.style.WARNING
                    
                    self.stdout.write(
                        f"  {test_color}  {test_name}: {test_result['status']}"
                    )
                    
                    if test_result['message']:
                        self.stdout.write(f"    Message: {test_result['message']}")
                    
                    if options['verbose'] and test_result.get('details'):
                        for key, value in test_result['details'].items():
                            if isinstance(value, list) and len(value) > 3:
                                self.stdout.write(f"    {key}: [{len(value)} items]")
                            else:
                                self.stdout.write(f"    {key}: {value}")
            
            # Issues
            if result['issues']:
                self.stdout.write(f"  {self.style.ERROR}  Issues:")
                for issue in result['issues']:
                    self.stdout.write(f"    - {issue}")

    def _output_json(self, results, options):
        """Output results in JSON format."""
        import json
        
        output_data = {
            'timestamp': timezone.now().isoformat(),
            'total_networks': len(results),
            'results': results
        }
        
        self.stdout.write(json.dumps(output_data, indent=2, default=str))

    def _print_summary(self, results):
        """Print verification summary."""
        total = len(results)
        passed = sum(1 for r in results if r['overall_status'] == 'PASS')
        failed = total - passed
        
        self.stdout.write("\n" + "="*50)
        self.stdout.write("VERIFICATION SUMMARY")
        self.stdout.write("="*50)
        self.stdout.write(f"Total networks: {total}")
        self.stdout.write(f"Passed: {passed}")
        self.stdout.write(f"Failed: {failed}")
        
        if failed > 0:
            self.stdout.write(
                self.style.ERROR(f"\n{failed} network(s) failed verification. "
                "See details above for issues.")
            )
        else:
            self.stdout.write(
                self.style.SUCCESS("\nAll networks passed verification!")
            )
        
        # Test statistics
        test_stats = {}
        for result in results:
            for test_name, test_result in result['tests'].items():
                if test_name not in test_stats:
                    test_stats[test_name] = {'PASS': 0, 'FAIL': 0, 'WARN': 0}
                test_stats[test_name][test_result['status']] += 1
        
        if test_stats:
            self.stdout.write("\nTest Statistics:")
            for test_name, stats in test_stats.items():
                self.stdout.write(f"  {test_name}:")
                for status, count in stats.items():
                    if count > 0:
                        color = self.style.SUCCESS if status == 'PASS' else self.style.ERROR if status == 'FAIL' else self.style.WARNING
                        self.stdout.write(f"    {color}{status}: {count}")
