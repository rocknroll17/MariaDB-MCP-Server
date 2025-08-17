import asyncio
from fastmcp import Client
from fastmcp.client.transports import SSETransport
import anyio

async def call_database_list(base_url, headers, idx):
    await asyncio.sleep(0.4*idx)  # 각 요청마다 0.4초 지연
    print(f"Request {idx} 시작 - Headers: {headers}")
    
    try:
        # SSETransport에 헤더 직접 전달
        transport = SSETransport(
            url=f"{base_url}/sse",
            headers=headers
        )
        
        async with Client(transport=transport) as client:
            result = await client.call_tool("list_databases", {})
            return result
            
    except Exception as e:
        print(f"Request {idx} 에러: {e}")
        return None

async def main():
    base_url = "http://localhost:9001"  # 실제 서버 주소로 변경
    
    # 각각 다른 헤더 설정
    headers_list = ["Bearer OEqumTUGBKJc07h8ALHEFK-1TNxpVEcg8Q_qpQQq8Mk=:a27c7c5cb330e5ef14b3607d15a9bd57826344a987158b37918dd0c43db2f93b","Bearer 6CGjzWOHZKX8v_igowE5KrjqbZ_P2TFUg9iX1hL-Mik=:3df0902c4b500425aeb560dae3c26b2be01542910349d7b9a5b664722cb7f51a"]

    tasks = []
    for i in range(2):  # 2번 호출 예시
        headers = {"authorization":headers_list[i]}
        tasks.append(asyncio.create_task(call_database_list(base_url, headers, i)))
    
    results = await asyncio.gather(*tasks)
    successful_results = [r for r in results if r is not None]
    print(f"모든 요청 완료. 총 {len(successful_results)}/{len(results)}개 성공")

if __name__ == "__main__":
    anyio.run(main)