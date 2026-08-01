from ohwang.tools.tasks import (
    TaskCreateTool,
    TaskGetTool,
    TaskListTool,
    TaskOutputTool,
    TaskStopTool,
    TaskStore,
    TaskUpdateTool,
)


def _make_store(tmp_path):
    return TaskStore(tmp_path)


def test_task_create_get(tmp_path):
    store = _make_store(tmp_path)
    task = store.create("写周报", "整理本周进展")
    assert task["status"] == "pending"
    assert task["id"].startswith("task-")
    got = store.get(task["id"])
    assert got["title"] == "写周报"
    assert got["description"] == "整理本周进展"


def test_task_list_and_filter(tmp_path):
    store = _make_store(tmp_path)
    t1 = store.create("任务一")
    store.update(t1["id"], status="completed")
    t2 = store.create("任务二")
    assert len(store.list()) == 2
    completed = [t for t in store.list() if t["status"] == "completed"]
    assert len(completed) == 1


def test_task_update_status_and_output(tmp_path):
    store = _make_store(tmp_path)
    t = store.create("分析数据")
    updated = store.update(t["id"], status="completed", output="结论：增长18%")
    assert updated["status"] == "completed"
    assert updated["output"] == "结论：增长18%"


def test_task_invalid_status_ignored(tmp_path):
    store = _make_store(tmp_path)
    t = store.create("任务")
    updated = store.update(t["id"], status="bogus")
    assert updated["status"] == "pending"


def test_task_remove(tmp_path):
    store = _make_store(tmp_path)
    t = store.create("临时任务")
    assert store.remove(t["id"]) is True
    assert store.get(t["id"]) is None
    assert store.remove(t["id"]) is False


def test_task_store_persists_across_instances(tmp_path):
    store1 = _make_store(tmp_path)
    t = store1.create("持久任务")
    store2 = _make_store(tmp_path)
    assert store2.get(t["id"]) is not None


def test_task_tools_crud(tmp_path):
    store = _make_store(tmp_path)
    create = TaskCreateTool(store)
    r = create.execute({"title": "发布会物料", "description": "300份资料袋"})
    task_id = store.list()[0]["id"]
    assert not r.is_error

    update = TaskUpdateTool(store)
    r2 = update.execute({"task_id": task_id, "status": "in_progress"})
    assert "in_progress" in r2.content

    output = TaskOutputTool(store)
    r3 = output.execute({"task_id": task_id, "output": "物料已备齐"})
    assert "completed" in r3.content

    get = TaskGetTool(store)
    r4 = get.execute({"task_id": task_id})
    assert "物料已备齐" in r4.content

    stop = TaskStopTool(store)
    t2 = store.create("被取消的任务")
    r5 = stop.execute({"task_id": t2["id"]})
    assert "Cancelled" in r5.content

    listing = TaskListTool(store)
    r6 = listing.execute({})
    assert "发布会物料" in r6.content
