import matplotlib.image as mpimg
import pandas as pd

from biochar_ad_twin.fit import fit_global
from biochar_ad_twin.model import BatchCondition, KineticParameters, cumulative_methane
from biochar_ad_twin.report import save_report


def _dataset(temperatures: tuple[float, ...]) -> pd.DataFrame:
    truth = KineticParameters()
    time = [0.0, 5.0, 10.0, 20.0, 30.0]
    rows = []
    for temperature in temperatures:
        for dose in (0.0, 5.0):
            condition = BatchCondition(dose, temperature)
            clean = cumulative_methane(time, condition, truth)
            rows.extend(
                {
                    "batch_id": f"T{temperature:.0f}_D{dose:.0f}",
                    "time_days": day,
                    "dose_g_l": dose,
                    "temperature_c": temperature,
                    "methane_ml_g_vs": value,
                }
                for day, value in zip(time, clean)
            )
    return pd.DataFrame(rows)


def test_save_report_plots_every_temperature_group(tmp_path) -> None:
    frame = _dataset((20.0, 37.0, 55.0))
    parameters, metrics = fit_global(frame)

    save_report(frame, parameters, metrics, tmp_path)

    assert (tmp_path / "fit_summary.json").exists()
    image_path = tmp_path / "fitted_curves.png"
    assert image_path.exists()
    width_px = mpimg.imread(image_path).shape[1]
    two_panel_frame = _dataset((20.0, 37.0))
    two_panel_parameters, two_panel_metrics = fit_global(two_panel_frame)
    save_report(two_panel_frame, two_panel_parameters, two_panel_metrics, tmp_path / "two_panel")
    two_panel_width_px = mpimg.imread(tmp_path / "two_panel" / "fitted_curves.png").shape[1]
    assert width_px > two_panel_width_px
