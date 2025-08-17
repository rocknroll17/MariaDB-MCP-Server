#!/usr/bin/env python3
"""
인증 키 생성 스크립트

독립적으로 실행 가능한 인증 키 생성기
"""

import sys
import argparse
from pathlib import Path

# 프로젝트 src 경로를 추가
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

from core.factory import service_factory

def main():
    parser = argparse.ArgumentParser(description="인증 키 생성기")
    parser.add_argument("token", help="인증할 토큰")
    parser.add_argument("--verify", "-v", action="store_true", help="토큰 검증 모드")
    
    args = parser.parse_args()
    
    try:
        auth_service = service_factory.auth_service
        
        if args.verify:
            # 토큰 검증
            is_valid = auth_service.verify(args.token)
            result = f"Token: {args.token}\nValid: {'✅ YES' if is_valid else '❌ NO'}"
        else:
            # 새 키 생성 (예시 - user_id로 토큰 사용)
            new_key = auth_service.generate(args.token)
            result = f"Input: {args.token}\nGenerated Key: {new_key}"
        
        print("==============================")
        print("  🔐 인증 키 처리 결과")
        print("------------------------------")
        print(result)
        print("==============================")
        
        return 0
        
    except Exception as e:
        print(f"❌ 오류: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
