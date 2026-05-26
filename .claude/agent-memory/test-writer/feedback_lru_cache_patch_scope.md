---
name: lru_cache patch scope — TestClient 요청까지 포함해야 함
description: get_settings()처럼 @lru_cache 로 감싼 함수를 patch 할 때, TestClient.get() 호출도 반드시 patch 컨텍스트 안에 있어야 한다
type: feedback
---

`get_settings()`는 `@lru_cache(maxsize=1)` 싱글톤이다.
`patch("maria_mcp.server.get_settings", ...)` 를 `with` 블록으로 사용할 때,
앱 생성(`Starlette(...)`)만 블록 안에 두고 `client.get()` 은 밖에서 호출하면
dispatch() 실행 시점에 이미 patch가 해제되어 실제 settings를 읽는다.
→ 결과: 올바른 키를 보내도 401 반환, WARNING 로그가 엉뚱하게 찍힘.

**Why:** Starlette TestClient 는 `client.get()` 호출 시 실제 ASGI dispatch 가 실행되므로
patch가 그 시점에 활성이어야 한다.

**How to apply:** `with patch(...) as mock:` 블록 안에 `Starlette(...)`, `TestClient(...)`,
그리고 `client.get(...)` 까지 모두 포함시킨다.
```python
with patch("maria_mcp.server.get_settings", return_value=mock_settings):
    app = Starlette(routes=[...], middleware=[...])
    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/probe", headers={"X-API-Key": _TEST_API_KEY})
```
