"""
MariaDB MCP Server용 프롬프트 템플릿 모음

이 모듈은 데이터베이스 분석 및 최적화를 위한 다양한 프롬프트 템플릿을 제공합니다.
"""

def get_explain_table_prompt(table_name: str) -> str:
    """
    테이블 구조 분석을 위한 프롬프트 템플릿을 반환합니다.
    
    Args:
        table_name: 분석할 테이블명
        
    Returns:
        포맷팅된 프롬프트 문자열
    """
    return f"""DB MCP를 활용하여 데이터베이스의 {table_name} 테이블에 대해
스키마와 관계를 분석하고, 사람이 읽기 쉽게 Markdown 형식으로 설명서를 작성하세요.
해당 작업을 진행하기 전에 List_databases를 호출하여 어떤 데이터베이스에서 작업할지 확인하세요.
사용자의 코드 베이스에 백엔드 코드가 존재한다면 코드베이스와 함께 참조하여 해당 테이블의 역할을 설명해주세요.

### 출력 형식 (Markdown) (다음과 같은 형식으로 작성)

# 📋 테이블 분석: {table_name}

## 1. 테이블 개요
- **이름**: {table_name}
- **유형**: 일반
- **역할**: 청구 내역을 저장하고 결제 상태를 관리

## 2. 컬럼 분석
| 컬럼명          | 타입         | PK/FK | NULL 허용 | 기본값 | 설명 |
|----------------|--------------|-------|-----------|--------|------|
| id             | BIGINT       | PK    | NO        | -      | 고유 식별자 |
| member_id      | BIGINT       | FK    | NO        | -      | 회원 ID (member.id) |
| amount         | DECIMAL(10,2)|       | NO        | 0.00   | 청구 금액 |
| status         | TINYINT      |       | NO        | 0      | 결제 상태 (0:대기, 1:완료, 2:취소) |
...

## 3. 관계 분석
### 부모 테이블
- member (member_id) → ON DELETE CASCADE / ON UPDATE CASCADE, 청구 대상 회원 정보

### 자식 테이블
- payment (charge_id) → 결제 내역 참조

## 4. 주요 인덱스
- PK 인덱스: PRIMARY KEY (id)
- 보조 인덱스: idx_member_id (member_id) → 회원별 조회 성능 개선"""

def get_query_tuning_prompt(original_query: str) -> str:
    """
    쿼리 성능 분석을 위한 프롬프트 템플릿을 반환합니다.
    
    Args:
        original_query: 분석할 원본 쿼리
        database_name: 데이터베이스명
        optimization_focus: 최적화 중점 영역
        
    Returns:
        포맷팅된 프롬프트 문자열
    """
    return f"""당신은 MariaDB/MySQL 쿼리 성능 최적화 전문가(DBA)입니다.  
아래 쿼리에 대해 Mariadb MCP를 활용하여 **실행 계획 분석, 병목 원인, 구체적인 개선안**을 제시하세요.
해당 작업을 진행하기 전에 List_databases를 호출하여 어떤 데이터베이스에서 작업할지 확인하세요.

---

### 분석 대상 쿼리
```sql
{original_query}
```

### 1. 실행 계획 분석
- EXPLAIN 기준 각 컬럼(type, rows, key, Extra) 해석
- 병목 구간과 원인을 구체적으로 명시 (풀스캔, filesort, 임시 테이블 등)
- 대용량 테이블 환경에서 발생할 수 있는 영향 설명

### 2. 최적화 제안
- 불필요한 연산/조건 제거
- 적합한 인덱스 생성 SQL 제안
- JOIN, WHERE, GROUP BY, ORDER BY 구조 개선
- 서브쿼리를 JOIN으로 변환 가능 여부
- LIMIT나 데이터 범위 제한 적용 방안
- 만일 특정 칼럼에 index 설정이 꼭 필요하다고 여겨지는 칼럼이 있다면 제안해 볼 수 있습니다.
- 제안하기 이전에 꼭 개선된 쿼리를 실행하여 문제가 없는지 확인하세요.

### 3. 개선된 쿼리 예시
- 원본과 동일한 결과를 유지
- 성능 향상을 기대할 수 있는 개선된 쿼리문 제시

```sql
[개선된 쿼리]
```

### 4. 예상 성능 효과
- 예상 실행 시간 변화
- 검사 행수 변화
- 인덱스 사용 여부 변화

*출력 형식은 반드시 위 구조(분석 → 제안 → 개선 쿼리 → 효과)를 따르며,
기술 용어는 간결하고, DBA와 개발자 모두 이해할 수 있는 수준의 설명을 사용하세요.*
"""

def get_migration_code_prompt(table_name: str, migration_description: str) -> str:
    """
    데이터베이스 마이그레이션 가이드를 위한 프롬프트 템플릿을 반환합니다.
    변경 대상 컬럼과 ID만 선택적으로 백업하는 효율적인 마이그레이션 전략 제공
    
    Args:
        table_name: 마이그레이션할 테이블명
        migration_description: 마이그레이션 내용 설명
        
    Returns:
        포맷팅된 프롬프트 문자열
    """
    return f"""'{table_name}' 테이블의 {migration_description} 마이그레이션을 위한 SQL 작성.

## 📋 핵심 요구사항
1. **선택적 백업**: 변경 대상 컬럼 + ID만 백업 (전체 테이블 X)
2. **마이그레이션 코드**: 트랜잭션 기반 안전한 변경
3. **변경 건수 확인**: ROW_COUNT(), COUNT(*) 실시간 검증  
4. **롤백 코드**: 문제시 백업에서 복원

## 🔧 필수 출력 구조

### 1. 백업 생성
```sql
-- 변경 대상만 백업
CREATE TABLE backup_{table_name}_YYYYMMDD AS
SELECT id, target_column_1, target_column_2 FROM {table_name} 
WHERE [변경_조건];
```

### 2. 마이그레이션 실행
```sql
START TRANSACTION;
UPDATE {table_name} SET target_column = NEW_VALUE WHERE [조건];
SELECT ROW_COUNT() as changed_rows;
COMMIT; -- 또는 ROLLBACK;
```

### 3. 결과 확인
```sql
-- 변경 건수 검증
SELECT COUNT(*) as migrated_count FROM {table_name} WHERE target_column = 'NEW_VALUE';
```

### 4. 롤백 방법
```sql
-- 문제시 복원
UPDATE {table_name} t 
JOIN backup_{table_name}_YYYYMMDD b ON t.id = b.id 
SET t.target_column = b.target_column;
```
"""
