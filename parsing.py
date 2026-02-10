from pathlib import Path
import re
import pandas as pd
import numpy as np

_num_re = re.compile(r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?")

def nrmse(sim_vals, exp_vals, eps=1e-12):
    """
    Normalized RMSE using the peak magnitude of the experimental signal.
    Returns a fraction (0.0 = perfect). Multiply by 100 for percent.
    """
    sim = np.asarray(sim_vals, dtype=float)
    exp = np.asarray(exp_vals, dtype=float)

    denom = np.max(np.abs(exp))
    denom = max(denom, eps)

    rmse = np.sqrt(np.mean((sim - exp) ** 2))
    return rmse / denom

def resample_to_n_points(df: pd.DataFrame, n: int) -> pd.DataFrame:
    """
    Resample a Step/Value dataframe to exactly n points using linear interpolation
    over normalized progress (0 -> 1). Keeps the same columns: Step, Value.
    """
    if n < 2:
        raise ValueError("n must be >= 2")

    y = df["Value"].to_numpy(dtype=float)
    m = len(y)
    if m < 2:
        raise ValueError("Need at least 2 points to resample")

    x_old = np.linspace(0.0, 1.0, m)
    x_new = np.linspace(0.0, 1.0, n)
    y_new = np.interp(x_new, x_old, y)

    # create a new Step index 1..n (or 0..n-1; either is fine as long as consistent)
    return pd.DataFrame({"Step": np.arange(1, n + 1), "Value": y_new})

def parse_febio_log_by_step(log_path, ids_keep=None, agg="sum"):
    """
    Parse FEBio logfile that looks like:
      *Step = N
      *Time = ...
      *Data = Rx   (or sx, etc.)
      id  value
      id  value
      ...

    Returns DataFrame with columns: Step, Value
    where Value is aggregated over the selected ids.
    """
    log_path = Path(log_path)
    lines = log_path.read_text(errors="ignore").splitlines()

    if ids_keep is not None:
        ids_keep = set(int(x) for x in ids_keep)

    current_step = None
    step_values = {}  # step -> list of values (for kept ids)

    for line in lines:
        s = line.strip()

        # Detect step header
        if s.startswith("*Step"):
            nums = _num_re.findall(s)
            if nums:
                current_step = int(float(nums[-1]))
                step_values.setdefault(current_step, [])
            continue

        # Ignore until we have a step
        if current_step is None:
            continue

        # Skip other headers
        if s.startswith("*Time") or s.startswith("*Data") or s.startswith("*"):
            continue

        # Try parse numeric "id value" rows
        nums = _num_re.findall(s)
        if len(nums) >= 2:
            _id = int(float(nums[0]))
            val = float(nums[1])

            if (ids_keep is None) or (_id in ids_keep):
                step_values[current_step].append(val)

    # Build output
    steps = sorted(step_values.keys())
    out_vals = []
    for st in steps:
        vals = np.array(step_values[st], dtype=float)

        if vals.size == 0:
            out_vals.append(np.nan)  # no kept nodes found at that step
            continue

        if agg == "sum":
            out_vals.append(np.sum(vals))
        elif agg == "mean":
            out_vals.append(np.mean(vals))
        else:
            raise ValueError("agg must be 'sum' or 'mean'")

    df = pd.DataFrame({"Step": steps, "Value": out_vals})
    df = df.dropna()  # drop steps where none of the nodes were found

    if df.empty:
        raise ValueError(f"No data parsed for the selected ids from {log_path}")

    return df


def read_experiment(csv_path):
    df = pd.read_csv(csv_path)

    # Choose the experimental force signal to compare:
    # For shear in X, these are the relevant channels.
    # A robust choice is net platen force:
    df["Value"] = 0.5 * (df["Force_Up_X (N)"] - df["Force_Down_X (N)"])

    # Use displacement as x-axis for possible later alignment
    df["X"] = df["X Displacement (mm)"]

    return df[["X", "Value"]]


def align_by_step(sim_df, exp_df):
    """
    Inner join by Step, ensuring aligned vectors.
    """
    merged = pd.merge(
        sim_df,
        exp_df,
        on="Step",
        how="inner",
        suffixes=("_sim", "_exp")
    )

    if merged.empty:
        raise ValueError("No overlapping steps between simulation and experiment")

    return (
        merged[["Step", "Value_sim"]].rename(columns={"Value_sim": "Value"}),
        merged[["Step", "Value_exp"]].rename(columns={"Value_exp": "Value"})
    )


def percent_error(sim_df, exp_df):
    """
    Compute MAPE exactly as in MATLAB.
    """
    sim = sim_df["Value"].to_numpy()
    exp = exp_df["Value"].to_numpy()

    return 100.0 * np.mean(
        np.abs(sim - exp) / np.maximum(1e-12, np.abs(exp))
    )
