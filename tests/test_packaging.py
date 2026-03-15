from pathlib import Path


def test_dockerfile_exists_and_entrypoint():
    path = Path("docker/Dockerfile")
    assert path.exists()
    text = path.read_text(encoding="utf-8")
    assert "ENTRYPOINT [\"schema-lens\"]" in text


def test_helm_chart_templates_exist():
    chart = Path("helm/schema-lens/Chart.yaml")
    deployment = Path("helm/schema-lens/templates/deployment.yaml")
    service = Path("helm/schema-lens/templates/service.yaml")
    assert chart.exists()
    assert deployment.exists()
    assert service.exists()


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
