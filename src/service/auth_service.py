import base64
import hmac
import hashlib
import functools
from typing import Optional, Callable
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
from Crypto.Random import get_random_bytes
import logging
from contextvars import ContextVar
from fastmcp.server.dependencies import get_http_request
from starlette.requests import Request

logger = logging.getLogger(__name__)

from config import API_KEYS
from exceptions import AuthenticationError
from config.config import MCP_AUTH_ENABLED

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

class AuthService:
    _instance = None
    _initialized = False
    
    def __new__(cls, encryption_key: str = None, signing_key: str = None):
        if cls._instance is None:
            cls._instance = super(AuthService, cls).__new__(cls)
        return cls._instance
    
    def __init__(self, encryption_key: str = None, signing_key: str = None):
        if not self._initialized:
            # 필수 값들이 없으면 오류 발생
            if encryption_key is None:
                logger.error("[AuthService] ENCRYPTION_KEY is missing.")
                raise ValueError("ENCRYPTION_KEY must be provided either as parameter or environment variable")
            if signing_key is None:
                logger.error("[AuthService] SIGNING_KEY is missing.")
                raise ValueError("SIGNING_KEY must be provided either as parameter or environment variable")
            if len(encryption_key) != 32:
                print(len(encryption_key))
                print(encryption_key)
                logger.error(f"[AuthService] ENCRYPTION_KEY length is {len(encryption_key)} (must be 32 bytes)")
                raise ValueError("Encryption key must be 32 bytes (AES-256)")
            self.encryption_key = encryption_key.encode() if isinstance(encryption_key, str) else encryption_key
            self.signing_key = signing_key.encode() if isinstance(signing_key, str) else signing_key
            AuthService._initialized = True

    def _encrypt_user_id(self, user_id: str) -> str:
        logger.debug(f"[AuthService] Encrypting user_id: {user_id}")
        iv = get_random_bytes(16)
        cipher = AES.new(self.encryption_key, AES.MODE_CBC, iv)
        ciphertext = cipher.encrypt(pad(user_id.encode(), AES.block_size))
        full = iv + ciphertext
        enc = base64.urlsafe_b64encode(full).decode()
        logger.debug(f"[AuthService] Encrypted user_id to: {enc}")
        return enc

    def _decrypt_user_id(self, encrypted_b64: str) -> str:
        logger.debug(f"[AuthService] Decrypting user_id: {encrypted_b64}")
        full = base64.urlsafe_b64decode(encrypted_b64.encode())
        iv, ciphertext = full[:16], full[16:]
        cipher = AES.new(self.encryption_key, AES.MODE_CBC, iv)
        decrypted = unpad(cipher.decrypt(ciphertext), AES.block_size)
        user_id = decrypted.decode()
        logger.debug(f"[AuthService] Decrypted user_id to: {user_id}")
        return user_id

    def _sign(self, enc_user_id: str) -> str:
        logger.debug(f"[AuthService] Signing encrypted user_id: {enc_user_id}")
        sig = hmac.new(self.signing_key, enc_user_id.encode(), hashlib.sha256).hexdigest()
        logger.debug(f"[AuthService] Signature: {sig}")
        return sig

    def generate(self, user_id: str) -> str:
        enc_user_id = self._encrypt_user_id(user_id)
        signature = self._sign(enc_user_id)
        token = f"{enc_user_id}:{signature}"
        logger.info(f"[AuthService] Token generated: {user_id}")
        return token

    def verify(self, token: str) -> Optional[str]:
        try:
            enc_user_id, sig = token.strip().split(":", 1)
            expected_sig = self._sign(enc_user_id)
            if not hmac.compare_digest(expected_sig, sig): 
                return False
            if token in API_KEYS:
                user_id = self._decrypt_user_id(enc_user_id)
                return user_id
            else:
                return False
        except Exception as e:
            return False

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

    @classmethod
    def authorization(cls, auth_instance_attr: str = 'auth'):
        """
        클래스 메서드용 인증 데코레이터
        
        Args:
            auth_instance_attr: AuthService 인스턴스가 저장된 속성명 (기본값: 'auth')
        
        Usage:
            class MyServer:
                def __init__(self):
                    self.auth = AuthService(...)
                
                @AuthService.authorization()
                async def my_method(self):
                    pass
        """
        def decorator(func: Callable) -> Callable:
            @functools.wraps(func)
            async def wrapper(self, *args, **kwargs):
                # self에서 AuthService 인스턴스 가져오기
                auth_service = getattr(self, auth_instance_attr, None)
                if auth_service is None:
                    raise ValueError(f"AuthService instance not found at '{auth_instance_attr}' attribute")
                
                # 인증 로직 실행
                client_ip = "unknown"
                
                try:
                    # HTTP 요청 가져오기 (인증 비활성화 시에도 필요)
                    request = get_http_request()
                    
                    # 클라이언트 IP 추출 (항상 먼저 추출하여 로깅에 사용)
                    if request:
                        client_ip = auth_service._extract_client_ip(request)
                        _current_client_ip.set(client_ip)
                    
                    if not MCP_AUTH_ENABLED:
                        # 인증이 비활성화된 경우, user_id를 "anonymous"로 설정
                        logger.info(f"AUTH BYPASS: Authentication disabled | IP: {client_ip} | Function: {func.__name__}")
                        _current_user_id.set("Anonymous")
                        _current_api_key.set("none")
                        return await func(self, *args, **kwargs)
                    
                    if not request:
                        logger.error(f"AUTH ERROR: No HTTP request context available | IP: {client_ip}")
                        raise AuthenticationError("No request context available")
                    
                    # 토큰 추출 및 보안 로깅
                    token = auth_service._extract_token_from_request(request)
                    if not token:
                        logger.warning(f"AUTH FAILED: No authorization token provided | IP: {client_ip} | Function: {func.__name__}")
                        raise AuthenticationError("Authorization token required")
                    
                    _current_api_key.set(token)
                    
                    # 토큰 검증
                    user_id = auth_service.verify(token)
                    if not user_id:
                        logger.warning(f"AUTH FAILED: Invalid or expired token | IP: {client_ip} | Token: {token} | Function: {func.__name__}")
                        raise AuthenticationError("Invalid or expired token")
                    
                    # 인증 성공
                    _current_user_id.set(user_id)
                    
                    # 원래 함수 실행 (시그니처 변경 없음)
                    return await func(self, *args, **kwargs)
                    
                except AuthenticationError as e:
                    # 인증 에러는 이미 위에서 로깅했으므로 재발생만
                    raise
                except Exception as e:
                    # 비즈니스 로직 에러는 AUTH ERROR로 로깅하지 않고 그대로 전파
                    raise
            
            return wrapper
        return decorator
