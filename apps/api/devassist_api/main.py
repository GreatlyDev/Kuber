from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query, Response, status
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from devassist_api.runtime import (
    RuntimeSettings,
    build_execution_runtime,
    load_settings,
)
from devassist_core.execution_runtime import ExecutionRunFailedError
from devassist_core.langchain_parser import DeterministicLangChainParser
from devassist_core.plan_builder import build_execution_plan
from devassist_core.plan_repository import InMemoryPlanRepository
from devassist_core.policy import PolicyDecision, validate_execution_plan
from devassist_core.schemas import (
    DeploymentAction,
    DeploymentState,
    ExecutionPlan,
    ExecutionRun,
    KUBERNETES_NAME_PATTERN,
    PipelineIntent,
    RunEvent,
    RunStatus,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_execution_runtime()
    yield


app = FastAPI(
    title="DevAssist API",
    version="0.1.0",
    description="Local MVP API for Kubernetes-native CI/CD orchestration.",
    lifespan=lifespan,
)
parser = DeterministicLangChainParser()
plan_repository = InMemoryPlanRepository()
execution_runtime = None


class CreatePlanRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    text: str = Field(min_length=1)


class ApprovePlanRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    approved_by: str = Field(min_length=1)


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/readyz")
def readyz(response: Response) -> dict[str, object]:
    if execution_runtime is not None and hasattr(
        execution_runtime,
        "check_dependencies",
    ):
        dependencies = execution_runtime.check_dependencies()
    else:
        runtime_status = "configured" if execution_runtime is not None else "not_configured"
        dependencies = {
            "kubernetes": runtime_status,
            "redis": runtime_status,
        }

    is_ready = all(value != "unavailable" for value in dependencies.values())
    if not is_ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return {
        "status": "ready" if is_ready else "not_ready",
        "dependencies": dependencies,
    }


@app.post("/plans", response_model=ExecutionPlan, status_code=status.HTTP_201_CREATED)
def create_plan(request: CreatePlanRequest) -> ExecutionPlan:
    try:
        intent = parser.parse(request.text)
    except ValidationError as exc:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "invalid pipeline intent",
                "errors": [error["msg"] for error in exc.errors()],
            },
        ) from exc
    plan = build_execution_plan(intent)
    return plan_repository.save(plan)


@app.get("/plans", response_model=list[ExecutionPlan])
def list_plans() -> list[ExecutionPlan]:
    return plan_repository.list()


@app.get("/plans/{plan_id}", response_model=ExecutionPlan)
def get_plan(plan_id: str) -> ExecutionPlan:
    return _load_plan(plan_id)


@app.post("/plans/{plan_id}/approve", response_model=ExecutionPlan)
def approve_plan(plan_id: str, request: ApprovePlanRequest) -> ExecutionPlan:
    try:
        return plan_repository.approve(plan_id, approved_by=request.approved_by)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except KeyError as exc:
        raise _not_found(plan_id) from exc


@app.post("/plans/{plan_id}/reject", response_model=ExecutionPlan)
def reject_plan(plan_id: str) -> ExecutionPlan:
    try:
        return plan_repository.reject(plan_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except KeyError as exc:
        raise _not_found(plan_id) from exc


@app.get("/plans/{plan_id}/policy", response_model=PolicyDecision)
def get_plan_policy(plan_id: str) -> PolicyDecision:
    return _validate_plan_policy(_load_plan(plan_id))


@app.get("/deployments/{namespace}/{app_name}/state", response_model=DeploymentState)
def get_deployment_state(namespace: str, app_name: str) -> DeploymentState:
    runtime = _require_execution_runtime()
    plan = build_execution_plan(
        PipelineIntent(
            action=DeploymentAction.STATUS,
            app=app_name,
            namespace=namespace,
        )
    )
    result = runtime.executor.execute(plan)
    if not result.policy.allowed:
        raise HTTPException(status_code=403, detail=result.policy.reasons)
    if result.deployment_state is None:
        raise HTTPException(
            status_code=404,
            detail=f"deployment '{namespace}/{app_name}' was not found",
        )
    return result.deployment_state


@app.post(
    "/plans/{plan_id}/runs",
    response_model=ExecutionRun,
    status_code=status.HTTP_201_CREATED,
)
def run_plan(plan_id: str) -> ExecutionRun:
    plan = _load_plan(plan_id)
    runtime = _require_execution_runtime()
    policy = _validate_plan_policy(plan)
    if not policy.allowed:
        raise HTTPException(status_code=403, detail=policy.reasons)

    try:
        return runtime.execute(plan)
    except ExecutionRunFailedError as exc:
        raise HTTPException(
            status_code=500,
            detail={
                "message": "execution failed",
                "run_id": exc.run.run_id,
                "status": exc.run.status,
                "error": exc.error,
                "events_path": f"/runs/{exc.run.run_id}/events",
            },
        ) from exc


@app.get("/runs", response_model=list[ExecutionRun])
def list_runs(
    run_status: RunStatus | None = Query(default=None, alias="status"),
    action: DeploymentAction | None = Query(default=None),
    app_name: str | None = Query(
        default=None,
        alias="app",
        pattern=KUBERNETES_NAME_PATTERN,
    ),
    namespace: str | None = Query(default=None, pattern=KUBERNETES_NAME_PATTERN),
    plan_id: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
) -> list[ExecutionRun]:
    runtime = _require_execution_runtime()
    return runtime.store.list_runs(
        status=run_status,
        action=action,
        app=app_name,
        namespace=namespace,
        plan_id=plan_id,
        limit=limit,
    )


@app.get("/runs/{run_id}", response_model=ExecutionRun)
def get_run(run_id: str) -> ExecutionRun:
    runtime = _require_execution_runtime()
    run = runtime.store.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"run '{run_id}' was not found")
    return run


@app.get("/runs/{run_id}/events", response_model=list[RunEvent])
def get_run_events(run_id: str) -> list[RunEvent]:
    runtime = _require_execution_runtime()
    run = runtime.store.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"run '{run_id}' was not found")
    return runtime.store.list_events(run_id)


def _load_plan(plan_id: str) -> ExecutionPlan:
    plan = plan_repository.get(plan_id)
    if plan is None:
        raise _not_found(plan_id)
    return plan


def _not_found(plan_id: str) -> HTTPException:
    return HTTPException(status_code=404, detail=f"plan '{plan_id}' was not found")


def _require_execution_runtime():
    if execution_runtime is None:
        raise HTTPException(
            status_code=503,
            detail="execution runtime is not configured",
        )
    return execution_runtime


def _validate_plan_policy(plan: ExecutionPlan) -> PolicyDecision:
    if execution_runtime is not None and hasattr(execution_runtime, "validate"):
        return execution_runtime.validate(plan)
    return validate_execution_plan(plan)


def configure_execution_runtime(
    settings: RuntimeSettings | None = None,
    runtime_builder=build_execution_runtime,
) -> None:
    global execution_runtime
    settings = settings or load_settings()
    execution_runtime = runtime_builder(settings)
