# Node verification: api_routes
# Edge verification: CORS headers present; response shapes match schema
def test_list_todos_empty(client):
    r = client.get("/todos")
    assert r.status_code == 200
    assert r.json() == []


def test_create_todo(client):
    r = client.post("/todos", json={"title": "buy milk"})
    assert r.status_code == 201
    body = r.json()
    assert body["title"] == "buy milk"
    assert body["completed"] is False
    assert isinstance(body["id"], int)


def test_create_todo_empty_title_rejected(client):
    r = client.post("/todos", json={"title": ""})
    assert r.status_code == 422


def test_list_todos_returns_created(client):
    client.post("/todos", json={"title": "a"})
    client.post("/todos", json={"title": "b"})
    r = client.get("/todos")
    assert r.status_code == 200
    assert len(r.json()) == 2


def test_toggle_todo(client):
    todo_id = client.post("/todos", json={"title": "buy milk"}).json()["id"]
    r = client.put(f"/todos/{todo_id}", json={"completed": True})
    assert r.status_code == 200
    assert r.json()["completed"] is True


def test_toggle_todo_not_found(client):
    r = client.put("/todos/999", json={"completed": True})
    assert r.status_code == 404


def test_delete_todo(client):
    todo_id = client.post("/todos", json={"title": "buy milk"}).json()["id"]
    r = client.delete(f"/todos/{todo_id}")
    assert r.status_code == 204
    assert client.get("/todos").json() == []


def test_delete_todo_not_found(client):
    r = client.delete("/todos/999")
    assert r.status_code == 404


# Edge verification: CORS headers present
def test_cors_headers(client):
    r = client.get("/todos", headers={"Origin": "http://localhost:5173"})
    assert "access-control-allow-origin" in r.headers
