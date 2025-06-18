import asyncio
import aiohttp
import requests
from typing import Dict, Any, Optional, List, Union
from datetime import datetime
import json
import time
from urllib.parse import urljoin

from config import config
from utils.logger import get_logger, log_exceptions
from models.data_models import APIResponse, SearchCriteria, SearchResult

logger = get_logger("api_client")

class APIError(Exception):
    """Custom API error exception"""
    def __init__(self, message: str, status_code: Optional[int] = None, response_data: Optional[Dict] = None):
        super().__init__(message)
        self.status_code = status_code
        self.response_data = response_data

class APIClient:
    """HTTP API client for backend communication"""
    
    def __init__(self, base_url: Optional[str] = None, api_key: Optional[str] = None):
        self.base_url = base_url or config.api.base_url
        self.api_key = api_key
        self.timeout = config.api.timeout
        self.retry_attempts = config.api.retry_attempts
        self.session = None
        
    async def __aenter__(self):
        """Async context manager entry"""
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=self.timeout),
            headers=self._get_headers()
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.session:
            await self.session.close()
    
    def _get_headers(self) -> Dict[str, str]:
        """Get request headers"""
        headers = {
            "Content-Type": config.api.content_type,
            "Accept": "application/json",
            "User-Agent": f"Anubis-Forensics/{config.app.version}"
        }
        
        if self.api_key:
            headers[config.api.api_key_header] = self.api_key
            
        return headers
    
    def _build_url(self, endpoint: str) -> str:
        """Build full URL for endpoint"""
        return urljoin(self.base_url, endpoint)
    
    @log_exceptions("api_client")
    async def _make_request(
        self, 
        method: str, 
        endpoint: str, 
        data: Optional[Dict] = None,
        params: Optional[Dict] = None,
        files: Optional[Dict] = None
    ) -> APIResponse:
        """Make HTTP request with retry logic"""
        
        url = self._build_url(endpoint)
        headers = self._get_headers()
        
        for attempt in range(self.retry_attempts):
            try:
                if method.upper() == "GET":
                    async with self.session.get(url, params=params, headers=headers) as response:
                        return await self._handle_response(response)
                        
                elif method.upper() == "POST":
                    if files:
                        # Handle file uploads
                        form_data = aiohttp.FormData()
                        for key, value in data.items() if data else {}:
                            form_data.add_field(key, str(value))
                        for key, file_info in files.items():
                            form_data.add_field(key, file_info['file'], filename=file_info['filename'])
                        
                        async with self.session.post(url, data=form_data, headers=headers) as response:
                            return await self._handle_response(response)
                    else:
                        async with self.session.post(url, json=data, headers=headers) as response:
                            return await self._handle_response(response)
                            
                elif method.upper() == "PUT":
                    async with self.session.put(url, json=data, headers=headers) as response:
                        return await self._handle_response(response)
                        
                elif method.upper() == "DELETE":
                    async with self.session.delete(url, headers=headers) as response:
                        return await self._handle_response(response)
                        
            except aiohttp.ClientError as e:
                logger.warning(f"Request attempt {attempt + 1} failed: {e}")
                if attempt == self.retry_attempts - 1:
                    raise APIError(f"Request failed after {self.retry_attempts} attempts: {e}")
                await asyncio.sleep(2 ** attempt)  # Exponential backoff
                
        raise APIError("Request failed")
    
    async def _handle_response(self, response: aiohttp.ClientResponse) -> APIResponse:
        """Handle HTTP response"""
        try:
            response_data = await response.json()
        except json.JSONDecodeError:
            response_text = await response.text()
            response_data = {"message": response_text}
        
        if response.status >= 400:
            error_msg = response_data.get("message", f"HTTP {response.status}")
            raise APIError(error_msg, response.status, response_data)
        
        return APIResponse(
            success=response.status < 400,
            data=response_data.get("data"),
            message=response_data.get("message"),
            error_code=response_data.get("error_code"),
            metadata=response_data.get("metadata", {})
        )
    
    # Case Management API methods
    async def create_case(self, case_data: Dict[str, Any]) -> APIResponse:
        """Create a new case"""
        return await self._make_request("POST", "/cases", data=case_data)
    
    async def get_case(self, case_id: str) -> APIResponse:
        """Get case by ID"""
        return await self._make_request("GET", f"/cases/{case_id}")
    
    async def update_case(self, case_id: str, case_data: Dict[str, Any]) -> APIResponse:
        """Update case"""
        return await self._make_request("PUT", f"/cases/{case_id}", data=case_data)
    
    async def delete_case(self, case_id: str) -> APIResponse:
        """Delete case"""
        return await self._make_request("DELETE", f"/cases/{case_id}")
    
    async def list_cases(self, criteria: Optional[SearchCriteria] = None) -> APIResponse:
        """List cases with optional filtering"""
        params = {}
        if criteria:
            if criteria.query:
                params["q"] = criteria.query
            if criteria.filters:
                params.update(criteria.filters)
            if criteria.sort_by:
                params["sort_by"] = criteria.sort_by
            if criteria.sort_order:
                params["sort_order"] = criteria.sort_order
            params["page"] = criteria.page
            params["page_size"] = criteria.page_size
            
        return await self._make_request("GET", "/cases", params=params)
    
    # Evidence Management API methods
    async def add_evidence(self, case_id: str, evidence_data: Dict[str, Any]) -> APIResponse:
        """Add evidence to case"""
        return await self._make_request("POST", f"/cases/{case_id}/evidence", data=evidence_data)
    
    async def get_evidence(self, case_id: str, evidence_id: str) -> APIResponse:
        """Get evidence by ID"""
        return await self._make_request("GET", f"/cases/{case_id}/evidence/{evidence_id}")
    
    async def update_evidence(self, case_id: str, evidence_id: str, evidence_data: Dict[str, Any]) -> APIResponse:
        """Update evidence"""
        return await self._make_request("PUT", f"/cases/{case_id}/evidence/{evidence_id}", data=evidence_data)
    
    async def delete_evidence(self, case_id: str, evidence_id: str) -> APIResponse:
        """Delete evidence"""
        return await self._make_request("DELETE", f"/cases/{case_id}/evidence/{evidence_id}")
    
    async def list_evidence(self, case_id: str, criteria: Optional[SearchCriteria] = None) -> APIResponse:
        """List evidence for a case"""
        params = {}
        if criteria:
            if criteria.query:
                params["q"] = criteria.query
            if criteria.filters:
                params.update(criteria.filters)
            if criteria.sort_by:
                params["sort_by"] = criteria.sort_by
            if criteria.sort_order:
                params["sort_order"] = criteria.sort_order
            params["page"] = criteria.page
            params["page_size"] = criteria.page_size
            
        return await self._make_request("GET", f"/cases/{case_id}/evidence", params=params)
    
    # Remote Acquisition API methods
    async def create_acquisition_session(self, session_data: Dict[str, Any]) -> APIResponse:
        """Create a new acquisition session"""
        return await self._make_request("POST", "/acquisition/sessions", data=session_data)
    
    async def get_acquisition_session(self, session_id: str) -> APIResponse:
        """Get acquisition session by ID"""
        return await self._make_request("GET", f"/acquisition/sessions/{session_id}")
    
    async def update_acquisition_session(self, session_id: str, session_data: Dict[str, Any]) -> APIResponse:
        """Update acquisition session"""
        return await self._make_request("PUT", f"/acquisition/sessions/{session_id}", data=session_data)
    
    async def start_acquisition(self, session_id: str) -> APIResponse:
        """Start acquisition session"""
        return await self._make_request("POST", f"/acquisition/sessions/{session_id}/start")
    
    async def stop_acquisition(self, session_id: str) -> APIResponse:
        """Stop acquisition session"""
        return await self._make_request("POST", f"/acquisition/sessions/{session_id}/stop")
    
    async def get_acquisition_progress(self, session_id: str) -> APIResponse:
        """Get acquisition progress"""
        return await self._make_request("GET", f"/acquisition/sessions/{session_id}/progress")
    
    # Agent Management API methods
    async def list_agents(self) -> APIResponse:
        """List available agents"""
        return await self._make_request("GET", "/agents")
    
    async def get_agent(self, agent_id: str) -> APIResponse:
        """Get agent by ID"""
        return await self._make_request("GET", f"/agents/{agent_id}")
    
    async def register_agent(self, agent_data: Dict[str, Any]) -> APIResponse:
        """Register a new agent"""
        return await self._make_request("POST", "/agents", data=agent_data)
    
    # File Upload API methods
    async def upload_file(self, file_path: str, metadata: Optional[Dict[str, Any]] = None) -> APIResponse:
        """Upload a file"""
        import os
        
        if not os.path.exists(file_path):
            raise APIError(f"File not found: {file_path}")
        
        files = {
            "file": {
                "file": open(file_path, "rb"),
                "filename": os.path.basename(file_path)
            }
        }
        
        data = metadata or {}
        
        return await self._make_request("POST", "/files/upload", data=data, files=files)
    
    # Health Check
    async def health_check(self) -> APIResponse:
        """Check API health"""
        return await self._make_request("GET", "/health")

