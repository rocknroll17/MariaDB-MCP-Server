#!/usr/bin/env python3
"""
API 키 생성 스크립트

독립적으로 실행 가능한 API 키 생성기
"""

import sys
import argparse
from pathlib import Path

# 프로젝트 src 경로를 추가
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

from core.factory import service_factory

def main():
    parser = argparse.ArgumentParser(description="API 키 생성기")
    parser.add_argument("user_id", help="사용자 ID")
    parser.add_argument("--output", "-o", help="결과를 파일로 저장")
    
    args = parser.parse_args()
    
    try:
        # 팩토리에서 서비스 가져오기
        auth_service = service_factory.auth_service
        api_key = auth_service.generate(args.user_id)
        
        result = f"User ID: {args.user_id}\nAPI Key: {api_key}"
        
        if args.output:
            with open(args.output, 'w') as f:
                f.write(result)
            print(f"✅ 결과가 {args.output}에 저장되었습니다.")
        else:
            print("==============================")
            print("  ✅ API KEY 생성 결과")
            print("------------------------------")
            print(result)
            print("==============================")
        
        return 0
        
    except Exception as e:
        print(f"❌ 오류: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
