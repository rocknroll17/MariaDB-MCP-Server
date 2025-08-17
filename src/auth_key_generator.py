"""
AuthService용 암호화 키 및 서명 키 생성기

AuthService에서 요구하는 정확한 형식으로 키를 생성합니다:
- ENCRYPTION_KEY: 32바이트 문자열 (UTF-8 인코딩 시 32바이트가 되는 문자열)
- SIGNING_KEY: 임의 길이의 문자열 (HMAC 서명용)
"""

import secrets
import string
from typing import Tuple

def generate_32_byte_string_key() -> str:
    """
    UTF-8로 인코딩했을 때 정확히 32바이트가 되는 문자열 키를 생성합니다.
    
    AuthService에서 len(encryption_key) == 32 체크를 통과하려면
    문자열 자체의 길이가 32여야 합니다.
    
    Returns:
        str: 정확히 32글자(32바이트)의 ASCII 문자열
    """
    # ASCII 문자만 사용하여 32글자 생성 (각 문자가 1바이트)
    alphabet = string.ascii_letters + string.digits
    key = ''.join(secrets.choice(alphabet) for _ in range(32))
    
    # 검증: UTF-8 인코딩했을 때 32바이트인지 확인
    assert len(key.encode('utf-8')) == 32, f"Key length mismatch: {len(key.encode('utf-8'))}"
    
    return key

def generate_signing_key(length: int = 64) -> str:
    """
    HMAC 서명용 키를 생성합니다.
    특수문자 없이 영숫자만 사용하여 환경변수 설정 시 문제를 방지합니다.
    
    Args:
        length (int): 키 길이 (기본값: 64글자)
    
    Returns:
        str: 서명용 키 문자열 (영숫자만)
    """
    alphabet = string.ascii_letters + string.digits  # 특수문자 제거
    return ''.join(secrets.choice(alphabet) for _ in range(length))

def validate_encryption_key(key: str) -> bool:
    """
    암호화 키가 AuthService 요구사항을 만족하는지 검증합니다.
    
    Args:
        key (str): 검증할 키
    
    Returns:
        bool: 유효한 키인지 여부
    """
    try:
        # 문자열 길이가 32인지 확인
        if len(key) != 32:
            print(f"❌ 키 길이 오류: {len(key)} (32 필요)")
            return False
        
        # UTF-8 인코딩 시 32바이트인지 확인
        encoded = key.encode('utf-8')
        if len(encoded) != 32:
            print(f"❌ 인코딩된 키 길이 오류: {len(encoded)}바이트 (32바이트 필요)")
            return False
        
        print(f"✅ 유효한 암호화 키: {len(key)}글자, {len(encoded)}바이트")
        return True
        
    except Exception as e:
        print(f"❌ 키 검증 중 오류: {e}")
        return False

def test_with_auth_service(encryption_key: str, signing_key: str) -> bool:
    """
    생성된 키가 실제 AuthService에서 작동하는지 테스트합니다.
    
    Args:
        encryption_key (str): 암호화 키
        signing_key (str): 서명 키
    
    Returns:
        bool: 테스트 성공 여부
    """
    try:
        # AuthService import는 여기서만 (의존성 최소화)
        import sys
        sys.path.append('/Users/reco/Desktop/MariaDB-MCP/src')
        
        from src.service.auth_service import AuthService
        
        # AuthService 인스턴스 생성 테스트
        auth = AuthService(encryption_key=encryption_key, signing_key=signing_key)
        
        # 토큰 생성/검증 테스트
        test_user_id = "test_user_123"
        token = auth.generate(test_user_id)
        verified_user_id = auth.verify(token)
        
        if verified_user_id == test_user_id:
            print("✅ AuthService 테스트 성공!")
            return True
        else:
            print("❌ AuthService 테스트 실패: 토큰 검증 오류")
            return False
            
    except Exception as e:
        print(f"❌ AuthService 테스트 실패: {e}")
        return False

def generate_keys_for_auth_service() -> Tuple[str, str]:
    """
    AuthService에서 사용할 수 있는 키 쌍을 생성합니다.
    
    Returns:
        Tuple[str, str]: (encryption_key, signing_key)
    """
    print("🔑 AuthService용 키 생성 중...")
    
    # 32바이트 문자열 암호화 키 생성
    encryption_key = generate_32_byte_string_key()
    
    # 서명 키 생성 (64글자)
    signing_key = generate_signing_key(64)
    
    # 키 검증
    if not validate_encryption_key(encryption_key):
        raise ValueError("생성된 암호화 키가 유효하지 않습니다.")
    
    print(f"✅ 암호화 키 생성 완료: {len(encryption_key)}글자")
    print(f"✅ 서명 키 생성 완료: {len(signing_key)}글자")
    
    return encryption_key, signing_key

def main():
    """메인 실행 함수 - 키 생성 후 바로 출력"""
    print("🔐 AuthService용 키 생성")
    print("=" * 50)
    
    # 키 생성
    encryption_key = generate_32_byte_string_key()
    signing_key = generate_signing_key(64)
    
    # 키 출력
    print(f"ENCRYPTION_KEY={encryption_key}")
    print(f"SIGNING_KEY={signing_key}")
    
    return 0

if __name__ == "__main__":
    main()
