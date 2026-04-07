# Lambda Function Examples

AWS Lambda + API Gateway + RDS(MySQL) 연동 예제 모음입니다.  
각 파일은 기능을 단계적으로 추가하는 구조로, 필요한 수준의 파일을 선택해 사용하세요.

---

## 파일 목록

| 파일 | 지원 메서드 | 추가 기능 |
|------|------------|----------|
| `lambda_function_1.py` | GET | 단건/전체 조회 |
| `lambda_function_2.py` | GET, POST | 생성 추가 |
| `lambda_function_3.py` | GET, POST, PUT, PATCH | 전체/부분 수정 추가 |
| `lambda_function_4.py` | GET, POST, PUT, PATCH | `updated_at` 자동 갱신 추가 |
| `lambda_function_5.py` | GET, POST, PUT | 필터 + 페이지네이션 추가 |
| `lambda_function_6.py` | GET, POST, PUT, PATCH, DELETE | 완전한 CRUD + 필터/페이지네이션 |
| `lambda_function_7.py` | GET, POST, PUT, PATCH, DELETE | Soft Delete (`is_deleted` 플래그) |
| `lambda_function_8.py` | GET, POST(Bulk), DELETE(Bulk) | 배치 생성 / 배치 삭제 |

---

## 공통 환경 변수

```
RDS_HOST      RDS 엔드포인트
RDS_PORT      포트 (기본값: 3306)
RDS_USER      DB 사용자
RDS_PASSWORD  DB 패스워드
RDS_DB        데이터베이스 이름
```

---

## ID 추출 방식

`ID_SOURCE` 상수로 `"query"` / `"path"` 중 선택합니다.

| 방식 | 예시 |
|------|------|
| `query` | `GET /item?id=<id>` |
| `path`  | `GET /item/<id>` (API Gateway 리소스: `/item/{id}` 필요) |

---

## 참고

- `pymysql` 은 Lambda Layer 또는 배포 패키지에 포함해야 합니다.
- 각 파일 상단의 `★ 수정 포인트 ★` 섹션만 변경하면 바로 사용 가능합니다.
