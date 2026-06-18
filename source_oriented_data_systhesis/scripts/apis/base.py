#!/usr/bin/env python3
"""
Base Classes for API Clients

This module provides shared base classes used by all API clients across
different domains.
"""

import json
import requests
from typing import Dict, Optional
from dataclasses import dataclass


@dataclass
class APIError(Exception):
    """Custom exception for API errors"""
    status_code: int
    message: str


class BaseClient:
    """Base class for API clients

    Provides common functionality for all API clients:
    - HTTP request handling
    - Error handling
    - Session management
    - Timeout configuration
    """

    def __init__(self, timeout: int = 15):
        """Initialize base client

        Args:
            timeout: Request timeout in seconds (default: 15)
        """
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (compatible; DataSynthesisBot/1.0)'
        })

    def _get(self, url: str, params: Optional[Dict] = None) -> Dict:
        """Make GET request and return JSON response

        Args:
            url: Request URL
            params: Optional query parameters

        Returns:
            JSON response as dict

        Raises:
            APIError: For HTTP errors, timeouts, or other exceptions
        """
        try:
            response = self.session.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 401:
                raise APIError(401, "Authentication required")
            elif e.response.status_code == 403:
                raise APIError(403, "Access forbidden")
            elif e.response.status_code == 429:
                raise APIError(429, "Rate limit exceeded")
            else:
                raise APIError(e.response.status_code, str(e))
        except requests.exceptions.Timeout:
            raise APIError(408, "Request timeout")
        except Exception as e:
            raise APIError(500, str(e))

    def _post(self, url: str, data: Optional[Dict] = None,
              json_data: Optional[Dict] = None) -> Dict:
        """Make POST request and return JSON response

        Args:
            url: Request URL
            data: Form data
            json_data: JSON data

        Returns:
            JSON response as dict

        Raises:
            APIError: For HTTP errors, timeouts, or other exceptions
        """
        try:
            if json_data:
                response = self.session.post(url, json=json_data, timeout=self.timeout)
            else:
                response = self.session.post(url, data=data, timeout=self.timeout)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 401:
                raise APIError(401, "Authentication required")
            elif e.response.status_code == 403:
                raise APIError(403, "Access forbidden")
            elif e.response.status_code == 429:
                raise APIError(429, "Rate limit exceeded")
            else:
                raise APIError(e.response.status_code, str(e))
        except requests.exceptions.Timeout:
            raise APIError(408, "Request timeout")
        except Exception as e:
            raise APIError(500, str(e))


class WebScraperClient:
    """Base client for web scraping

    Used by APIs that scrape websites rather than using formal APIs.
    """

    def __init__(self, timeout: int = 15):
        """Initialize web scraper client

        Args:
            timeout: Request timeout in seconds (default: 15)
        """
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })

    def _get(self, url: str) -> Optional[str]:
        """Get HTML content from URL

        Args:
            url: URL to fetch

        Returns:
            HTML content as string, or None if failed
        """
        try:
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            return response.text
        except Exception:
            return None
