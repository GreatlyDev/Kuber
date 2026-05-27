from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from devassist_core.schemas import (
    DeploymentAction,
    DeploymentState,
    ExecutionPlan,
    ExecutionRun,
    PipelineIntent,
    PlanStep,
    PlanStatus,
    RunEvent,
    RunStatus,
)


def test_pipeline_intent_rejects_unknown_fields():
    with pytest.raises(ValidationError):
        PipelineIntent(
            action=DeploymentAction.DEPLOY,
            app="api",
            namespace="dev",
            image="example/api:1.0.0",
            unexpected=True,
        )


def test_pipeline_intent_requires_image_for_deploy():
    with pytest.raises(ValidationError, match="image is required"):
        PipelineIntent(action=DeploymentAction.DEPLOY, app="api", namespace="dev")


def test_execution_plan_defaults_to_unapproved_draft():
    intent = PipelineIntent(
        action=DeploymentAction.DEPLOY,
        app="api",
        namespace="dev",
        image="example/api:1.0.0",
    )
    step = PlanStep(
        action=DeploymentAction.DEPLOY,
        resource="deployment",
        namespace="dev",
        name="api",
        params={"image": "example/api:1.0.0"},
    )

    plan = ExecutionPlan(intent=intent, summary="Deploy api", steps=[step])

    assert plan.status is PlanStatus.DRAFT
    assert plan.approved is False
    assert plan.requires_approval is True


def test_run_models_include_redis_keys_for_state_and_events():
    now = datetime.now(UTC)

    run = ExecutionRun(
        plan_id="plan-123",
        status=RunStatus.QUEUED,
        redis_state_key="devassist:runs:run-123",
    )
    event = RunEvent(
        run_id=run.run_id,
        event_type="run.queued",
        message="Run queued",
        redis_stream_key="devassist:runs:run-123:events",
        created_at=now,
    )

    assert run.redis_state_key.startswith("devassist:runs:")
    assert event.redis_stream_key.endswith(":events")


def test_deployment_state_tracks_observed_cluster_state():
    state = DeploymentState(
        app="api",
        namespace="dev",
        desired_image="example/api:1.0.0",
        current_image="example/api:0.9.0",
        replicas=2,
        available_replicas=1,
        observed_at=datetime.now(UTC),
    )

    assert state.available_replicas == 1
