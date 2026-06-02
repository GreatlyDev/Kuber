from pathlib import Path

import yaml


MANIFEST_PATH = Path("deploy/local/demo-app.yaml")


def _load_resources():
    return list(yaml.safe_load_all(MANIFEST_PATH.read_text(encoding="utf-8")))


def test_demo_manifest_defines_dev_namespace():
    namespace = _load_resources()[0]

    assert namespace["kind"] == "Namespace"
    assert namespace["metadata"]["name"] == "dev"


def test_demo_manifest_defines_api_deployment_for_devassist_plans():
    resources = _load_resources()
    deployment = next(resource for resource in resources if resource["kind"] == "Deployment")

    assert deployment["metadata"]["name"] == "api"
    assert deployment["metadata"]["namespace"] == "dev"
    assert deployment["spec"]["selector"]["matchLabels"] == {"app": "api"}
    assert deployment["spec"]["template"]["metadata"]["labels"] == {"app": "api"}
    assert deployment["spec"]["template"]["spec"]["containers"][0]["name"] == "api"


def test_demo_manifest_defines_api_service():
    resources = _load_resources()
    service = next(resource for resource in resources if resource["kind"] == "Service")

    assert service["metadata"]["name"] == "api"
    assert service["metadata"]["namespace"] == "dev"
    assert service["spec"]["selector"] == {"app": "api"}
    assert service["spec"]["ports"] == [
        {
            "name": "http",
            "port": 80,
            "targetPort": 8080,
        }
    ]
