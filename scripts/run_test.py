#!/usr/bin/env python3
"""
데이터베이스 테스트 스크립트

독립적으로 실행 가능한 테스트 러너
"""

import sys
import asyncio
from pathlib import Path

# 프로젝트 src 경로를 추가
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

async def run_database_test():
    """데이터베이스 동시성 테스트 실행"""
    import aiohttp
    import time
    
    url = "http://localhost:9001"
    headers = {"Content-Type": "application/json"}
    
    # JSON-RPC 요청 페이로드
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": "mcp_mariadb-mcp-s_list_databases",
            "arguments": {}
        }
    }
    
    print("🚀 데이터베이스 동시성 테스트 시작...")
    print("📡 0.2초 간격으로 동시 요청을 보냅니다...\n")
    
    async def send_request(session, req_id):
        start_time = time.time()
        payload_copy = payload.copy()
        payload_copy["id"] = req_id
        
        print(f"📤 요청 {req_id} 전송...")
        
        async with session.post(url, json=payload_copy, headers=headers) as response:
            result = await response.json()
            end_time = time.time()
            duration = end_time - start_time
            
            print(f"📥 요청 {req_id} 응답 완료 (소요시간: {duration:.2f}초)")
            return result
    
    async with aiohttp.ClientSession() as session:
        # 동시에 여러 요청 보내기
        tasks = []
        for i in range(1, 6):  # 5개 요청
            task = send_request(session, i)
            tasks.append(task)
        
        start_total = time.time()
        results = await asyncio.gather(*tasks)
        end_total = time.time()
        
        print(f"\n✅ 모든 요청 완료!")
        print(f"⏱️  총 소요시간: {end_total - start_total:.2f}초")
        print(f"📊 평균 응답시간: {(end_total - start_total)/len(tasks):.2f}초")
        
        # 결과 요약
        for i, result in enumerate(results, 1):
            if "result" in result:
                db_count = len(result["result"])
                print(f"   요청 {i}: {db_count}개 데이터베이스 조회됨")
            else:
                print(f"   요청 {i}: 오류 발생 - {result}")

def main():
    try:
        asyncio.run(run_database_test())
        return 0
    except KeyboardInterrupt:
        print("\n⚠️ 사용자에 의해 중단되었습니다.")
        return 1
    except Exception as e:
        print(f"❌ 오류: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
