# MCP MariaDB 서버

MCP MariaDB 서버는 표준 SQL 작업을 모두 지원하며, MariaDB 데이터베이스를 관리하고 쿼리하기 위한 MCP(Model Context Protocol) 인터페이스를 제공합니다.

---

## 목차

- [개요](#개요)
- [핵심 구성 요소](#핵심-구성-요소)
- [사용 가능한 도구](#사용-가능한-도구)
- [구성 및 환경 변수](#구성-및-환경-변수)
- [설정](#설정)
- [통합 - Claude desktop/Cursor/Windsurf/VS Code](#통합---claude-desktopcursorwindsurfvs-code)
- [로깅](#로깅)
- [테스트](#테스트)

---

## 개요

MCP MariaDB 서버는 표준화된 프로토콜을 통해 MariaDB 데이터베이스와 상호 작용하기 위한 도구 세트를 제공합니다. 다음을 지원합니다:

- 데이터베이스 및 테이블 목록 조회
- 테이블 스키마 검색
- 안전한 읽기 전용 SQL 쿼리 실행
- EXPLAIN 및 EXPLAIN EXTENDED를 사용한 쿼리 성능 분석
- LLM이 스스로 사용법을 학습할 수 있도록 돕는 포괄적인 도구 사용 가이드

---

## 핵심 구성 요소

- **config.py**: 환경 및 `.env` 파일에서 구성을 로드합니다.
- **logger.py**: MCP 서버의 로깅을 구성합니다.
- **main.py**: MCP 서버 실행을 위한 진입점입니다.
- **server.py**: 기본 MCP 서버 로직 및 도구 정의가 포함되어 있습니다.
- **tests/**: 수동 및 자동 테스트 문서와 스크립트가 포함되어 있습니다.

---

## 사용 가능한 도구

### 표준 데이터베이스 도구

- **list_databases**
    - 접근 가능한 모든 데이터베이스 목록을 조회합니다.
    - 매개변수: _없음_

- **list_tables**
    - 지정된 데이터베이스의 모든 테이블 목록을 조회합니다.
- **list_tables**
    - 지정된 데이터베이스의 모든 테이블 목록을 조회합니다.
    - 매개변수: `database_name` (문자열, 필수)

- **get_table_schema**
    - 테이블의 스키마(열, 유형, 키 등)를 검색합니다.
    - 매개변수: `database_name` (문자열, 필수), `table_name` (문자열, 필수)

- **execute_sql**
    - 읽기 전용 SQL 쿼리(`SELECT`, `SHOW`, `DESCRIBE`)를 실행합니다.
    - 매개변수: `sql_query` (문자열, 필수), `database_name` (문자열, 선택 사항), `parameters` (리스트, 선택 사항)
    - _참고: `MCP_READ_ONLY`가 활성화된 경우 읽기 전용 모드가 강제됩니다._
- **create_database**
    - 존재하지 않는 경우 새 데이터베이스를 생성합니다.
    - 매개변수: `database_name` (문자열, 필수)

### 쿼리 성능 분석 도구

- **explain_query**
    - SQL 쿼리에 대해 EXPLAIN을 실행하여 성능 분석을 위한 실행 계획을 보여줍니다.
    - 매개변수: `sql_query` (문자열, 필수), `database_name` (문자열, 필수), `parameters` (리스트, 선택 사항)
    - _참고: 쿼리 성능 분석 및 최적화 기회를 파악하는 데 도움이 됩니다. 실제 쿼리를 실행하지는 않습니다._

- **explain_query_extended**
    - SQL 쿼리에 대해 EXPLAIN EXTENDED를 실행하여 추가 정보가 포함된 상세 실행 계획을 보여줍니다.
    - 매개변수: `sql_query` (문자열, 필수), `database_name` (문자열, 필수), `parameters` (리스트, 선택 사항)
    - _참고: 필터링된 행 비율 및 추가 최적화 세부 정보를 포함한 포괄적인 분석을 제공합니다._

### 도구 검색 및 사용 가이드

**! 참고: LLM이 이 도구를 이해하도록 프롬프트를 제공해야 합니다**  
`예시: "먼저 MCP 도구 사용법을 이해하는 데 도움이 되는 get_usage_guide 도구가 있습니다."`

- **get_usage_guide**
    - 예제와 모범 사례를 포함하여 사용 가능한 모든 MCP 도구에 대한 포괄적인 사용 가이드를 제공합니다.
    - 매개변수: _없음_

---

## 구성 및 환경 변수

모든 구성은 환경 변수(일반적으로 `.env` 파일에 설정)를 통해 이루어집니다:

| 변수                | 설명                                                            | 필수   | 기본값      |
| ------------------- | --------------------------------------------------------------- | ------ | ----------- |
| `DB_HOST`           | MariaDB 호스트 주소                                             | 예     | `localhost` |
| `DB_PORT`           | MariaDB 포트                                                    | 아니요 | `3306`      |
| `DB_USER`           | MariaDB 사용자 이름                                             | 예     |             |
| `DB_PASSWORD`       | MariaDB 비밀번호                                                | 예     |             |
| `DB_NAME`           | 기본 데이터베이스 (선택 사항; 쿼리별로 설정 가능)               | 아니요 |             |
| `MCP_READ_ONLY`     | 읽기 전용 SQL 모드 강제 (`true`/`false`)                        | 아니요 | `true`      |
| `MCP_MAX_POOL_SIZE` | 최대 DB 연결 풀 크기                                            | 아니요 | `10`        |
| `MCP_AUTH_ENABLED`  | MCP 인증 활성화 (`true`/`false`)                                | 아니요 | `false`     |
| `ENCRYPTION_KEY`    | 사용자 ID 암호화용 키 (32바이트)                                | 아니요 |             |
| `SIGNING_KEY`       | 토큰 서명용 키 (`MCP_AUTH_ENABLED=true`인 경우 필수)            | 아니요 |             |
| `API_KEYS`          | 인증용 API 키의 JSON 배열 (`MCP_AUTH_ENABLED=true`인 경우 필수) | 아니요 | `[]`        |

#### 예제 `.env` 파일

```dotenv
DB_HOST=localhost
DB_USER=your_db_user
DB_PASSWORD=your_db_password
DB_PORT=3306
DB_NAME=your_default_database

MCP_READ_ONLY=true
MCP_MAX_POOL_SIZE=10

MCP_AUTH_ENABLED=true
ENCRYPTION_KEY=EmL8QakI4j4W...
SIGNING_KEY=key...
API_KEYS=["WSgFMWo_0_ThMDQ....","JTFtQBTFE825iVbohnR...."]
```

---

# 설정

## MariaDB가 Docker를 사용하지 않는 경우 (로컬 머신이나 원격 서버에 설치된 경우)

### MCP 서버 빌드
```bash
docker build -t mcp-server .
````

### MCP 서버 컨테이너 실행

```bash
docker run -d \
  --name mcp-server \
  -e DB_HOST={mariadb-hostname-or-ip} \
  -e DB_USER={mariadb-username} \
  -e DB_PASSWORD={mariadb-password} \
  -e DB_PORT=3306 \
  -e DB_NAME={mariadb-database-name} \
  -e MCP_READ_ONLY=true \
  -e MCP_MAX_POOL_SIZE=10 \
  -e MCP_AUTH_ENABLED=true \
  -e ENCRYPTION_KEY={your-32-byte-encryption-key} \
  -e SIGNING_KEY={your-signing-key} \
  -e API_KEYS='["{your-api-key-1}","{your-api-key-2}"]' \
  -p 9001:9001 \
  mcp-server
```

## Docker로 MariaDB를 사용하는 경우

### MariaDB와 MCP 서버 연결을 위한 네트워크 생성

```bash
docker network create mariadb-mcp-network
docker network connect mariadb-mcp-network {mariadb-container-name}
```

### MCP 서버용 Docker 이미지 빌드

```bash
docker build -t mcp-server .
```

### MCP 서버 컨테이너 실행

```bash
docker run -d \
  --name mcp-server \
  --network mariadb-mcp-network \
  -e DB_HOST={mariadb-container-name} \
  -e DB_USER={mariadb-username} \
  -e DB_PASSWORD={mariadb-password} \
  -e DB_PORT=3306 \
  -e DB_NAME={mariadb-database-name} \
  -e MCP_READ_ONLY=true \
  -e MCP_MAX_POOL_SIZE=10 \
  -e MCP_AUTH_ENABLED=true \
  -e ENCRYPTION_KEY={your-32-byte-encryption-key} \
  -e SIGNING_KEY={your-signing-key} \
  -e API_KEYS='["{your-api-key-1}","{your-api-key-2}"]' \
  -p 9001:9001 \
  mcp-server
```

---

## Docker 없이 MCP 서버 실행

Docker 없이 MCP 서버를 실행하려면 다음 단계를 따르세요:

1. `.env` 설정 (위의 예제 참조):
    - MariaDB 연결 세부 정보가 포함된 `.env` 파일을 `src/` 디렉토리에 생성하세요.
    - 필요한 환경 변수가 설정되어 있는지 확인하세요.
2. 의존성 설치:

```bash
  python3 -m venv venv
  source venv/bin/activate
  pip install uv
  uv pip compile pyproject.toml -o uv.lock
  uv pip sync uv.lock
```

3. MCP 서버 실행:
    ```bash
    python src/main.py
    ```

---

## 통합 - Claude desktop/Cursor/Windsurf/VS Code

### VS Code -> `.vscode/mcp.json`

```json
{
    "servers": {
        "mariadb-mcp-server": {
            "url": "http://localhost:9001/sse/",
            "type": "sse",
            "headers": {
                "Authorization": "Bearer {your-api-key}"
            }
        }
    }
}
```

### Cursor -> `~/.cursor/mcp.json`

```json
{
    "servers": {
        "mariadb-mcp-server": {
            "url": "http://localhost:9001/sse/",
            "type": "sse",
            "headers": {
                "Authorization": "Bearer {your-api-key}"
            }
        }
    }
}
```

### Claude Code

```
claude mcp add-json mariadb-mcp-server '{"url": "http://localhost:9001/sse/","type": "sse","headers": {"Authorization": "Bearer {your-api-key}"}}'
```

---

## 로깅

- 로그는 기본적으로 `logs/application.log`에 기록됩니다.
- 로그 메시지에는 도구 호출, 구성 문제, 임베딩 오류 및 클라이언트 요청이 포함됩니다.
- 로그 레벨과 출력은 코드에서 조정할 수 있습니다(`config.py` 및 로거 설정 참조).

---

## 테스트

- 테스트는 `src/tests/` 디렉토리에 위치합니다.
- 개요는 `src/tests/README.md`를 참조하세요.
- 테스트는 표준 SQL 및 벡터/임베딩 도구 작업을 모두 다룹니다.
- 로그 수준 및 출력은 코드에서 조정할 수 있습니다 (`config.py` 및 로거 설정 참조).

