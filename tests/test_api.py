import json
import subprocess
import sys
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from ground_ops import api
from ground_ops.checks import assignment_violations
from ground_ops.domain import AssignmentInstance, Handler, Task
from ground_ops.instances import generate_assignment
from ground_ops.model1 import build_model, model_size
from ground_ops.solver import DEFAULT_SETTINGS, gurobi_env
from tests.support import InMemoryTelemetry

# Search exposed, about 3 work units: long enough that a cancel or a second request lands while it runs.
LONG_RUN = {"model": "assignment", "tasks": 40, "seed": 1, "expose_search": True}


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(api.create_app(None)) as test_client:
        yield test_client


def events(client: TestClient, run_id: str, last_event_id: str | None = None) -> list[dict[str, str]]:
    """Read a run's event stream until it ends, as one dict of SSE fields per event."""
    headers = {} if last_event_id is None else {"Last-Event-ID": last_event_id}
    parsed, current = [], {}
    with client.stream("GET", f"/api/runs/{run_id}/events", headers=headers) as response:
        assert response.status_code == 200
        for line in response.iter_lines():
            if line:
                key, _, value = line.partition(": ")
                current[key] = value
            elif current:
                parsed.append(current)
                current = {}
    return parsed


def start(client: TestClient, **request: object) -> str:
    response = client.post("/api/runs", json=request)
    assert response.status_code == 202, response.text
    run_id: str = response.json()["id"]
    return run_id


def test_a_run_streams_progress_then_done_and_its_result_is_a_feasible_optimum(client: TestClient) -> None:
    run_id = start(client, model="assignment", tasks=10, seed=3)
    stream = events(client, run_id)
    assert [e["id"] for e in stream] == [str(i) for i in range(len(stream))]
    assert {e["event"] for e in stream[:-1]} == {"progress"}
    assert (stream[-1]["event"], json.loads(stream[-1]["data"])) == ("done", {"status": "optimal", "error": None})

    view = client.get(f"/api/runs/{run_id}").json()
    assert view["state"] == "done"
    assert view["result"]["objective"] == 9
    assert json.loads(stream[-2]["data"]) == view["progress"]
    instance = generate_assignment(10, seed=3)
    assignment = {int(task): handler for task, handler in view["result"]["solution"].items()}
    assert assignment_violations(instance, assignment) == []


def test_a_coverage_run_returns_its_roster(client: TestClient) -> None:
    run_id = start(client, model="coverage", seed=1)
    assert json.loads(events(client, run_id)[-1]["data"])["status"] == "optimal"
    view = client.get(f"/api/runs/{run_id}").json()
    assert view["result"]["objective"] == 239
    assert len(view["instance"]["demand"]) == 48


def test_a_reconnecting_client_resumes_after_its_last_event(client: TestClient) -> None:
    run_id = start(client, **LONG_RUN)
    full = events(client, run_id)
    resumed = events(client, run_id, last_event_id=full[-3]["id"])
    assert resumed == full[-2:]


def test_a_work_limit_ends_the_run_as_limit_reached(client: TestClient) -> None:
    run_id = start(client, **LONG_RUN, work_limit=0.5)
    assert json.loads(events(client, run_id)[-1]["data"])["status"] == "limit reached"
    assert client.get(f"/api/runs/{run_id}").json()["result"]["gap"] > 0


def test_too_few_handlers_ends_the_run_as_infeasible_with_the_iis(client: TestClient) -> None:
    run_id = start(client, model="assignment", tasks=10, seed=1, handlers=2)
    assert json.loads(events(client, run_id)[-1]["data"])["status"] == "infeasible"
    assert "cover[0]" in client.get(f"/api/runs/{run_id}").json()["result"]["iis"]


def test_cancelling_a_run_ends_it_as_interrupted_and_a_second_cancel_conflicts(client: TestClient) -> None:
    run_id = start(client, **LONG_RUN)
    assert client.post(f"/api/runs/{run_id}/cancel").status_code == 202
    assert json.loads(events(client, run_id)[-1]["data"])["status"] == "interrupted"
    assert client.get(f"/api/runs/{run_id}").json()["result"]["status"] == "interrupted"
    assert client.post(f"/api/runs/{run_id}/cancel").status_code == 409


@pytest.mark.parametrize(("method", "path"), [("GET", ""), ("GET", "/events"), ("POST", "/cancel")])
def test_a_missing_run_is_a_404_before_any_stream_starts(client: TestClient, method: str, path: str) -> None:
    response = client.request(method, f"/api/runs/no-such-run{path}")
    assert response.status_code == 404
    assert response.headers["content-type"] == "application/json"


