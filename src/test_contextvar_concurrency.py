import asyncio
from contextvars import ContextVar
from typing import Optional

# 테스트용 ContextVar
test_user_id: ContextVar[Optional[str]] = ContextVar('test_user_id', default=None)

async def simulate_request(user_id: str, delay: float):
    """요청 시뮬레이션"""
    print(f"[{user_id}] 요청 시작")
    
    # 사용자 ID 설정
    test_user_id.set(user_id)
    print(f"[{user_id}] ContextVar 설정 완료: {test_user_id.get()}")
    
    # 처리 시간 시뮬레이션
    await asyncio.sleep(delay)
    
    # 처리 완료 후 확인
    current_user = test_user_id.get()
    print(f"[{user_id}] 처리 완료. 현재 ContextVar: {current_user}")
    
    # 정확성 검증
    if current_user == user_id:
        print(f"✅ [{user_id}] 성공: ContextVar가 올바르게 유지됨")
    else:
        print(f"❌ [{user_id}] 실패: 예상={user_id}, 실제={current_user}")

async def test_concurrency():
    """동시성 테스트"""
    print("=== ContextVar 동시성 테스트 시작 ===")
    
    # 동시에 여러 요청 실행
    tasks = [
        simulate_request("alice", 0.3),
        simulate_request("bob", 0.1),
        simulate_request("charlie", 0.2),
    ]
    
    await asyncio.gather(*tasks)
    print("=== 테스트 완료 ===")

# 테스트 실행
if __name__ == "__main__":
    asyncio.run(test_concurrency())
