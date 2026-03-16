import hashlib
import json
import re
import uuid
from typing import Dict, List, Any, Optional, Tuple
from django.utils import timezone
from datetime import timedelta
import logging
from .BaseDetector import BaseDetector
from django.db.models import Count, Q

logger = logging.getLogger(__name__)

class DeviceFingerprinter(BaseDetector):
    """
    Advanced device fingerprinting and spoofing detection
    Uses canvas, WebGL, audio, and behavioral fingerprinting
    """
    
    def __init__(self, config: Dict = None):
        super().__init__(config)
        
        # Configuration
        self.min_entropy = config.get('min_entropy', 50) if config else 50
        self.spoofing_threshold = config.get('spoofing_threshold', 75) if config else 75
        self.consistency_threshold = config.get('consistency_threshold', 80) if config else 80
        
        # Known browser/device patterns
        self.browser_patterns = {
            'chrome': r'Chrome/(\d+)',
            'firefox': r'Firefox/(\d+)',
            'safari': r'Safari/(\d+)',
            'edge': r'Edg/(\d+)',
            'opera': r'OPR/(\d+)',
        }
        
        # Known bot/automation patterns
        self.bot_patterns = [
            r'headless', r'phantom', r'selenium', r'puppeteer',
            r'playwright', r'crawler', r'spider', r'bot', r'automation',
            r'scrapy', r'curl', r'wget', r'python-requests'
        ]
        
    def get_required_fields(self) -> List[str]:
        return ['user_agent', 'device_data']
    
    def detect(self, data: Dict) -> Dict:
        """
        Detect device spoofing and generate fingerprint
        """
        try:
            user_agent = data.get('user_agent', '')
            device_data = data.get('device_data', {})
            user_id = data.get('user_id')
            session_id = data.get('session_id')
            
            if not self.validate_data(data):
                return self.get_detection_result()
            
            # Generate device fingerprint
            fingerprint = self._generate_device_fingerprint(user_agent, device_data)
            
            # Run detection checks
            checks = [
                self._check_browser_consistency(user_agent, device_data),
                self._check_canvas_fingerprint(device_data),
                self._check_webgl_fingerprint(device_data),
                self._check_audio_fingerprint(device_data),
                self._check_hardware_consistency(device_data),
                self._check_timezone_consistency(device_data, user_id),
                self._check_font_fingerprint(device_data),
                self._check_plugin_fingerprint(device_data),
                self._check_screen_properties(device_data),
                self._check_behavioral_fingerprint(data)
            ]
            
            # Calculate overall score
            self._calculate_device_score(checks, fingerprint)
            
            # Check for spoofing
            spoofing_detected = self._detect_spoofing(checks)
            self.detected_fraud = spoofing_detected
            
            # Calculate confidence
            self.confidence = self._calculate_fingerprint_confidence(fingerprint, checks)
            
            # Add evidence
            self._compile_device_evidence(fingerprint, checks, data)
            
            # Log detection
            self.log_detection(user_id)
            
            result = self.get_detection_result()
            result['fingerprint'] = fingerprint
            result['device_hash'] = self._generate_device_hash(fingerprint)
            
            return result
            
        except Exception as e:
            logger.error(f"Error in DeviceFingerprinter: {str(e)}")
            return {
                'detector': self.detector_name,
                'is_fraud': False,
                'fraud_score': 0,
                'confidence': 0,
                'error': str(e)
            }
    
    def _generate_device_fingerprint(self, user_agent: str, device_data: Dict) -> Dict:
        """
        Generate comprehensive device fingerprint
        """
        fingerprint = {
            'browser': self._extract_browser_info(user_agent),
            'platform': self._extract_platform_info(user_agent),
            'device_type': self._detect_device_type(user_agent, device_data),
            'screen_properties': self._extract_screen_properties(device_data),
            'hardware': self._extract_hardware_info(device_data),
            'timezone': self._extract_timezone_info(device_data),
            'language': self._extract_language_info(device_data),
            'fonts': self._extract_font_info(device_data),
            'plugins': self._extract_plugin_info(device_data),
            'canvas_fingerprint': device_data.get('canvas_hash', ''),
            'webgl_fingerprint': device_data.get('webgl_hash', ''),
            'audio_fingerprint': device_data.get('audio_hash', ''),
            'entropy_score': 0,
            'uniqueness_score': 0
        }
        
        # Calculate entropy (uniqueness)
        fingerprint['entropy_score'] = self._calculate_entropy(fingerprint)
        fingerprint['uniqueness_score'] = self._calculate_uniqueness(fingerprint)
        
        return fingerprint
    
    def _extract_browser_info(self, user_agent: str) -> Dict:
        """Extract browser information from user agent"""
        browser_info = {
            'user_agent': user_agent,
            'name': 'Unknown',
            'version': 'Unknown',
            'engine': 'Unknown',
            'is_mobile': False,
            'is_tablet': False,
            'is_desktop': False
        }
        
        # Detect mobile/tablet
        mobile_pattern = r'(Mobile|Android|iPhone|iPad|iPod|BlackBerry|Windows Phone)'
        tablet_pattern = r'(Tablet|iPad)'
        
        if re.search(mobile_pattern, user_agent, re.IGNORECASE):
            browser_info['is_mobile'] = True
        if re.search(tablet_pattern, user_agent, re.IGNORECASE):
            browser_info['is_tablet'] = True
        
        browser_info['is_desktop'] = not (browser_info['is_mobile'] or browser_info['is_tablet'])
        
        # Detect browser
        for browser, pattern in self.browser_patterns.items():
            match = re.search(pattern, user_agent, re.IGNORECASE)
            if match:
                browser_info['name'] = browser.capitalize()
                browser_info['version'] = match.group(1)
                break
        
        # Detect browser engine
        if 'AppleWebKit' in user_agent:
            browser_info['engine'] = 'WebKit'
        elif 'Gecko' in user_agent:
            browser_info['engine'] = 'Gecko'
        elif 'Trident' in user_agent or 'MSIE' in user_agent:
            browser_info['engine'] = 'Trident'
        elif 'Blink' in user_agent:
            browser_info['engine'] = 'Blink'
        
        return browser_info
    
    def _extract_platform_info(self, user_agent: str) -> Dict:
        """Extract platform/OS information"""
        platform_info = {
            'os': 'Unknown',
            'os_version': 'Unknown',
            'architecture': 'Unknown'
        }
        
        # Windows
        if 'Windows' in user_agent:
            platform_info['os'] = 'Windows'
            win_version = re.search(r'Windows NT (\d+\.\d+)', user_agent)
            if win_version:
                platform_info['os_version'] = win_version.group(1)
        
        # macOS
        elif 'Mac OS X' in user_agent:
            platform_info['os'] = 'macOS'
            mac_version = re.search(r'Mac OS X (\d+[_.]\d+)', user_agent)
            if mac_version:
                platform_info['os_version'] = mac_version.group(1).replace('_', '.')
        
        # Linux
        elif 'Linux' in user_agent:
            platform_info['os'] = 'Linux'
        
        # Android
        elif 'Android' in user_agent:
            platform_info['os'] = 'Android'
            android_version = re.search(r'Android (\d+\.\d+)', user_agent)
            if android_version:
                platform_info['os_version'] = android_version.group(1)
        
        # iOS
        elif 'iPhone OS' in user_agent or 'iPad' in user_agent:
            platform_info['os'] = 'iOS'
            ios_version = re.search(r'OS (\d+[_.]\d+)', user_agent)
            if ios_version:
                platform_info['os_version'] = ios_version.group(1).replace('_', '.')
        
        # Detect architecture
        if 'x64' in user_agent or 'x86_64' in user_agent or 'Win64' in user_agent:
            platform_info['architecture'] = '64-bit'
        elif 'x86' in user_agent or 'i686' in user_agent:
            platform_info['architecture'] = '32-bit'
        elif 'ARM' in user_agent:
            platform_info['architecture'] = 'ARM'
        
        return platform_info
    
    def _detect_device_type(self, user_agent: str, device_data: Dict) -> str:
        """Detect device type"""
        # Check user agent first
        if re.search(r'(Mobile|Android|iPhone)', user_agent, re.IGNORECASE):
            return 'mobile'
        elif re.search(r'(Tablet|iPad)', user_agent, re.IGNORECASE):
            return 'tablet'
        
        # Check device data
        if device_data.get('is_mobile', False):
            return 'mobile'
        elif device_data.get('is_tablet', False):
            return 'tablet'
        
        # Check screen properties
        screen_width = device_data.get('screen_width', 0)
        screen_height = device_data.get('screen_height', 0)
        
        if screen_width > 0 and screen_height > 0:
            if max(screen_width, screen_height) < 800:
                return 'mobile'
            elif max(screen_width, screen_height) < 1400:
                return 'tablet'
        
        return 'desktop'
    
    def _extract_screen_properties(self, device_data: Dict) -> Dict:
        """Extract screen properties"""
        return {
            'width': device_data.get('screen_width', 0),
            'height': device_data.get('screen_height', 0),
            'color_depth': device_data.get('color_depth', 24),
            'pixel_ratio': device_data.get('pixel_ratio', 1.0),
            'orientation': device_data.get('orientation', 'landscape'),
            'available_width': device_data.get('available_width', 0),
            'available_height': device_data.get('available_height', 0)
        }
    
    def _extract_hardware_info(self, device_data: Dict) -> Dict:
        """Extract hardware information"""
        return {
            'cpu_cores': device_data.get('cpu_cores', 0),
            'device_memory': device_data.get('device_memory', 0),
            'max_touch_points': device_data.get('max_touch_points', 0),
            'hardware_concurrency': device_data.get('hardware_concurrency', 0),
            'has_touch_support': device_data.get('has_touch', False),
            'has_gyroscope': device_data.get('has_gyroscope', False),
            'has_accelerometer': device_data.get('has_accelerometer', False)
        }
    
    def _extract_timezone_info(self, device_data: Dict) -> Dict:
        """Extract timezone information"""
        return {
            'timezone': device_data.get('timezone', 'UTC'),
            'timezone_offset': device_data.get('timezone_offset', 0),
            'locale': device_data.get('locale', 'en-US'),
            'system_language': device_data.get('system_language', 'en')
        }
    
    def _extract_language_info(self, device_data: Dict) -> Dict:
        """Extract language information"""
        return {
            'browser_language': device_data.get('language', 'en-US'),
            'languages': device_data.get('languages', ['en-US']),
            'accept_language': device_data.get('accept_language', 'en-US,en;q=0.9')
        }
    
    def _extract_font_info(self, device_data: Dict) -> Dict:
        """Extract font information"""
        fonts = device_data.get('fonts', [])
        return {
            'font_list': fonts,
            'font_count': len(fonts),
            'common_fonts': self._identify_common_fonts(fonts)
        }
    
    def _extract_plugin_info(self, device_data: Dict) -> Dict:
        """Extract plugin information"""
        plugins = device_data.get('plugins', [])
        return {
            'plugin_list': plugins,
            'plugin_count': len(plugins),
            'has_flash': any('flash' in p.lower() for p in plugins),
            'has_java': any('java' in p.lower() for p in plugins),
            'has_pdf': any('pdf' in p.lower() for p in plugins)
        }
    
    def _calculate_entropy(self, fingerprint: Dict) -> float:
        """Calculate entropy (uniqueness) of fingerprint"""
        entropy = 0
        
        # Browser entropy
        browser_name = fingerprint['browser']['name']
        browser_version = fingerprint['browser']['version']
        if browser_name != 'Unknown' and browser_version != 'Unknown':
            entropy += 15
        
        # Platform entropy
        if fingerprint['platform']['os'] != 'Unknown':
            entropy += 10
        
        # Screen entropy
        screen = fingerprint['screen_properties']
        if screen['width'] > 0 and screen['height'] > 0:
            entropy += 20
        
        # Hardware entropy
        hardware = fingerprint['hardware']
        if hardware['cpu_cores'] > 0:
            entropy += 10
        if hardware['device_memory'] > 0:
            entropy += 10
        
        # Timezone entropy
        if fingerprint['timezone']['timezone'] != 'UTC':
            entropy += 5
        
        # Font entropy
        font_count = fingerprint['fonts']['font_count']
        entropy += min(font_count, 30)  # Cap at 30
        
        # Plugin entropy
        plugin_count = fingerprint['plugins']['plugin_count']
        entropy += min(plugin_count, 15)  # Cap at 15
        
        # Canvas/WebGL/Audio entropy
        if fingerprint['canvas_fingerprint']:
            entropy += 20
        if fingerprint['webgl_fingerprint']:
            entropy += 20
        if fingerprint['audio_fingerprint']:
            entropy += 20
        
        return min(entropy, 100)
    
    def _calculate_uniqueness(self, fingerprint: Dict) -> float:
        """Calculate uniqueness score"""
        unique_features = 0
        total_features = 0
        
        # Check each feature for uniqueness
        features_to_check = [
            ('canvas_fingerprint', 3),
            ('webgl_fingerprint', 3),
            ('audio_fingerprint', 2),
            ('fonts', 2),
            ('plugins', 1),
            ('hardware', 2)
        ]
        
        for feature, weight in features_to_check:
            if feature in fingerprint:
                if isinstance(fingerprint[feature], (list, dict)):
                    if len(fingerprint[feature]) > 0:
                        unique_features += weight
                elif fingerprint[feature]:
                    unique_features += weight
                total_features += weight
        
        if total_features > 0:
            return (unique_features / total_features) * 100
        
        return 0
    
    def _check_browser_consistency(self, user_agent: str, device_data: Dict) -> Dict:
        """Check browser consistency"""
        result = {
            'check': 'browser_consistency',
            'issues': [],
            'risk_score': 0
        }
        
        # Check for bot patterns in user agent
        for pattern in self.bot_patterns:
            if re.search(pattern, user_agent, re.IGNORECASE):
                result['issues'].append(f"Bot pattern detected: {pattern}")
                result['risk_score'] += 30
        
        # Check user agent length (suspicious if too short/long)
        ua_length = len(user_agent)
        if ua_length < 20:
            result['issues'].append(f"Suspiciously short user agent: {ua_length} chars")
            result['risk_score'] += 20
        elif ua_length > 500:
            result['issues'].append(f"Suspiciously long user agent: {ua_length} chars")
            result['risk_score'] += 15
        
        # Check for common inconsistencies
        if 'Mozilla' not in user_agent and 'AppleWebKit' not in user_agent:
            result['issues'].append("Missing standard browser identifiers")
            result['risk_score'] += 25
        
        # Check for spoofed browser
        declared_browser = device_data.get('browser', '')
        if declared_browser and declared_browser not in user_agent:
            result['issues'].append(f"Declared browser '{declared_browser}' not in user agent")
            result['risk_score'] += 20
        
        result['risk_score'] = min(100, result['risk_score'])
        
        if result['risk_score'] > 0:
            for issue in result['issues'][:2]:
                self.add_reason(issue, result['risk_score'] // len(result['issues']))
        
        return result
    
    def _check_canvas_fingerprint(self, device_data: Dict) -> Dict:
        """Check canvas fingerprint for anomalies"""
        result = {
            'check': 'canvas_fingerprint',
            'issues': [],
            'risk_score': 0
        }
        
        canvas_hash = device_data.get('canvas_hash', '')
        
        if not canvas_hash:
            result['issues'].append("No canvas fingerprint provided")
            result['risk_score'] += 10
            return result
        
        # Check canvas hash length and pattern
        hash_length = len(canvas_hash)
        
        if hash_length < 10:
            result['issues'].append(f"Suspiciously short canvas hash: {hash_length} chars")
            result['risk_score'] += 25
        elif hash_length > 1000:
            result['issues'].append(f"Suspiciously long canvas hash: {hash_length} chars")
            result['risk_score'] += 20
        
        # Check for common/default canvas hashes
        common_hashes = [
            '00000000000000000000000000000000',
            'ffffffffffffffffffffffffffffffff',
            'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'
        ]
        
        if canvas_hash in common_hashes:
            result['issues'].append("Common/default canvas hash detected")
            result['risk_score'] += 40
        
        # Check entropy of canvas hash
        entropy = self._calculate_string_entropy(canvas_hash)
        if entropy < 2.0:
            result['issues'].append(f"Low entropy canvas hash: {entropy:.2f}")
            result['risk_score'] += 30
        
        result['risk_score'] = min(100, result['risk_score'])
        
        if result['risk_score'] > 0:
            for issue in result['issues'][:2]:
                self.add_reason(issue, result['risk_score'] // len(result['issues']))
        
        return result
    
    def _check_webgl_fingerprint(self, device_data: Dict) -> Dict:
        """Check WebGL fingerprint for anomalies"""
        result = {
            'check': 'webgl_fingerprint',
            'issues': [],
            'risk_score': 0
        }
        
        webgl_hash = device_data.get('webgl_hash', '')
        webgl_info = device_data.get('webgl_info', {})
        
        if not webgl_hash:
            result['issues'].append("No WebGL fingerprint provided")
            result['risk_score'] += 10
            return result
        
        # Check WebGL support consistency
        has_webgl = device_data.get('has_webgl', False)
        if has_webgl and not webgl_hash:
            result['issues'].append("WebGL reported but no fingerprint")
            result['risk_score'] += 20
        elif not has_webgl and webgl_hash:
            result['issues'].append("WebGL fingerprint without WebGL support")
            result['risk_score'] += 30
        
        # Check WebGL renderer/vendor
        renderer = webgl_info.get('renderer', '')
        vendor = webgl_info.get('vendor', '')
        
        if renderer and vendor:
            # Check for virtual GPU indicators
            virtual_gpu_indicators = ['SwiftShader', 'Google SwiftShader', 'VirtualBox', 'VMware', 'Parallels']
            for indicator in virtual_gpu_indicators:
                if indicator in renderer or indicator in vendor:
                    result['issues'].append(f"Virtual/emulated GPU detected: {indicator}")
                    result['risk_score'] += 35
        
        # Check for common WebGL hashes
        if webgl_hash == 'unknown' or webgl_hash == 'null' or len(webgl_hash) < 5:
            result['issues'].append("Invalid WebGL fingerprint")
            result['risk_score'] += 25
        
        result['risk_score'] = min(100, result['risk_score'])
        
        if result['risk_score'] > 0:
            for issue in result['issues'][:2]:
                self.add_reason(issue, result['risk_score'] // len(result['issues']))
        
        return result
    
    def _check_audio_fingerprint(self, device_data: Dict) -> Dict:
        """Check audio fingerprint for anomalies"""
        result = {
            'check': 'audio_fingerprint',
            'issues': [],
            'risk_score': 0
        }
        
        audio_hash = device_data.get('audio_hash', '')
        audio_info = device_data.get('audio_info', {})
        
        if not audio_hash:
            result['issues'].append("No audio fingerprint provided")
            result['risk_score'] += 5
            return result
        
        # Check audio context support
        has_audio = device_data.get('has_audio_context', False)
        if has_audio and not audio_hash:
            result['issues'].append("Audio context reported but no fingerprint")
            result['risk_score'] += 15
        
        # Check audio fingerprint pattern
        if audio_hash == '0' * len(audio_hash) or audio_hash == 'f' * len(audio_hash):
            result['issues'].append("Uniform audio fingerprint (likely spoofed)")
            result['risk_score'] += 40
        
        # Check for common audio fingerprints
        common_audio_hashes = [
            '0000000000000000',
            'ffffffffffffffff',
            '1234567890abcdef'
        ]
        
        if audio_hash in common_audio_hashes:
            result['issues'].append("Common audio fingerprint detected")
            result['risk_score'] += 30
        
        result['risk_score'] = min(100, result['risk_score'])
        
        if result['risk_score'] > 0:
            for issue in result['issues'][:2]:
                self.add_reason(issue, result['risk_score'] // len(result['issues']))
        
        return result
    
    def _check_hardware_consistency(self, device_data: Dict) -> Dict:
        """Check hardware information consistency"""
        result = {
            'check': 'hardware_consistency',
            'issues': [],
            'risk_score': 0
        }
        
        # Check CPU cores consistency
        cpu_cores = device_data.get('cpu_cores', 0)
        hardware_concurrency = device_data.get('hardware_concurrency', 0)
        
        if cpu_cores > 0 and hardware_concurrency > 0:
            if cpu_cores != hardware_concurrency:
                result['issues'].append(f"CPU cores mismatch: {cpu_cores} vs {hardware_concurrency}")
                result['risk_score'] += 20
        
        # Check device memory
        device_memory = device_data.get('device_memory', 0)
        if device_memory > 0:
            # Check for unrealistic memory values
            if device_memory < 1:  # Less than 1GB
                result['issues'].append(f"Unrealistically low device memory: {device_memory}GB")
                result['risk_score'] += 25
            elif device_memory > 128:  # More than 128GB (uncommon for consumer devices)
                result['issues'].append(f"Unrealistically high device memory: {device_memory}GB")
                result['risk_score'] += 20
        
        # Check screen resolution consistency
        screen_width = device_data.get('screen_width', 0)
        screen_height = device_data.get('screen_height', 0)
        available_width = device_data.get('available_width', 0)
        available_height = device_data.get('available_height', 0)
        
        if screen_width > 0 and available_width > 0:
            if available_width > screen_width:
                result['issues'].append(f"Available width ({available_width}) > screen width ({screen_width})")
                result['risk_score'] += 15
        
        # Check for virtual machine indicators
        vm_indicators = device_data.get('vm_indicators', {})
        vm_score = 0
        
        if vm_indicators.get('has_vm_device', False):
            vm_score += 25
        if vm_indicators.get('has_vm_driver', False):
            vm_score += 20
        if vm_indicators.get('has_vm_registry', False):
            vm_score += 15
        
        if vm_score > 0:
            result['issues'].append(f"Virtual machine indicators detected (score: {vm_score})")
            result['risk_score'] += min(vm_score, 40)
        
        result['risk_score'] = min(100, result['risk_score'])
        
        if result['risk_score'] > 0:
            for issue in result['issues'][:2]:
                self.add_reason(issue, result['risk_score'] // len(result['issues']))
        
        return result
    
    def _check_timezone_consistency(self, device_data: Dict, user_id: int = None) -> Dict:
        """Check timezone consistency"""
        result = {
            'check': 'timezone_consistency',
            'issues': [],
            'risk_score': 0
        }
        
        timezone = device_data.get('timezone', '')
        timezone_offset = device_data.get('timezone_offset', 0)
        
        if not timezone:
            return result
        
        # Check for suspicious timezones
        suspicious_timezones = ['UTC', 'GMT', 'Etc/UTC', 'Etc/GMT']
        if timezone in suspicious_timezones:
            result['issues'].append(f"Suspicious timezone: {timezone}")
            result['risk_score'] += 15
        
        # Check timezone offset consistency
        try:
            import pytz
            tz = pytz.timezone(timezone)
            import datetime
            current_offset = tz.utcoffset(datetime.datetime.utcnow()).total_seconds() / 3600
            
            if abs(current_offset - timezone_offset) > 1:
                result['issues'].append(f"Timezone offset mismatch: {timezone_offset} vs calculated {current_offset}")
                result['risk_score'] += 20
        except:
            pass
        
        # Compare with user's historical timezone if available
        if user_id:
            try:
                from ..models import DeviceFingerprint
                historical_tzs = DeviceFingerprint.objects.filter(
                    user_id=user_id
                ).exclude(
                    timezone__isnull=True
                ).values_list('timezone', flat=True).distinct()
                
                if historical_tzs:
                    if timezone not in historical_tzs:
                        result['issues'].append(f"New timezone detected: {timezone}")
                        result['risk_score'] += 15
            except:
                pass
        
        result['risk_score'] = min(100, result['risk_score'])
        
        if result['risk_score'] > 0:
            for issue in result['issues'][:2]:
                self.add_reason(issue, result['risk_score'] // len(result['issues']))
        
        return result
    
    def _check_font_fingerprint(self, device_data: Dict) -> Dict:
        """Check font fingerprint for anomalies"""
        result = {
            'check': 'font_fingerprint',
            'issues': [],
            'risk_score': 0
        }
        
        fonts = device_data.get('fonts', [])
        font_count = len(fonts)
        
        # Check font count
        if font_count == 0:
            result['issues'].append("No fonts detected")
            result['risk_score'] += 10
        elif font_count < 10:
            result['issues'].append(f"Low font count: {font_count}")
            result['risk_score'] += 15
        elif font_count > 200:
            result['issues'].append(f"Unusually high font count: {font_count}")
            result['risk_score'] += 20
        
        # Check for common/default font lists
        common_fonts = self._identify_common_fonts(fonts)
        if common_fonts.get('is_common', False):
            result['issues'].append("Common/default font list detected")
            result['risk_score'] += 25
        
        # Check for system-specific fonts
        system_fonts = self._identify_system_fonts(fonts, device_data)
        if not system_fonts.get('has_system_fonts', True):
            result['issues'].append("Missing system fonts")
            result['risk_score'] += 20
        
        result['risk_score'] = min(100, result['risk_score'])
        
        if result['risk_score'] > 0:
            for issue in result['issues'][:2]:
                self.add_reason(issue, result['risk_score'] // len(result['issues']))
        
        return result
    
    def _check_plugin_fingerprint(self, device_data: Dict) -> Dict:
        """Check plugin fingerprint for anomalies"""
        result = {
            'check': 'plugin_fingerprint',
            'issues': [],
            'risk_score': 0
        }
        
        plugins = device_data.get('plugins', [])
        plugin_count = len(plugins)
        
        # Modern browsers have few or no plugins
        if plugin_count > 10:
            result['issues'].append(f"High plugin count: {plugin_count}")
            result['risk_score'] += 25
        
        # Check for outdated/dangerous plugins
        dangerous_plugins = ['Java', 'Flash', 'Silverlight', 'QuickTime', 'RealPlayer']
        for plugin in plugins:
            for dangerous in dangerous_plugins:
                if dangerous.lower() in plugin.lower():
                    result['issues'].append(f"Outdated/dangerous plugin: {plugin}")
                    result['risk_score'] += 15
        
        # Check for virtual machine plugins
        vm_plugins = ['VMware', 'VirtualBox', 'Parallels']
        for plugin in plugins:
            for vm in vm_plugins:
                if vm.lower() in plugin.lower():
                    result['issues'].append(f"Virtual machine plugin: {plugin}")
                    result['risk_score'] += 30
        
        result['risk_score'] = min(100, result['risk_score'])
        
        if result['risk_score'] > 0:
            for issue in result['issues'][:2]:
                self.add_reason(issue, result['risk_score'] // len(result['issues']))
        
        return result
    
    def _check_screen_properties(self, device_data: Dict) -> Dict:
        """Check screen properties for anomalies"""
        result = {
            'check': 'screen_properties',
            'issues': [],
            'risk_score': 0
        }
        
        screen_width = device_data.get('screen_width', 0)
        screen_height = device_data.get('screen_height', 0)
        pixel_ratio = device_data.get('pixel_ratio', 1.0)
        
        # Check for unrealistic screen dimensions
        if screen_width > 0 and screen_height > 0:
            # Common mobile resolutions
            common_resolutions = [
                (375, 667), (414, 896), (360, 640),  # iPhone
                (768, 1024), (810, 1080), (1280, 800)  # Tablets
            ]
            
            is_common = False
            for w, h in common_resolutions:
                if abs(screen_width - w) < 50 and abs(screen_height - h) < 50:
                    is_common = True
                    break
            
            if not is_common and (screen_width < 200 or screen_height < 200):
                result['issues'].append(f"Unusual screen resolution: {screen_width}x{screen_height}")
                result['risk_score'] += 15
        
        # Check pixel ratio
        if pixel_ratio > 0:
            common_ratios = [1.0, 1.5, 2.0, 2.5, 3.0]
            if pixel_ratio not in common_ratios and pixel_ratio > 3.5:
                result['issues'].append(f"Unusual pixel ratio: {pixel_ratio}")
                result['risk_score'] += 10
        
        result['risk_score'] = min(100, result['risk_score'])
        
        if result['risk_score'] > 0:
            for issue in result['issues'][:2]:
                self.add_reason(issue, result['risk_score'] // len(result['issues']))
        
        return result
    
    def _check_behavioral_fingerprint(self, data: Dict) -> Dict:
        """Check behavioral fingerprinting"""
        result = {
            'check': 'behavioral_fingerprint',
            'issues': [],
            'risk_score': 0
        }
        
        behavioral_data = data.get('behavioral_data', {})
        
        # Check mouse/touch movements
        mouse_data = behavioral_data.get('mouse_movements', [])
        if mouse_data:
            # Analyze movement patterns
            is_robotic = self._detect_robotic_movements(mouse_data)
            if is_robotic:
                result['issues'].append("Robotic mouse movement patterns")
                result['risk_score'] += 30
        
        # Check typing patterns
        typing_data = behavioral_data.get('typing_patterns', {})
        if typing_data:
            typing_speed = typing_data.get('typing_speed', 0)
            if typing_speed > 200:  # Unnaturally fast typing
                result['issues'].append(f"Unnaturally fast typing: {typing_speed} CPM")
                result['risk_score'] += 25
        
        # Check scroll behavior
        scroll_data = behavioral_data.get('scroll_patterns', {})
        if scroll_data:
            is_mechanical = self._detect_mechanical_scrolling(scroll_data)
            if is_mechanical:
                result['issues'].append("Mechanical scrolling patterns")
                result['risk_score'] += 20
        
        result['risk_score'] = min(100, result['risk_score'])
        
        if result['risk_score'] > 0:
            for issue in result['issues'][:2]:
                self.add_reason(issue, result['risk_score'] // len(result['issues']))
        
        return result
    
    def _calculate_device_score(self, checks: List[Dict], fingerprint: Dict):
        """Calculate overall device fraud score"""
        risk_scores = [check.get('risk_score', 0) for check in checks]
        
        if risk_scores:
            # Weighted average with emphasis on certain checks
            weights = {
                'browser_consistency': 1.2,
                'canvas_fingerprint': 1.5,
                'webgl_fingerprint': 1.3,
                'audio_fingerprint': 1.0,
                'hardware_consistency': 1.1,
                'timezone_consistency': 0.8,
                'font_fingerprint': 0.9,
                'plugin_fingerprint': 0.7,
                'screen_properties': 0.6,
                'behavioral_fingerprint': 1.4
            }
            
            weighted_sum = 0
            total_weight = 0
            
            for check in checks:
                check_name = check.get('check', '')
                weight = weights.get(check_name, 1.0)
                risk_score = check.get('risk_score', 0)
                
                weighted_sum += risk_score * weight
                total_weight += weight
            
            if total_weight > 0:
                self.fraud_score = int(weighted_sum / total_weight)
        
        # Adjust based on fingerprint entropy
        entropy = fingerprint.get('entropy_score', 0)
        if entropy < self.min_entropy:
            self.fraud_score = min(100, self.fraud_score + (self.min_entropy - entropy))
    
    def _detect_spoofing(self, checks: List[Dict]) -> bool:
        """Detect device spoofing"""
        high_risk_checks = [check for check in checks if check.get('risk_score', 0) >= 50]
        
        if len(high_risk_checks) >= 2:
            return True
        
        total_risk = sum(check.get('risk_score', 0) for check in checks)
        if total_risk >= self.spoofing_threshold:
            return True
        
        return False
    
    def _calculate_fingerprint_confidence(self, fingerprint: Dict, checks: List[Dict]) -> int:
        """Calculate confidence in fingerprint"""
        confidence_factors = []
        
        # Entropy-based confidence
        entropy = fingerprint.get('entropy_score', 0)
        if entropy >= 70:
            confidence_factors.append(80)
        elif entropy >= 50:
            confidence_factors.append(60)
        else:
            confidence_factors.append(30)
        
        # Consistency-based confidence
        low_risk_checks = len([check for check in checks if check.get('risk_score', 0) < 30])
        if low_risk_checks >= 8:
            confidence_factors.append(70)
        elif low_risk_checks >= 5:
            confidence_factors.append(50)
        else:
            confidence_factors.append(30)
        
        # Feature completeness
        features_present = sum(1 for key in ['canvas_fingerprint', 'webgl_fingerprint', 'audio_fingerprint'] 
                              if fingerprint.get(key))
        if features_present >= 3:
            confidence_factors.append(85)
        elif features_present >= 2:
            confidence_factors.append(65)
        else:
            confidence_factors.append(40)
        
        if confidence_factors:
            return min(100, int(sum(confidence_factors) / len(confidence_factors)))
        
        return 50
    
    def _compile_device_evidence(self, fingerprint: Dict, checks: List[Dict], data: Dict):
        """Compile device evidence"""
        self.add_evidence('fingerprint_summary', {
            'entropy_score': fingerprint.get('entropy_score', 0),
            'uniqueness_score': fingerprint.get('uniqueness_score', 0),
            'device_type': fingerprint.get('device_type', 'unknown'),
            'browser': fingerprint['browser']['name']
        })
        
        self.add_evidence('check_results', {
            check['check']: check['risk_score'] for check in checks
        })
        
        # Add specific high-risk evidence
        for check in checks:
            if check.get('risk_score', 0) >= 30:
                self.add_evidence(f"{check['check']}_details", {
                    'issues': check.get('issues', [])[:3],
                    'risk_score': check['risk_score']
                })
    
    def _generate_device_hash(self, fingerprint: Dict) -> str:
        """Generate unique device hash"""
        fingerprint_str = json.dumps(fingerprint, sort_keys=True)
        return hashlib.sha256(fingerprint_str.encode()).hexdigest()
    
    def _calculate_string_entropy(self, string: str) -> float:
        """Calculate Shannon entropy of a string"""
        import math
        if not string:
            return 0
        
        entropy = 0
        for char in set(string):
            p_x = string.count(char) / len(string)
            entropy += -p_x * math.log2(p_x)
        
        return entropy
    
    def _identify_common_fonts(self, fonts: List[str]) -> Dict:
        """Identify common font patterns"""
        # Common default font lists for different browsers/OS
        common_patterns = {
            'windows_default': ['Arial', 'Times New Roman', 'Courier New', 'Verdana'],
            'mac_default': ['Helvetica', 'Times', 'Courier', 'Geneva'],
            'linux_default': ['DejaVu Sans', 'Liberation Sans', 'FreeSans'],
            'web_safe': ['Arial', 'Helvetica', 'Times New Roman', 'Times', 'Courier New']
        }
        
        result = {
            'is_common': False,
            'pattern_matched': None,
            'match_percentage': 0
        }
        
        font_set = set(f.lower() for f in fonts)
        
        for pattern_name, pattern_fonts in common_patterns.items():
            pattern_set = set(f.lower() for f in pattern_fonts)
            intersection = font_set.intersection(pattern_set)
            
            if len(intersection) >= 3:  # At least 3 matching fonts
                match_percentage = len(intersection) / len(pattern_set) * 100
                if match_percentage > 60:
                    result['is_common'] = True
                    result['pattern_matched'] = pattern_name
                    result['match_percentage'] = match_percentage
                    break
        
        return result
    
    def _identify_system_fonts(self, fonts: List[str], device_data: Dict) -> Dict:
        """Identify system-specific fonts"""
        platform = device_data.get('platform', '').lower()
        font_set = set(f.lower() for f in fonts)
        
        result = {
            'has_system_fonts': True,
            'missing_fonts': []
        }
        
        # Expected fonts based on platform
        expected_fonts = []
        
        if 'windows' in platform:
            expected_fonts = ['arial', 'times new roman', 'courier new', 'tahoma']
        elif 'mac' in platform:
            expected_fonts = ['helvetica', 'times', 'courier', 'geneva']
        elif 'linux' in platform:
            expected_fonts = ['dejavu sans', 'liberation sans', 'freesans']
        
        for font in expected_fonts:
            if font not in font_set:
                result['missing_fonts'].append(font)
        
        if len(result['missing_fonts']) > 2:
            result['has_system_fonts'] = False
        
        return result
    
    def _detect_robotic_movements(self, mouse_data: List[Dict]) -> bool:
        """Detect robotic mouse movements"""
        if len(mouse_data) < 10:
            return False
        
        # Analyze movement patterns
        # This is a simplified version - in production, use more sophisticated analysis
        return False
    
    def _detect_mechanical_scrolling(self, scroll_data: Dict) -> bool:
        """Detect mechanical scrolling patterns"""
        # Implement scroll pattern analysis
        return False
    
    def get_detector_config(self) -> Dict:
        base_config = super().get_detector_config()
        base_config.update({
            'description': 'Advanced device fingerprinting and spoofing detection',
            'version': '2.0.0',
            'thresholds': {
                'min_entropy': self.min_entropy,
                'spoofing_threshold': self.spoofing_threshold,
                'consistency_threshold': self.consistency_threshold
            }
        })
        return base_config