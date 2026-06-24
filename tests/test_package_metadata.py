from pathlib import Path
import tomllib


ROOT = Path(__file__).resolve().parents[1]


def test_dashboard_static_assets_are_declared_as_package_data():
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))

    package_data = pyproject["tool"]["setuptools"]["package-data"]

    assert package_data["devassist_api"] == [
        "static/*.css",
        "static/*.js",
    ]
