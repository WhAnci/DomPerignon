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
| `lambda_secrets_manager.py` | GET, POST, PUT, PATCH, DELETE | Secrets Manager로 DB 자격 증명 관리 |

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

## Secrets Manager로 DB 자격 증명 관리

환경 변수에 평문 비밀번호를 넣는 대신, Secrets Manager에 저장하고 Lambda에서 불러오는 방식입니다.  
`lambda_secrets_manager.py` 가 이 패턴을 사용합니다.

### Secret 형식 (JSON)

Secrets Manager에 아래 형식의 JSON으로 시크릿을 저장합니다.

```json
{
  "host":     "your-rds-endpoint.rds.amazonaws.com",
  "port":     3306,
  "username": "admin",
  "password": "yourpassword",
  "dbname":   "mydb"
}
```

### 코드 패턴

```python
import json
import boto3

_SECRET_CACHE = None  # 콜드 스타트 이후 재사용 (웜 스타트 캐싱)

def get_secret() -> dict:
    global _SECRET_CACHE
    if _SECRET_CACHE is not None:
        return _SECRET_CACHE

    client = boto3.client('secretsmanager', region_name='ap-northeast-2')
    response = client.get_secret_value(SecretId='prod/myapp/mysql')
    _SECRET_CACHE = json.loads(response['SecretString'])
    return _SECRET_CACHE

secret = get_secret()
```

> 💡 `_SECRET_CACHE` 를 모듈 레벨에 두면 Lambda 컨테이너가 **웜 스타트**될 때 Secrets Manager API를 매번 호출하지 않아 비용과 레이턴시를 줄일 수 있습니다.

### 환경 변수 설정

기존 `RDS_*` 환경 변수 대신 아래 하나만 설정하면 됩니다.

```
SECRET_ID     Secrets Manager 시크릿 이름 또는 ARN
              예) prod/myapp/mysql
```

### 필요한 IAM 권한

Lambda 실행 Role에 아래 인라인 정책을 추가합니다.

```json
{
  "Effect": "Allow",
  "Action": [
    "secretsmanager:GetSecretValue",
    "secretsmanager:DescribeSecret"
  ],
  "Resource": "arn:aws:secretsmanager:ap-northeast-2:<ACCOUNT_ID>:secret:prod/myapp/mysql-*"
}
```

> ⚠️ `Resource` 에 `*` 대신 특정 Secret ARN(또는 접두사+와일드카드)을 지정하는 것이 최소 권한 원칙에 맞습니다.

---

## 참고

- `pymysql` 은 Lambda Layer 또는 배포 패키지에 포함해야 합니다.
- 각 파일 상단의 `★ 수정 포인트 ★` 섹션만 변경하면 바로 사용 가능합니다.