# Synchronous wrapper for compatibility
class SyncAPIClient:
    """Synchronous wrapper for API client"""
    
    def __init__(self, base_url: Optional[str] = None, api_key: Optional[str] = None):
        self.base_url = base_url or config.api.base_url
        self.api_key = api_key
        self.timeout = config.api.timeout
        self.retry_attempts = config.api.retry_attempts
        self.session = requests.Session()
        self.session.headers.update(self._get_headers())
    
    def _get_headers(self) -> Dict[str, str]:
        """Get request headers"""
        headers = {
            "Content-Type": config.api.content_type,
            "Accept": "application/json",
            "User-Agent": f"Anubis-Forensics/{config.app.version}"
        }
        
        if self.api_key:
            headers[config.api.api_key_header] = self.api_key
            
        return headers
    
    def _build_url(self, endpoint: str) -> str:
        """Build full URL for endpoint"""
        return urljoin(self.base_url, endpoint)
    
    @log_exceptions("api_client")
    def _make_request(
        self, 
        method: str, 
        endpoint: str, 
        data: Optional[Dict] = None,
        params: Optional[Dict] = None,
        files: Optional[Dict] = None
    ) -> APIResponse:
        """Make HTTP request with retry logic"""
        
        url = self._build_url(endpoint)
        
        for attempt in range(self.retry_attempts):
            try:
                if method.upper() == "GET":
                    response = self.session.get(url, params=params, timeout=self.timeout)
                elif method.upper() == "POST":
                    if files:
                        response = self.session.post(url, data=data, files=files, timeout=self.timeout)
                    else:
                        response = self.session.post(url, json=data, timeout=self.timeout)
                elif method.upper() == "PUT":
                    response = self.session.put(url, json=data, timeout=self.timeout)
                elif method.upper() == "DELETE":
                    response = self.session.delete(url, timeout=self.timeout)
                else:
                    raise APIError(f"Unsupported HTTP method: {method}")
                
                return self._handle_response(response)
                
            except requests.RequestException as e:
                logger.warning(f"Request attempt {attempt + 1} failed: {e}")
                if attempt == self.retry_attempts - 1:
                    raise APIError(f"Request failed after {self.retry_attempts} attempts: {e}")
                time.sleep(2 ** attempt)  # Exponential backoff
                
        raise APIError("Request failed")
    
    def _handle_response(self, response: requests.Response) -> APIResponse:
        """Handle HTTP response"""
        try:
            response_data = response.json()
        except json.JSONDecodeError:
            response_data = {"message": response.text}
        
        if response.status_code >= 400:
            error_msg = response_data.get("message", f"HTTP {response.status_code}")
            raise APIError(error_msg, response.status_code, response_data)
        
        return APIResponse(
            success=response.status_code < 400,
            data=response_data.get("data"),
            message=response_data.get("message"),
            error_code=response_data.get("error_code"),
            metadata=response_data.get("metadata", {})
        )
    
    # Delegate all methods to async client
    def create_case(self, case_data: Dict[str, Any]) -> APIResponse:
        """Create a new case"""
        return self._make_request("POST", "/cases", data=case_data)
    
    def get_case(self, case_id: str) -> APIResponse:
        """Get case by ID"""
        return self._make_request("GET", f"/cases/{case_id}")
    
    def update_case(self, case_id: str, case_data: Dict[str, Any]) -> APIResponse:
        """Update case"""
        return self._make_request("PUT", f"/cases/{case_id}", data=case_data)
    
    def delete_case(self, case_id: str) -> APIResponse:
        """Delete case"""
        return self._make_request("DELETE", f"/cases/{case_id}")
    
    def list_cases(self, criteria: Optional[SearchCriteria] = None) -> APIResponse:
        """List cases with optional filtering"""
        params = {}
        if criteria:
            if criteria.query:
                params["q"] = criteria.query
            if criteria.filters:
                params.update(criteria.filters)
            if criteria.sort_by:
                params["sort_by"] = criteria.sort_by
            if criteria.sort_order:
                params["sort_order"] = criteria.sort_order
            params["page"] = criteria.page
            params["page_size"] = criteria.page_size
            
        return self._make_request("GET", "/cases", params=params)
    
    def health_check(self) -> APIResponse:
        """Check API health"""
        return self._make_request("GET", "/health") 