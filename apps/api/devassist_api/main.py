from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from devassist_core.langchain_parser import DeterministicLangChainParser
from devassist_core.plan_builder import build_execution_plan
from devassist_core.plan_repository import InMemoryPlanRepository
from devassist_core.policy import PolicyDecision, validate_execution_plan
from devassist_core.schemas import ExecutionPlan, ExecutionRun

app = FastAPI(
    title="DevAssist API",
    version="0.1.0",
    description="Local MVP API for Kubernetes-native CI/CD orchestration.",
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
def readyz() -> dict[str, object]:
    return {
        "status": "ready",
        "dependencies": {
            "kubernetes": "not_configured",
            "redis": "not_configured",
        },
    }


@app.post("/plans", response_model=ExecutionPlan, status_code=status.HTTP_201_CREATED)
def create_plan(request: CreatePlanRequest) -> ExecutionPlan:
    intent = parser.parse(request.text)
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
    except KeyError as exc:
        raise _not_found(plan_id) from exc


@app.get("/plans/{plan_id}/policy", response_model=PolicyDecision)
def get_plan_policy(plan_id: str) -> PolicyDecision:
    return validate_execution_plan(_load_plan(plan_id))


@app.post(
    "/plans/{plan_id}/runs",
    response_model=ExecutionRun,
    status_code=status.HTTP_201_CREATED,
)
def run_plan(plan_id: str) -> ExecutionRun:
    plan = _load_plan(plan_id)
    policy = validate_execution_plan(plan)
    if not policy.allowed:
        raise HTTPException(status_code=403, detail=policy.reasons)

    if execution_runtime is None:
        raise HTTPException(
            status_code=503,
            detail="execution runtime is not configured",
        )

    return execution_runtime.execute(plan)


def _load_plan(plan_id: str) -> ExecutionPlan:
    plan = plan_repository.get(plan_id)
    if plan is None:
        raise _not_found(plan_id)
    return plan


def _not_found(plan_id: str) -> HTTPException:
    return HTTPException(status_code=404, detail=f"plan '{plan_id}' was not found")