def test_a_third_run_is_refused_while_both_workers_are_busy_and_accepted_once_one_ends(client: TestClient) -> None:
    first, second = start(client, **LONG_RUN), start(client, **LONG_RUN)
    assert client.post("/api/runs", json={"model": "coverage"}).status_code == 429
    client.post(f"/api/runs/{first}/cancel")
    events(client, first)
    start(client, model="coverage")
    client.post(f"/api/runs/{second}/cancel")


def test_two_runs_at_once_each_reach_their_own_optimum(client: TestClient) -> None:
    runs = {start(client, model="assignment", tasks=10, seed=3): 9, start(client, model="coverage", seed=1): 239}
    for run_id, objective in runs.items():
        events(client, run_id)
        assert client.get(f"/api/runs/{run_id}").json()["result"]["objective"] == objective


@pytest.mark.parametrize(
    ("request_body", "message"),
    [
        ({"model": "assignment", "tasks": 7}, "positive multiple of 2"),
        ({"model": "assignment", "tasks": 80}, "free Gurobi licence allows 2000"),
        ({"model": "assignment", "tasks": 2002}, "less than or equal to 2000"),
        ({"model": "assignment", "handlers": 1001}, "less than or equal to 1000"),
        ({"model": "assignment", "handlers": -1}, "greater than or equal to 0"),
        ({"model": "coverage", "work_limit": -1}, "greater than or equal to 0"),
        ({"model": "routing"}, "'assignment' or 'coverage'"),
    ],
)
def test_an_invalid_request_is_refused_before_a_run_starts(
    client: TestClient, request_body: dict[str, object], message: str
) -> None:
    response = client.post("/api/runs", json=request_body)
    assert response.status_code == 422
    assert message in response.text


@pytest.mark.parametrize("failure", [RuntimeError("Gurobi stopped with status code 12"), KeyError(3)])
def test_a_solver_failure_ends_the_run_as_failed(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, failure: Exception
) -> None:
    def fail(*_: object, **__: object) -> None:
        raise failure

    monkeypatch.setattr(api, "solve_coverage", fail)
    run_id = start(client, model="coverage")
    assert json.loads(events(client, run_id)[-1]["data"]) == {"status": None, "error": str(failure)}
    assert client.get(f"/api/runs/{run_id}").json()["state"] == "failed"


def test_a_negative_last_event_id_is_refused(client: TestClient) -> None:
    run_id = start(client, model="coverage")
    events(client, run_id)
    assert client.get(f"/api/runs/{run_id}/events", headers={"Last-Event-ID": "-5"}).status_code == 422


def test_with_telemetry_the_runs_trace_carries_the_api_run_id(in_memory: InMemoryTelemetry) -> None:
    with TestClient(api.create_app(in_memory.telemetry)) as client:
        run_id = start(client, model="assignment", tasks=10, seed=3)
        events(client, run_id)
    root = next(s for s in in_memory.spans.get_finished_spans() if s.name == "ground-ops run")
    assert root.attributes is not None
    assert root.attributes["run_id"] == run_id


@pytest.mark.parametrize(("n_tasks", "seed"), [(2, 1), (10, 3), (30, 1), (48, 7)])
def test_the_size_counted_without_gurobi_matches_the_built_model(n_tasks: int, seed: int) -> None:
    instance = generate_assignment(n_tasks, seed)
    with gurobi_env(DEFAULT_SETTINGS) as env:
        model, _ = build_model(instance, env)
        with model:
            assert model_size(instance) == (model.NumVars, model.NumConstrs)


def test_the_size_of_an_instance_without_handlers_is_one_constraint_per_task() -> None:
    assert model_size(AssignmentInstance((Task(0, 0, 10), Task(1, 5, 15)), handlers=())) == (0, 2)
    assert model_size(AssignmentInstance((Task(0, 0, 10),), (Handler(0, 0, 60),))) == (1, 1)


def test_the_core_modules_dont_load_the_web_stack() -> None:
    core = ["domain", "instances", "model1", "model2", "solver", "progress", "telemetry", "checks", "cli"]
    code = "; ".join(
        [
            *(f"import ground_ops.{name}" for name in core),
            "import sys",
            "print(sorted({'fastapi', 'uvicorn', 'starlette'} & set(sys.modules)))",
        ]
    )
    assert subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True).stdout == "[]\n"
