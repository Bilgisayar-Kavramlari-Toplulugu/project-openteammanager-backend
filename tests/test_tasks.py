import pytest


# --- Görev Oluşturma ---

@pytest.mark.asyncio
async def test_create_task_success(auth_client, org, project):
    response = await auth_client.post(
        f"/api/v1/organizations/{org['id']}/projects/{project['id']}/tasks",
        json={"title": "My Task", "priority": "high"}
    )
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "My Task"
    assert data["priority"] == "high"
    assert data["status"] == "todo"
    assert data["task_number"] == 1
    assert "id" in data
    assert "position" in data


@pytest.mark.asyncio
async def test_create_task_number_increments(auth_client, org, project):
    """task_number her yeni görevde 1 artmalı."""
    await auth_client.post(
        f"/api/v1/organizations/{org['id']}/projects/{project['id']}/tasks",
        json={"title": "Task 1"}
    )
    response = await auth_client.post(
        f"/api/v1/organizations/{org['id']}/projects/{project['id']}/tasks",
        json={"title": "Task 2"}
    )
    assert response.json()["task_number"] == 2


@pytest.mark.asyncio
async def test_create_task_position_increments(auth_client, org, project):
    """Aynı status'taki ikinci görev daha büyük position almalı."""
    r1 = await auth_client.post(
        f"/api/v1/organizations/{org['id']}/projects/{project['id']}/tasks",
        json={"title": "Task 1", "status": "todo"}
    )
    r2 = await auth_client.post(
        f"/api/v1/organizations/{org['id']}/projects/{project['id']}/tasks",
        json={"title": "Task 2", "status": "todo"}
    )
    assert r2.json()["position"] > r1.json()["position"]


@pytest.mark.asyncio
async def test_create_task_with_parent(auth_client, org, project, task):
    """Alt görev oluşturulabilmeli."""
    response = await auth_client.post(
        f"/api/v1/organizations/{org['id']}/projects/{project['id']}/tasks",
        json={"title": "Sub Task", "parent_id": task["id"]}
    )
    assert response.status_code == 201
    assert response.json()["parent_id"] == task["id"]


@pytest.mark.asyncio
async def test_create_task_forbidden_non_member(outsider_client, org, project):
    """Proje üyesi olmayan kullanıcı görev oluşturamaz."""

    response = await outsider_client.post(
        f"/api/v1/organizations/{org['id']}/projects/{project['id']}/tasks",
        json={"title": "Hacked Task"}
    )
    assert response.status_code == 403


# --- Görev Listeleme ---

