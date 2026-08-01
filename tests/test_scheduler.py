import time

from ohwang.services.scheduler import Scheduler, cron_matches


def test_cron_star_matches_all():
    assert cron_matches("* * * * *", 5, 3, 20, 6, 1) is True


def test_cron_step():
    assert cron_matches("*/5 * * * *", 5, 3, 20, 6, 1) is True
    assert cron_matches("*/5 * * * *", 6, 3, 20, 6, 1) is False


def test_cron_range_and_dow():
    assert cron_matches("0 9 * * 1-5", 0, 9, 15, 3, 3) is True
    assert cron_matches("0 9 * * 1-5", 30, 9, 15, 3, 3) is False
    assert cron_matches("0 9 * * 1-5", 0, 9, 15, 3, 6) is False


def test_cron_list_field():
    assert cron_matches("1,30 * * * *", 30, 0, 1, 1, 0) is True
    assert cron_matches("1,30 * * * *", 15, 0, 1, 1, 0) is False


def test_bad_expression_rejected():
    assert cron_matches("not a cron", 0, 0, 1, 1, 0) is False


def test_add_rejects_invalid_even_when_matches_now():
    lt = time.localtime()
    expr = f"{lt.tm_min} {lt.tm_hour} {lt.tm_mday} {lt.tm_mon} {lt.tm_wday} extra"
    s = Scheduler()
    assert not s.add("j", expr, "x")
    assert s.count() == 0


def test_add_does_not_raise_on_garbage_fields():
    s = Scheduler()
    assert not s.add("j", "abc * * * *", "x")
    assert s.count() == 0


def test_scheduler_add_remove_list():
    s = Scheduler()
    assert s.add("j1", "*/5 * * * *", "run tests")
    assert not s.add("j1", "*/5 * * * *", "dup")  # duplicate id
    assert not s.add("bad", "not a cron", "x")
    assert s.count() == 1
    assert [j.id for j in s.list()] == ["j1"]
    assert s.remove("j1")
    assert not s.remove("j1")
    assert s.count() == 0


def test_scheduler_fires_due_job():
    fired: list[str] = []
    s = Scheduler(runner=lambda p: fired.append(p))
    lt = time.localtime()
    expr = f"{lt.tm_min} {lt.tm_hour} {lt.tm_mday} {lt.tm_mon} {lt.tm_wday}"
    assert s.add("now", expr, "hello")
    s.start()
    deadline = time.time() + 6
    while time.time() < deadline and not fired:
        time.sleep(0.2)
    s.stop()
    assert fired == ["hello"]


def test_scheduler_runner_error_is_swallowed():
    def boom(prompt):
        raise RuntimeError("oops")

    s = Scheduler(runner=boom)
    lt = time.localtime()
    expr = f"{lt.tm_min} {lt.tm_hour} {lt.tm_mday} {lt.tm_mon} {lt.tm_wday}"
    s.add("j", expr, "x")
    s.start()
    time.sleep(2)
    s.stop()
    assert s.count() == 1


def test_scheduler_stop_joins_thread():
    s = Scheduler()
    s.start()
    thread = s._thread
    assert thread is not None and thread.is_alive()
    s.stop()
    assert not thread.is_alive()
    assert s._thread is None


def test_scheduler_stop_without_start_is_safe():
    s = Scheduler()
    s.stop()
    assert s._thread is None


def test_scheduler_persists_jobs(tmp_path):
    state = tmp_path / "cron.json"
    s1 = Scheduler(state_file=state)
    assert s1.add("daily", "0 9 * * 1", "run report")
    assert s1.add("weekly", "0 10 * * 5", "send summary")
    s2 = Scheduler(state_file=state)
    assert s2.count() == 2
    ids = {j.id for j in s2.list()}
    assert ids == {"daily", "weekly"}


def test_scheduler_persists_last_run(tmp_path):
    state = tmp_path / "cron.json"
    s1 = Scheduler(state_file=state)
    s1.add("job", "* * * * *", "x")
    s1.list()[0].last_run = 12345.0
    s1._save()
    s2 = Scheduler(state_file=state)
    assert s2.list()[0].last_run == 12345.0


def test_scheduler_remove_persists(tmp_path):
    state = tmp_path / "cron.json"
    s1 = Scheduler(state_file=state)
    s1.add("keep", "* * * * *", "a")
    s1.add("drop", "* * * * *", "b")
    s1.remove("drop")
    s2 = Scheduler(state_file=state)
    assert {j.id for j in s2.list()} == {"keep"}


def test_scheduler_loads_bad_state_safely(tmp_path):
    state = tmp_path / "cron.json"
    state.write_text("{bad json", encoding="utf-8")
    s = Scheduler(state_file=state)
    assert s.count() == 0


def test_scheduler_loads_bom_state(tmp_path):
    state = tmp_path / "cron.json"
    import json
    payload = json.dumps({"jobs": [{"id": "j", "expression": "* * * * *", "prompt": "p"}]})
    state.write_bytes(b"\xef\xbb\xbf" + payload.encode("utf-8"))
    s = Scheduler(state_file=state)
    assert s.count() == 1
    assert s.list()[0].id == "j"
