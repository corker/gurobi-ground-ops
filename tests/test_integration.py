"""End to end against a real grafana/otel-lgtm container. Opt-in: `uv run pytest -m integration` (needs Docker)."""

import base64
import json
import time
import urllib.parse
import urllib.request
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest
from testcontainers.core.container import DockerContainer

from ground_ops.cli import main

pytestmark = pytest.mark.integration

GRAFANA = Path(__file__).parent.parent / "grafana"
PROVISIONING = "/otel-lgtm/grafana/conf/provisioning/dashboards"
WAIT_SECONDS = 120
PORTS = {"grafana": 3000, "otlp": 4318, "prometheus": 9090}


def poll[T](fetch: Callable[[], T], *, what: str) -> T:
    """Call `fetch` until it returns something truthy, tolerating connection errors while the container starts."""
    deadline = time.monotonic() + WAIT_SECONDS
    while time.monotonic() < deadline:
        try:
            if value := fetch():
                return value
        except OSError:
            pass
        time.sleep(2)
    raise AssertionError(f"timed out after {WAIT_SECONDS} s waiting for {what}")


def get_json(url: str, *, auth: bool = False) -> Any:  # noqa: ANN401 - parsed JSON
    headers = {"Authorization": "Basic " + base64.b64encode(b"admin:admin").decode()} if auth else {}
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=10) as response:
        return json.load(response)


@pytest.fixture(scope="module")
def lgtm() -> Iterator[dict[str, str]]:
    container = (
        DockerContainer("grafana/otel-lgtm:0.41.1")
        .with_exposed_ports(3000, 4318, 9090)
        .with_volume_mapping(GRAFANA / "dashboards.yaml", f"{PROVISIONING}/ground-ops.yaml")
        .with_volume_mapping(GRAFANA / "dashboards", f"{PROVISIONING}/ground-ops")
    )
    with container:
        host = container.get_container_host_ip()
        urls = {name: f"http://{host}:{container.get_exposed_port(port)}" for name, port in PORTS.items()}
        poll(lambda: get_json(f"{urls['grafana']}/api/health").get("database") == "ok", what="Grafana")
        poll(
            lambda: urllib.request.urlopen(f"{urls['prometheus']}/-/ready", timeout=5).status == 200, what="Prometheus"
        )
        yield urls


@pytest.fixture(scope="module")
def exported_run(lgtm: dict[str, str]) -> str:
    """Runs one solve through the real OTLP exporter; the fresh container has seen only this run's run_id."""
    with pytest.MonkeyPatch.context() as env:
        env.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", lgtm["otlp"])
        assert main(["solve", "--tasks", "40", "--seed", "1", "--expose-search"]) == 0

    def run_ids() -> list[str]:
        ids: list[str] = get_json(f"{lgtm['prometheus']}/api/v1/label/run_id/values")["data"]
        return ids

    (run_id,) = poll(run_ids, what="the run_id in Prometheus")
    return run_id


def test_metrics_reach_prometheus_under_their_translated_names(lgtm: dict[str, str], exported_run: str) -> None:
    query = urllib.parse.urlencode({"query": f'groundops_solver_bound{{run_id="{exported_run}"}}'})

    def final_bound() -> float | None:
        result = get_json(f"{lgtm['prometheus']}/api/v1/query?{query}")["data"]["result"]
        return float(result[0]["value"][1]) if result else None

    # Ingestion lags slightly, so an earlier export can briefly be the latest sample; wait for the final one.
    assert poll(lambda: final_bound() == 30.0, what="the run's final bound (30) in Prometheus")


def test_gurobi_log_lines_reach_loki(lgtm: dict[str, str], exported_run: str) -> None:
    now = int(time.time())
    params = {"query": f'{{service_name="ground-ops"}} | run_id="{exported_run}"', "start": (now - 600) * 10**9}
    url = f"{lgtm['grafana']}/api/datasources/proxy/uid/loki/loki/api/v1/query_range?{urllib.parse.urlencode(params)}"

    def lines() -> list[str]:
        streams = get_json(url, auth=True)["data"]["result"]
        return [value[1] for stream in streams for value in stream["values"]]

    assert any(line.startswith("Optimal solution found") for line in poll(lines, what="the run's log lines in Loki"))


def test_the_run_is_traced_in_tempo_with_a_span_per_phase(lgtm: dict[str, str], exported_run: str) -> None:
    now = int(time.time())
    params = {"q": f'{{ span.run_id = "{exported_run}" }}', "start": now - 600, "end": now + 60}
    search = f"{lgtm['grafana']}/api/datasources/proxy/uid/tempo/api/search?{urllib.parse.urlencode(params)}"

    def trace_ids() -> list[str]:
        return [t["traceID"] for t in get_json(search, auth=True).get("traces") or []]

    # Tempo's search index lags ingestion, so this can take tens of seconds.
    (trace_id,) = poll(trace_ids, what="the run's trace in Tempo")
    trace = get_json(f"{lgtm['grafana']}/api/datasources/proxy/uid/tempo/api/traces/{trace_id}", auth=True)
    names = {span["name"] for batch in trace["batches"] for scope in batch["scopeSpans"] for span in scope["spans"]}
    assert names == {"ground-ops run", "generate instance", "build model", "solve"}


def test_the_dashboard_is_provisioned(lgtm: dict[str, str]) -> None:
    dashboard = get_json(f"{lgtm['grafana']}/api/dashboards/uid/ground-ops-solver", auth=True)["dashboard"]
    assert dashboard["title"] == "ground-ops: solver progress"
