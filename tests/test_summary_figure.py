import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load_module():
    spec = importlib.util.spec_from_file_location(
        "make_summary_figure", ROOT / "scripts" / "make_summary_figure.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_readme_key_findings_match_committed_results():
    module = _load_module()
    results = module.load_results()
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    kinetic = results["kinetic"]
    best = kinetic[kinetic["rank_by_holdout_rmse"] == 1.0]
    assert set(best["model"]) == {"modified_gompertz"}
    assert len(best) == 4

    potential = results["dose"].query("response == 'potential_ml_g_vs'").set_index("model")
    errors = potential["mean_absolute_percentage_error"]
    assert f"{errors['log_linear_dose']:.1f}%" in readme
    assert f"{errors['log_quadratic_dose']:.1f}%" in readme

    forecast = results["forecast"].set_index("method")["error_percent"]
    assert forecast.idxmin() == "recent_rate"
    assert f"{forecast['recent_rate']:.1f}%" in readme
    assert f"{forecast.drop(['recent_rate', 'persistence']).min():.1f}%" in readme


def test_summary_figure_builds(tmp_path):
    module = _load_module()
    figure = module.build_figure(module.load_results())
    target = tmp_path / "key_findings.png"
    figure.savefig(target)
    assert target.stat().st_size > 10_000
    assert len(figure.axes) == 3
