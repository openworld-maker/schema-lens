from pathlib import Path


def test_dockerfile_exists_and_entrypoint():
    path = Path("docker/Dockerfile")
    assert path.exists()
    text = path.read_text(encoding="utf-8")
    assert "ENTRYPOINT [\"solrguard\"]" in text


def test_helm_chart_templates_exist():
    chart = Path("helm/solrguard/Chart.yaml")
    deployment = Path("helm/solrguard/templates/deployment.yaml")
    service = Path("helm/solrguard/templates/service.yaml")
    assert chart.exists()
    assert deployment.exists()
    assert service.exists()
    assert "solrguard" in chart.read_text(encoding="utf-8")
    assert Path("helm/schema-lens/Chart.yaml").exists()
    assert Path("helm/schema-lens/README.md").exists()
    assert Path("helm/solrguard/README.md").exists()


def test_release_workflow_and_scripts_exist():
    workflow = Path(".github/workflows/release.yml")
    build_script = Path("scripts/release/build_release.sh")
    verify_script = Path("scripts/release/verify_reproducibility.sh")
    assert workflow.exists()
    assert build_script.exists()
    assert verify_script.exists()


def test_deploy_examples_exist():
    assert Path("examples/deploy/docker_run.md").exists()
    assert Path("examples/deploy/k8s_job.yaml").exists()
    assert Path("examples/deploy/github_actions.yml").exists()


def test_pyproject_has_solrguard_and_legacy_alias():
    text = Path("pyproject.toml").read_text(encoding="utf-8")
    assert 'solrguard = "schema_lens.cli:app"' in text
    assert 'schema-lens = "schema_lens.cli:app"' in text
