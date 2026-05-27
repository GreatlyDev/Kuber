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