@pytest.mark.asyncio
async def test_list_tasks(auth_client, org, project, task):
    response = await auth_client.get(
        f"/api/v1/organizations/{org['id']}/projects/{project['id']}/tasks"
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    assert any(t["title"] == "Test Task" for t in data)


@pytest.mark.asyncio
async def test_list_tasks_filter_by_status(auth_client, org, project):
    """Status filtrelemesi doğru çalışmalı."""
    await auth_client.post(
        f"/api/v1/organizations/{org['id']}/projects/{project['id']}/tasks",
        json={"title": "Todo Task", "status": "todo"}
    )
    await auth_client.post(
        f"/api/v1/organizations/{org['id']}/projects/{project['id']}/tasks",
        json={"title": "In Progress Task", "status": "in_progress"}
    )
    response = await auth_client.get(
        f"/api/v1/organizations/{org['id']}/projects/{project['id']}/tasks",
        params={"status": "todo"}
    )
    assert response.status_code == 200
    data = response.json()
    assert all(t["status"] == "todo" for t in data)


@pytest.mark.asyncio
async def test_list_tasks_filter_by_assignee(auth_client, org, project):
    """Atanan filtresi doğru çalışmalı."""
    me = (await auth_client.get("/api/v1/auth/me")).json()

    await auth_client.post(
        f"/api/v1/organizations/{org['id']}/projects/{project['id']}/tasks",
        json={"title": "Assigned Task", "assignee_id": me["id"]}
    )
    await auth_client.post(
        f"/api/v1/organizations/{org['id']}/projects/{project['id']}/tasks",
        json={"title": "Unassigned Task"}
    )
    response = await auth_client.get(
        f"/api/v1/organizations/{org['id']}/projects/{project['id']}/tasks",
        params={"assignee_id": me["id"]}
    )
    assert response.status_code == 200
    data = response.json()
    assert all(t["assignee_id"] == me["id"] for t in data)


# --- Görev Detay ---

@pytest.mark.asyncio
async def test_get_task_success(auth_client, org, project, task):
    response = await auth_client.get(
        f"/api/v1/organizations/{org['id']}/projects/{project['id']}/tasks/{task['id']}"
    )
    assert response.status_code == 200
    assert response.json()["id"] == task["id"]


@pytest.mark.asyncio
async def test_get_task_not_found(auth_client, org, project):
    fake_id = "00000000-0000-0000-0000-000000000000"
    response = await auth_client.get(
        f"/api/v1/organizations/{org['id']}/projects/{project['id']}/tasks/{fake_id}"
    )
    assert response.status_code == 404


# --- Görev Güncelleme ---

@pytest.mark.asyncio
async def test_update_task_success(auth_client, org, project, task):
    response = await auth_client.patch(
        f"/api/v1/organizations/{org['id']}/projects/{project['id']}/tasks/{task['id']}",
        json={"title": "Updated Task", "priority": "critical"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Updated Task"
    assert data["priority"] == "critical"


@pytest.mark.asyncio
async def test_update_task_status_to_done_sets_completed_at(auth_client, org, project, task):
    """Status done yapılınca completed_at set edilmeli."""
    response = await auth_client.patch(
        f"/api/v1/organizations/{org['id']}/projects/{project['id']}/tasks/{task['id']}",
        json={"status": "done"}
    )
    assert response.status_code == 200
    assert response.json()["completed_at"] is not None


@pytest.mark.asyncio
async def test_update_task_status_from_done_clears_completed_at(auth_client, org, project, task):
    """Status done'dan başka bir duruma alınınca completed_at temizlenmeli."""
    await auth_client.patch(
        f"/api/v1/organizations/{org['id']}/projects/{project['id']}/tasks/{task['id']}",
        json={"status": "done"}
    )
    response = await auth_client.patch(
        f"/api/v1/organizations/{org['id']}/projects/{project['id']}/tasks/{task['id']}",
        json={"status": "in_progress"}
    )
    assert response.status_code == 200
    assert response.json()["completed_at"] is None


# --- Görev Taşıma (Kanban) ---

@pytest.mark.asyncio
async def test_move_task_changes_status(auth_client, org, project, task):
    """Görev taşıma status'u değiştirmeli."""
    response = await auth_client.patch(
        f"/api/v1/organizations/{org['id']}/projects/{project['id']}/tasks/{task['id']}/move",
        json={"status": "in_progress", "position": 1000.0}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "in_progress"
    assert data["position"] == 1000.0


@pytest.mark.asyncio
async def test_move_task_to_done_sets_completed_at(auth_client, org, project, task):
    """Bitmiş görev taşınınca completed_at set edilmeli."""
    response = await auth_client.patch(
        f"/api/v1/organizations/{org['id']}/projects/{project['id']}/tasks/{task['id']}/move",
        json={"status": "done", "position": 1000.0}
    )
    assert response.status_code == 200
    assert response.json()["completed_at"] is not None


@pytest.mark.asyncio
async def test_rebalance_positions(auth_client, org, project):
    """Pozisyonlar çok yaklaşınca rebalance yapılmalı."""
    r1 = await auth_client.post(
        f"/api/v1/organizations/{org['id']}/projects/{project['id']}/tasks",
        json={"title": "Task A", "status": "todo"}
    )
    r2 = await auth_client.post(
        f"/api/v1/organizations/{org['id']}/projects/{project['id']}/tasks",
        json={"title": "Task B", "status": "todo"}
    )
    pos1 = r1.json()["position"]
    pos2 = r2.json()["position"]

    # İki görev arasına çok yakın pozisyonla taşı
    await auth_client.patch(
        f"/api/v1/organizations/{org['id']}/projects/{project['id']}/tasks/{r2.json()['id']}/move",
        json={"status": "todo", "position": pos1 + 0.0001}
    )

    # Rebalance sonrası pozisyonlar 1000'in katı olmalı
    response = await auth_client.get(
        f"/api/v1/organizations/{org['id']}/projects/{project['id']}/tasks",
        params={"status": "todo"}
    )
    positions = [t["position"] for t in response.json()]
    assert all(p % 1000 == 0 for p in positions)


# --- Görev Silme ---

@pytest.mark.asyncio
async def test_delete_task_success(auth_client, org, project, task):
    response = await auth_client.delete(
        f"/api/v1/organizations/{org['id']}/projects/{project['id']}/tasks/{task['id']}"
    )
    assert response.status_code == 204

    get_response = await auth_client.get(
        f"/api/v1/organizations/{org['id']}/projects/{project['id']}/tasks/{task['id']}"
    )
    assert get_response.status_code == 404


@pytest.mark.asyncio
async def test_list_tasks_filter_by_label(auth_client, org, project):
    """Etiket filtrelemesi doğru çalışmalı."""
    await auth_client.post(
        f"/api/v1/organizations/{org['id']}/projects/{project['id']}/tasks",
        json={"title": "Bug Task", "labels": ["bug", "backend"]}
    )
    await auth_client.post(
        f"/api/v1/organizations/{org['id']}/projects/{project['id']}/tasks",
        json={"title": "Feature Task", "labels": ["feature"]}
    )
    response = await auth_client.get(
        f"/api/v1/organizations/{org['id']}/projects/{project['id']}/tasks",
        params={"label": "bug"}
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["title"] == "Bug Task"