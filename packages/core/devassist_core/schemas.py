from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    computed_field,
    field_validator,
    model_validator,
)

KUBERNETES_NAME_PATTERN = r"^[a-z0-9]([-a-z0-9]*[a-z0-9])?$"
RUN_EVENT_TYPE_PATTERN = r"^[a-z0-9][a-z0-9-]*(\.[a-z0-9][a-z0-9-]*)+$"


class StrictModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
    )


class DeploymentAction(StrEnum):
    DEPLOY = "deploy"
    ROLLBACK = "rollback"
    RESTART = "restart"
    SCALE = "scale"
    STATUS = "status"


class PlanStatus(StrEnum):
    DRAFT = "draft"
    APPROVED = "approved"
    REJECTED = "rejected"


class RunStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class PipelineIntent(StrictModel):
    action: DeploymentAction
    app: str = Field(pattern=KUBERNETES_NAME_PATTERN)
    namespace: str = Field(default="dev", pattern=KUBERNETES_NAME_PATTERN)
    image: str | None = None
    replicas: int | None = Field(default=None, ge=0, le=20)
    raw_text: str | None = None

    @model_validator(mode="after")
    def validate_action_inputs(self) -> "PipelineIntent":
        if self.action is DeploymentAction.DEPLOY and not self.image:
            raise ValueError("image is required for deploy intents")
        if self.action is DeploymentAction.SCALE and self.replicas is None:
            raise ValueError("replicas is required for scale intents")
        return self


class PlanStep(StrictModel):
    action: DeploymentAction
    resource: str = Field(pattern=KUBERNETES_NAME_PATTERN)
    namespace: str = Field(pattern=KUBERNETES_NAME_PATTERN)
    name: str = Field(pattern=KUBERNETES_NAME_PATTERN)
    params: dict[str, Any] = Field(default_factory=dict)


class ExecutionPlan(StrictModel):
    plan_id: str = Field(default_factory=lambda: f"plan-{uuid4().hex}")
    intent: PipelineIntent
    summary: str
    steps: list[PlanStep]
    status: PlanStatus = PlanStatus.DRAFT
    requires_approval: bool = True
    approved_by: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @computed_field
    @property
    def approved(self) -> bool:
        return self.status is PlanStatus.APPROVED

    @model_validator(mode="after")
    def validate_approval_metadata(self) -> "ExecutionPlan":
        if self.status is PlanStatus.APPROVED and not self.approved_by:
            raise ValueError("approved_by is required when plan status is approved")
        return self


class ExecutionRun(StrictModel):
    run_id: str = Field(default_factory=lambda: f"run-{uuid4().hex}")
    plan_id: str
    plan_summary: str | None = None
    plan_action: DeploymentAction | None = None
    plan_app: str | None = Field(default=None, pattern=KUBERNETES_NAME_PATTERN)
    plan_namespace: str | None = Field(default=None, pattern=KUBERNETES_NAME_PATTERN)
    status: RunStatus
    redis_state_key: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class RunEvent(StrictModel):
    event_id: str = Field(default_factory=lambda: f"evt-{uuid4().hex}")
    run_id: str
    event_type: str
    message: str
    redis_stream_key: str
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("event_type")
    @classmethod
    def event_type_uses_dotted_name(cls, value: str) -> str:
        if "." not in value:
            raise ValueError("event_type must use dotted naming, for example run.queued")
        return value


class DeploymentState(StrictModel):
    app: str = Field(pattern=KUBERNETES_NAME_PATTERN)
    namespace: str = Field(pattern=KUBERNETES_NAME_PATTERN)
    desired_image: str | None = None
    current_image: str | None = None
    replicas: int = Field(ge=0)
    available_replicas: int = Field(ge=0)
    observed_at: datetime
    conditions: dict[str, str] = Field(default_factory=dict)


class PolicyDecision(StrictModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
        frozen=True,
    )

    allowed: bool
    reasons: list[str]


class ApprovalQueueItem(StrictModel):
    plan: ExecutionPlan
    policy: PolicyDecision
