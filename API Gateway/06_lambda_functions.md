# 06. Lambda 함수 구현 패턴

> 과제에서 자주 등장하는 함수 구조를 단계별로 정리

---

## 공통 패턴

### DB 연결 (Lambda 외부 초기화)

```python
import json
import pymysql
import os

# Lambda 컨테이너 재사용 시 DB 연결 재활용 (Cold Start 최소화)
conn = None

def get_connection():
    global conn
    if conn is None or not conn.open:
        conn = pymysql.connect(
            host=os.environ['RDS_HOST'],
            port=int(os.environ.get('RDS_PORT', 3306)),
            user=os.environ['RDS_USER'],
            password=os.environ['RDS_PASSWORD'],
            db=os.environ['RDS_DB'],
            charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor
        )
    return conn
```

### 응답 헬퍼

```python
def _response(status_code, body):
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
        },
        "body": json.dumps(body, default=str)
    }
```

---

## function 1 — 조회 (GET)

| 메서드 | 경로 | 설명 |
|--------|------|----- |
| GET | /item | 전체 조회 |
| GET | /item?id=\<id\> | 단일 조회 |

```python
def lambda_handler(event, context):
    method = event['httpMethod']
    params = event.get('queryStringParameters') or {}
    
    if method == 'GET':
        item_id = params.get('id')
        conn = get_connection()
        with conn.cursor() as cur:
            if item_id:
                cur.execute("SELECT * FROM items WHERE id=%s", (item_id,))
                row = cur.fetchone()
                return _response(200, row) if row else _response(404, {"message": "Not Found"})
            else:
                cur.execute("SELECT * FROM items")
                return _response(200, cur.fetchall())
```

---

## function 2 — 생성 추가 (POST)

```python
import uuid
from datetime import datetime

# POST /item
body = json.loads(event.get('body') or '{}')
item_id = str(uuid.uuid4())
created_at = datetime.utcnow().isoformat()

with conn.cursor() as cur:
    cur.execute(
        "INSERT INTO items (id, name, category, price, created_at) VALUES (%s, %s, %s, %s, %s)",
        (item_id, body['name'], body['category'], body['price'], created_at)
    )
    conn.commit()
return _response(201, {"id": item_id})
```

---

## function 3 — 수정 추가 (PUT / PATCH)

```python
# PUT: 전체 필드 교체 (id, created_at 제외)
# PATCH: 전달된 필드만 수정

body = json.loads(event.get('body') or '{}')
item_id = params.get('id')

if method == 'PUT':
    cur.execute(
        "UPDATE items SET name=%s, category=%s, price=%s WHERE id=%s",
        (body['name'], body['category'], body['price'], item_id)
    )
elif method == 'PATCH':
    # 동적 UPDATE 쿼리 생성
    allowed = {'name', 'category', 'price'}
    updates = {k: v for k, v in body.items() if k in allowed}
    if not updates:
        return _response(400, {"message": "수정할 필드 없음"})
    set_clause = ", ".join(f"{k}=%s" for k in updates)
    values = list(updates.values()) + [item_id]
    cur.execute(f"UPDATE items SET {set_clause} WHERE id=%s", values)

conn.commit()
```

---

## function 4 — updated_at 자동 갱신

```python
# 생성 시: updated_at = created_at
# 수정 시: updated_at = 현재 시각

updated_at = datetime.utcnow().isoformat()
cur.execute(
    "UPDATE items SET name=%s, category=%s, price=%s, updated_at=%s WHERE id=%s",
    (body['name'], body['category'], body['price'], updated_at, item_id)
)
```

---

## function 5 — 필터 + 페이지네이션

```python
# Query Parameters: category, price_lt, price_gt, limit, offset

where = []
values = []

if params.get('category'):
    where.append("category = %s")
    values.append(params['category'])
if params.get('price_lt'):
    where.append("price < %s")
    values.append(int(params['price_lt']))
if params.get('price_gt'):
    where.append("price > %s")
    values.append(int(params['price_gt']))

where_clause = ("WHERE " + " AND ".join(where)) if where else ""
limit = int(params.get('limit', 10))
offset = int(params.get('offset', 0))

query = f"SELECT * FROM items {where_clause} LIMIT %s OFFSET %s"
values += [limit, offset]
```

---

## function 6 — 삭제 추가 (DELETE) → CRUD 완성

```python
# DELETE /item?id=<uuid>

item_id = params.get('id')
if not item_id:
    return _response(400, {"message": "id 필수"})

with conn.cursor() as cur:
    cur.execute("DELETE FROM items WHERE id=%s", (item_id,))
    if cur.rowcount == 0:
        return _response(404, {"message": "Not Found"})
    conn.commit()

return _response(200, {"message": "삭제 완료", "id": item_id})
```

---

## 에러 처리 패턴

```python
def lambda_handler(event, context):
    try:
        # ... 로직
    except KeyError as e:
        return _response(400, {"message": f"필수 필드 누락: {str(e)}"})
    except pymysql.MySQLError as e:
        return _response(500, {"message": f"DB 오류: {str(e)}"})
    except Exception as e:
        return _response(500, {"message": f"서버 오류: {str(e)}"})
```
