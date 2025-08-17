import functools
import logging
from typing import Optional, Callable, Any
from contextvars import ContextVar
from fastmcp.server.dependencies import get_http_request
from starlette.requests import Request
from service.auth_service import AuthService
from logger.logger import Logger
from exceptions.exceptions import AuthenticationError
from config.config import (
    ENCRYPTION_KEY,
    SIGNING_KEY,
    MCP_AUTH_ENABLED
)
logger = Logger.getLogger()

# 현재 사용자 ID를 저장하는 컨텍스트 변수
_current_user_id: ContextVar[Optional[str]] = ContextVar('current_user_id', default=None)
_current_client_ip: ContextVar[Optional[str]] = ContextVar('current_client_ip', default=None)
_current_api_key: ContextVar[Optional[str]] = ContextVar('current_api_key', default=None)

def get_current_user_id() -> Optional[str]:
    """현재 인증된 사용자 ID를 반환합니다."""
    return _current_user_id.get()

def get_current_client_ip() -> Optional[str]:
    """현재 클라이언트 IP 주소를 반환합니다."""
    return _current_client_ip.get()

def get_current_api_key() -> Optional[str]:
    """현재 사용된 API 키를 반환합니다."""
    return _current_api_key.get()

auth_service = AuthService(
    encryption_key=ENCRYPTION_KEY,
    signing_key=SIGNING_KEY
)

class Auth:
    """MCP 툴 인증을 위한 데코레이터 클래스"""
    
    def _extract_token_from_request(self, request: Request) -> Optional[str]:
        """HTTP 요청에서 Authorization 토큰 추출"""
        try:
            auth_header = request.headers.get("authorization", "")
            if auth_header.startswith("Bearer "):
                token = auth_header[7:]  # "Bearer " 제거
                return token
            # 토큰이 없거나 형식이 잘못된 경우는 caller에서 로깅
            return None
        except Exception as e:
            logger.error(f"Failed to extract token from request: {type(e).__name__}: {str(e)}")
            return None

    def _extract_client_ip(self, request: Request) -> str:
        """HTTP 요청에서 클라이언트 IP 주소 추출"""
        try:
            # X-Forwarded-For 헤더 확인 (프록시 뒤에 있는 경우)
            forwarded_for = request.headers.get("x-forwarded-for")
            if forwarded_for:
                # 첫 번째 IP 주소가 실제 클라이언트 IP
                return forwarded_for.split(",")[0].strip()
            
            # X-Real-IP 헤더 확인
            real_ip = request.headers.get("x-real-ip")
            if real_ip:
                return real_ip.strip()
            
            # 직접 연결된 경우 클라이언트 IP
            if hasattr(request, 'client') and request.client:
                return request.client.host
            
            return "unknown"
        except Exception as e:
            logger.warning(f"Failed to extract client IP: {type(e).__name__}: {str(e)}")
            return "unknown"

    def require_auth(self, func: Callable) -> Callable:
        """
        인증을 요구하는 데코레이터
        인증된 사용자의 user_id를 ContextVar에 설정
        """
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            client_ip = "unknown"
            token_preview = "none"
            
            try:
                # HTTP 요청 가져오기 (인증 비활성화 시에도 필요)
                request = get_http_request()
                
                # 클라이언트 IP 추출 (항상 먼저 추출하여 로깅에 사용)
                if request:
                    client_ip = self._extract_client_ip(request)
                    _current_client_ip.set(client_ip)
                
                if not MCP_AUTH_ENABLED:
                    # 인증이 비활성화된 경우, user_id를 "anonymous"로 설정
                    logger.info(f"AUTH BYPASS: Authentication disabled | IP: {client_ip} | Function: {func.__name__}")
                    _current_user_id.set("Anonymous")
                    _current_api_key.set("none")
                    return await func(*args, **kwargs)
                
                if not request:
                    logger.error(f"AUTH ERROR: No HTTP request context available | IP: {client_ip}")
                    raise AuthenticationError("No request context available")
                
                # 토큰 추출 및 보안 로깅
                token = self._extract_token_from_request(request)
                if not token:
                    logger.warning(f"AUTH FAILED: No authorization token provided | IP: {client_ip} | Function: {func.__name__}")
                    raise AuthenticationError("Authorization token required")
                
                _current_api_key.set(token)
                
                # 토큰 검증
                auth_service = AuthService()
                user_id = auth_service.verify(token)
                if not user_id:
                    logger.warning(f"AUTH FAILED: Invalid or expired token | IP: {client_ip} | Token: {token} | Function: {func.__name__}")
                    raise AuthenticationError("Invalid or expired token")
                
                # 인증 성공
                _current_user_id.set(user_id)
                
                # 원래 함수 실행 (시그니처 변경 없음)
                return await func(*args, **kwargs)
                
            except AuthenticationError as e:
                # 인증 에러는 이미 위에서 로깅했으므로 재발생만
                raise
            except Exception as e:
                # 비즈니스 로직 에러는 AUTH ERROR로 로깅하지 않고 그대로 전파
                raise
        
        return wrapper

# 전역 인스턴스 생성
auth = Auth()
