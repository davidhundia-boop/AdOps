"""
AppsFlyer Tracking Link Generator and Parser.

Provides functionality to:
- Parse AppsFlyer tracking links into their component parameters
- Generate tracking links from campaign data
- Create test links with device IDs and custom parameters
"""

from urllib.parse import urlparse, parse_qs, urlencode, quote
from typing import Dict, Optional, List, Any
import re


class AppsFlyerTrackingLink:
    """AppsFlyer tracking link handler for parsing, generating, and testing tracking links."""
    
    # Standard AppsFlyer parameters with descriptions
    STANDARD_PARAMS = {
        'pid': 'Media source (partner ID)',
        'c': 'Campaign name',
        'af_c_id': 'Campaign ID',
        'af_adset': 'Ad set name',
        'af_adset_id': 'Ad set ID',
        'af_ad': 'Ad name',
        'af_ad_id': 'Ad ID',
        'af_siteid': 'Publisher/Site ID',
        'af_sub1': 'Sub parameter 1',
        'af_sub2': 'Sub parameter 2',
        'af_sub3': 'Sub parameter 3',
        'af_sub4': 'Sub parameter 4',
        'af_sub5': 'Sub parameter 5',
        'af_click_lookback': 'Click lookback window',
        'af_prt': 'Agency/Partner name',
        'clickid': 'Click ID',
        'advertising_id': 'Android Advertising ID (GAID)',
        'sha1_advertising_id': 'SHA1 hashed Advertising ID',
        'idfa': 'iOS IDFA',
        'idfv': 'iOS IDFV',
        'af_dp': 'Deep link path',
        'af_web_dp': 'Web deep link',
        'is_retargeting': 'Retargeting flag',
        'af_reengagement_window': 'Re-engagement window',
        'af_ua': 'User agent',
        'redirect': 'Redirect URL',
        'af_r': 'Fallback URL',
    }
    
    # Placeholder patterns commonly used in tracking templates
    PLACEHOLDER_PATTERNS = [
        r'\[([A-Z_]+)\]',  # [PLACEHOLDER]
        r'\{([a-z_]+)\}',  # {placeholder}
        r'\$\{([a-zA-Z_]+)\}',  # ${placeholder}
        r'__([A-Z_]+)__',  # __PLACEHOLDER__
    ]
    
    def __init__(self, url: Optional[str] = None):
        """Initialize with an optional tracking link URL to parse."""
        self.app_id: Optional[str] = None
        self.base_url: str = "https://app.appsflyer.com"
        self.params: Dict[str, str] = {}
        self.placeholders: Dict[str, str] = {}
        
        if url:
            self.parse(url)
    
    def parse(self, url: str) -> 'AppsFlyerTrackingLink':
        """Parse an AppsFlyer tracking link URL into its components."""
        url = url.strip()
        
        # Handle URLs that might be truncated or duplicated (like in the user's message)
        if '|' in url:
            url = url.split('|')[0]
        
        parsed = urlparse(url)
        
        # Extract app ID from path (e.g., /com.makemytrip)
        path = parsed.path.strip('/')
        if path:
            self.app_id = path
        
        # Parse query parameters
        query_params = parse_qs(parsed.query, keep_blank_values=True)
        
        for key, values in query_params.items():
            value = values[0] if values else ''
            self.params[key] = value
            
            # Detect placeholders in values
            for pattern in self.PLACEHOLDER_PATTERNS:
                matches = re.findall(pattern, value)
                for match in matches:
                    self.placeholders[match] = key
        
        return self
    
    def generate(
        self,
        app_id: Optional[str] = None,
        params: Optional[Dict[str, str]] = None,
        include_existing: bool = True
    ) -> str:
        """
        Generate an AppsFlyer tracking link URL.
        
        Args:
            app_id: The app package/bundle ID (e.g., com.makemytrip)
            params: Dictionary of parameters to include
            include_existing: Whether to include existing parsed parameters
            
        Returns:
            The generated tracking link URL
        """
        final_app_id = app_id or self.app_id
        if not final_app_id:
            raise ValueError("App ID is required to generate a tracking link")
        
        final_params = {}
        
        if include_existing:
            final_params.update(self.params)
        
        if params:
            final_params.update(params)
        
        # Build the URL
        query_string = urlencode(final_params, safe='[]{}$_')
        return f"{self.base_url}/{final_app_id}?{query_string}"
    
    def generate_test_link(
        self,
        device_id: Optional[str] = None,
        test_param: Optional[str] = None,
        replacements: Optional[Dict[str, str]] = None
    ) -> str:
        """
        Generate a test tracking link with device ID and custom replacements.
        
        Args:
            device_id: Device advertising ID (GAID/IDFA) for attribution testing
            test_param: Custom test parameter value (added as af_sub1)
            replacements: Dictionary to replace placeholder values
            
        Returns:
            The generated test tracking link URL
        """
        test_params = dict(self.params)
        
        # Replace placeholders with provided values
        if replacements:
            for key, value in test_params.items():
                for placeholder, replacement in replacements.items():
                    # Replace various placeholder formats
                    value = value.replace(f'[{placeholder}]', replacement)
                    value = value.replace(f'{{{placeholder.lower()}}}', replacement)
                    value = value.replace(f'${{{placeholder}}}', replacement)
                    value = value.replace(f'__{placeholder}__', replacement)
                test_params[key] = value
        
        # Add device ID for attribution
        if device_id:
            test_params['advertising_id'] = device_id
            # Remove SHA1 placeholder if present since we're using raw ID
            if 'sha1_advertising_id' in test_params:
                sha1_val = test_params['sha1_advertising_id']
                if any(re.match(pattern, sha1_val) for pattern in self.PLACEHOLDER_PATTERNS):
                    del test_params['sha1_advertising_id']
        
        # Add test parameter
        if test_param:
            test_params['af_sub1'] = test_param
        
        return self.generate(params=test_params, include_existing=False)
    
    def get_summary(self) -> Dict[str, Any]:
        """Get a summary of the parsed tracking link."""
        return {
            'app_id': self.app_id,
            'partner_id': self.params.get('pid', ''),
            'campaign': self.params.get('c', ''),
            'campaign_id': self.params.get('af_c_id', ''),
            'ad_set': self.params.get('af_adset', ''),
            'ad_set_id': self.params.get('af_adset_id', ''),
            'site_id': self.params.get('af_siteid', ''),
            'partner': self.params.get('af_prt', ''),
            'click_lookback': self.params.get('af_click_lookback', ''),
            'total_params': len(self.params),
            'placeholders': list(self.placeholders.keys()),
        }
    
    def validate(self) -> Dict[str, Any]:
        """
        Validate the tracking link and return any issues.
        
        Returns:
            Dictionary with 'valid' boolean and 'issues' list
        """
        issues = []
        warnings = []
        
        # Check required fields
        if not self.app_id:
            issues.append("Missing app ID in URL path")
        
        if 'pid' not in self.params:
            issues.append("Missing 'pid' (media source/partner ID)")
        
        if 'c' not in self.params and 'af_c_id' not in self.params:
            warnings.append("No campaign name or ID specified")
        
        # Check for unresolved placeholders that might cause issues
        for key, value in self.params.items():
            for pattern in self.PLACEHOLDER_PATTERNS:
                if re.search(pattern, str(value)):
                    warnings.append(f"Unresolved placeholder in '{key}': {value}")
                    break
        
        return {
            'valid': len(issues) == 0,
            'issues': issues,
            'warnings': warnings,
        }
    
    @classmethod
    def from_campaign_data(
        cls,
        app_id: str,
        campaign_name: str,
        campaign_id: str,
        site_id: str,
        partner_id: str = "onedigitalturbine_int",
        partner_name: str = "",
        click_lookback: str = "7d",
        additional_params: Optional[Dict[str, str]] = None
    ) -> 'AppsFlyerTrackingLink':
        """
        Create a tracking link from campaign data.
        
        Args:
            app_id: The app package/bundle ID
            campaign_name: Campaign name
            campaign_id: Campaign ID
            site_id: Publisher/Site ID
            partner_id: Media source partner ID (default: onedigitalturbine_int)
            partner_name: Agency/partner name
            click_lookback: Click attribution lookback window (default: 7d)
            additional_params: Any additional parameters
            
        Returns:
            Configured AppsFlyerTrackingLink instance
        """
        link = cls()
        link.app_id = app_id
        
        link.params = {
            'pid': partner_id,
            'c': campaign_name,
            'af_c_id': campaign_id,
            'af_siteid': f"od_{site_id}" if not str(site_id).startswith('od_') else site_id,
            'af_adset': campaign_name,
            'af_adset_id': campaign_id,
            'af_click_lookback': click_lookback,
        }
        
        if partner_name:
            link.params['af_prt'] = partner_name
        
        if additional_params:
            link.params.update(additional_params)
        
        return link


def parse_tracking_link(url: str) -> AppsFlyerTrackingLink:
    """Parse an AppsFlyer tracking link URL."""
    return AppsFlyerTrackingLink(url)


def generate_tracking_link(
    app_id: str,
    campaign_name: str,
    campaign_id: str,
    site_id: str,
    **kwargs
) -> str:
    """Generate an AppsFlyer tracking link from campaign data."""
    link = AppsFlyerTrackingLink.from_campaign_data(
        app_id=app_id,
        campaign_name=campaign_name,
        campaign_id=campaign_id,
        site_id=site_id,
        **kwargs
    )
    return link.generate()


def generate_test_link(
    url: str,
    device_id: str,
    test_param: Optional[str] = None,
    replacements: Optional[Dict[str, str]] = None
) -> str:
    """Generate a test tracking link from an existing URL template."""
    link = AppsFlyerTrackingLink(url)
    return link.generate_test_link(
        device_id=device_id,
        test_param=test_param,
        replacements=replacements
    )
