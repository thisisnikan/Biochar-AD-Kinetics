# Synthetic paired-model regression reference

These results use `generate_demo_dataset(seed=27)`: 248 synthetic measurements
across eight dose/temperature batches. They are software evidence only. The
generating model is quadratic, so its advantage is not independent validation.

Rebuild from the repository root:

```bash
biochar-ad demo --output outputs/paired-validation --bootstrap 2
```

`leave_one_batch_out.csv` retains all 24 model/fold evaluations, each tagged
`is_boundary_condition`. This demo only ever tests two temperatures (37 °C and
55 °C), so every batch sits at a temperature boundary by construction — every
row here is `True`, meaning none of them test genuine interpolation on the
temperature axis. `held_out_model_comparison.csv` gives each batch equal
weight. The two bootstrap iterations only exercise the CLI; use substantially
more for uncertainty work. Numerical values can vary slightly with
SciPy/platform versions.

Reference environment: Python 3.12, NumPy 2.5.2, SciPy 1.18.1, pandas 3.0.5.
Mean held-out RMSE: quadratic 3.6911, log-linear 16.2812, constant 72.6201 mL/g VS.
Existing real-data benchmarks are unchanged by this comparison.
