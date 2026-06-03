import pytest
from pydantic import ValidationError

from devassist_core.langchain_parser import DeterministicLangChainParser
from devassist_core.schemas import DeploymentAction


def test_stub_parser_returns_deterministic_deploy_intent():
    parser = DeterministicLangChainParser()

    intent = parser.parse(
        "deploy api to dev with image example/api:1.0.0",
    )

    assert intent.action is DeploymentAction.DEPLOY
    assert intent.app == "api"
    assert intent.namespace == "dev"
    assert intent.image == "example/api:1.0.0"


def test_stub_parser_does_not_execute_commands():
    parser = DeterministicLangChainParser()

    intent = parser.parse("kubectl delete namespace prod")

    assert intent.action is DeploymentAction.STATUS
    assert intent.app == "unknown"
    assert intent.namespace == "dev"


def test_stub_parser_returns_deterministic_scale_intent():
    parser = DeterministicLangChainParser()

    intent = parser.parse("scale api in dev to 3 replicas")

    assert intent.action is DeploymentAction.SCALE
    assert intent.app == "api"
    assert intent.namespace == "dev"
    assert intent.replicas == 3


def test_stub_parser_requires_explicit_scale_replicas():
    parser = DeterministicLangChainParser()

    with pytest.raises(ValidationError, match="replicas is required"):
        parser.parse("scale api in dev")


def test_stub_parser_preserves_status_namespace():
    parser = DeterministicLangChainParser()

    intent = parser.parse("status api in staging")

    assert intent.action is DeploymentAction.STATUS
    assert intent.app == "api"
    assert intent.namespace == "staging"
