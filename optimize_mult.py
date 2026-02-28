import time
import csv
from pathlib import Path
from datetime import datetime
from typing import Dict, Tuple, List

import numpy as np
from scipy.optimize import minimize

from objective import objective_coeffs


# ============================================================
# USER SETTINGS
# ============================================================

# How many (c,m) pairs to optimize THIS run.
# Example: 1 -> optimize (c1,m1); 2 -> optimize (c1,m1,c2,m2); etc.
N_ACTIVE_PAIRS = 2

# Freeze previously-tested pairs here.
# Keys are 1-based pair indices.
# Example: freeze pair 1 to its best values, then optimize pair 2:
# FIXED_PAIRS = {1: {"c": 1.68e-5, "m": 1.0}}
FIXED_PAIRS: Dict[int, Dict[str, float]] = {
    # 1: {"c": 1.68e-5, "m": 1.0},
}

# Bounds for each active pair.
# We optimize in log10(c_i) space for stability across orders of magnitude.
LOG10_C_BOUNDS = (-12.0, 0.0)   # c in [1e-12, 1] MPa (adjust if needed)
M_BOUNDS = (0.1, 25.0)          # unitless

# Starting guesses for active pairs (log10(c), m)
DEFAULT_LOG10_C0 = -5.0         # c=1e-5 MPa
DEFAULT_M0 = 1.0

# FEBio controls
THREADS = 6
FEBIO_TIMEOUT = 270  # seconds per FEBio run (you measured ~205s at threads=6)

# Optimization budget / stopping
MAX_EVALS = 15
TARGET_ERR = 5.0     # percent

# Logging
RUN_LOG = Path(f"multi_run_log_{N_ACTIVE_PAIRS}pairs.csv")
ROUND_DIGITS = 4      # rounding for duplicate detection


# ============================================================
# INTERNAL HELPERS
# ============================================================

def clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))

def roundf(x: float, d: int = ROUND_DIGITS) -> float:
    return round(float(x), d)

def active_pair_indices() -> List[int]:
    """
    Active pairs are the first N_ACTIVE_PAIRS pairs, excluding any fixed ones.
    Example:
      N_ACTIVE_PAIRS=3, FIXED contains pair 1 -> optimize pairs 2 and 3.
    """
    all_pairs = list(range(1, N_ACTIVE_PAIRS + 1))
    return [i for i in all_pairs if i not in FIXED_PAIRS]

def build_x0_and_bounds() -> Tuple[np.ndarray, List[Tuple[float, float]], List[int]]:
    """
    Returns:
      x0: initial vector for optimizer
      bounds: bounds list aligned with x0
      opt_pairs: which pair indices are optimized (not fixed)
    Vector layout: [log10(c_i), m_i, log10(c_j), m_j, ...] for each optimized pair.
    """
    opt_pairs = active_pair_indices()

    x0_list = []
    bounds = []
    for i in opt_pairs:
        x0_list.extend([DEFAULT_LOG10_C0, DEFAULT_M0])
        bounds.extend([LOG10_C_BOUNDS, M_BOUNDS])

    if len(x0_list) == 0:
        raise ValueError("No active (unfixed) pairs to optimize. Either reduce FIXED_PAIRS or increase N_ACTIVE_PAIRS.")

    return np.array(x0_list, dtype=float), bounds, opt_pairs

def x_to_coeffs(x: np.ndarray, opt_pairs: List[int]) -> Dict[str, float]:
    """
    Convert optimizer vector x into full FEBio coeff dict including:
      - fixed pairs from FIXED_PAIRS
      - optimized pairs from x
    """
    coeffs: Dict[str, float] = {}

    # 1) apply fixed pairs
    for i, vals in FIXED_PAIRS.items():
        coeffs[f"c{i}"] = float(vals["c"])
        coeffs[f"m{i}"] = float(vals["m"])

    # 2) apply optimized pairs from x
    # x layout: [log10(c_pair1), m_pair1, log10(c_pair2), m_pair2, ...]
    k = 0
    for i in opt_pairs:
        log10_c = float(x[k]);     k += 1
        m = float(x[k]);           k += 1

        log10_c = clamp(log10_c, *LOG10_C_BOUNDS)
        m = clamp(m, *M_BOUNDS)

        coeffs[f"c{i}"] = 10.0 ** log10_c
        coeffs[f"m{i}"] = m

    return coeffs

def coeffs_to_key(coeffs: Dict[str, float]) -> Tuple[float, ...]:
    """
    Create a rounded tuple key for dedupe across sessions.
    Key includes all c1..cN_ACTIVE_PAIRS and m1..mN_ACTIVE_PAIRS.
    """
    parts: List[float] = []
    for i in range(1, N_ACTIVE_PAIRS + 1):
        # Use log10 for c in key to be scale-consistent
        ci = float(coeffs.get(f"c{i}", 0.0))
        mi = float(coeffs.get(f"m{i}", 0.0))
        log10_ci = -999.0
        if ci > 0:
            log10_ci = np.log10(ci)
        parts.append(roundf(log10_ci))
        parts.append(roundf(mi))
    return tuple(parts)

def ensure_log_header():
    """
    Create CSV with a header that scales with N_ACTIVE_PAIRS.
    Columns: timestamp, log10_c1, c1, m1, log10_c2, c2, m2, ..., error_percent
    """
    if RUN_LOG.exists():
        return
    header = ["timestamp"]
    for i in range(1, N_ACTIVE_PAIRS + 1):
        header += [f"log10_c{i}", f"c{i}", f"m{i}"]
    header += ["error_percent"]
    with RUN_LOG.open("w", newline="") as f:
        csv.writer(f).writerow(header)

def load_logged_results() -> Dict[Tuple[float, ...], float]:
    """
    Load previous evaluations from CSV into a dict:
      key(tuple) -> error
    If file doesn't exist or header mismatch, returns empty.
    """
    if not RUN_LOG.exists():
        return {}

    logged: Dict[Tuple[float, ...], float] = {}

    with RUN_LOG.open("r", newline="") as f:
        reader = csv.DictReader(f)
        # If the file header doesn't match current N_ACTIVE_PAIRS, don't reuse
        needed_cols = ["timestamp"] + [f"c{i}" for i in range(1, N_ACTIVE_PAIRS + 1)] + [f"m{i}" for i in range(1, N_ACTIVE_PAIRS + 1)] + ["error_percent"]
        for col in needed_cols:
            if col not in (reader.fieldnames or []):
                return {}

        for row in reader:
            try:
                coeffs = {}
                for i in range(1, N_ACTIVE_PAIRS + 1):
                    coeffs[f"c{i}"] = float(row[f"c{i}"])
                    coeffs[f"m{i}"] = float(row[f"m{i}"])
                err = float(row["error_percent"])
                logged[coeffs_to_key(coeffs)] = err
            except Exception:
                pass

    return logged

def append_log_row(coeffs: Dict[str, float], err: float):
    row = [datetime.now().isoformat()]
    for i in range(1, N_ACTIVE_PAIRS + 1):
        ci = float(coeffs.get(f"c{i}", 0.0))
        mi = float(coeffs.get(f"m{i}", 0.0))
        log10_ci = np.log10(ci) if ci > 0 else -999.0
        row += [log10_ci, ci, mi]
    row += [err]
    with RUN_LOG.open("a", newline="") as f:
        csv.writer(f).writerow(row)


# ============================================================
# OPTIMIZER WRAPPER
# ============================================================

class Runner:
    def __init__(self, opt_pairs: List[int], logged: Dict[Tuple[float, ...], float]):
        self.opt_pairs = opt_pairs
        self.logged = logged               # cross-session dedupe
        self.cache: Dict[Tuple[float, ...], float] = {}  # in-run cache

        self.eval_count = 0
        self.best_err = float("inf")
        self.best_coeffs: Dict[str, float] | None = None
        self.t0 = time.time()

    def __call__(self, x: np.ndarray) -> float:
        coeffs = x_to_coeffs(x, self.opt_pairs)
        key = coeffs_to_key(coeffs)

        # In-run cache
        if key in self.cache:
            return self.cache[key]

        # Cross-run dedupe
        if key in self.logged:
            old_err = self.logged[key]
            print(f"Found duplicate in log. Reusing error: {old_err}")
            self.cache[key] = old_err
            return old_err

        self.eval_count += 1
        elapsed = time.time() - self.t0

        # Pretty print current coeffs for active pairs
        print(f"\n=== Eval {self.eval_count}/{MAX_EVALS} | elapsed {elapsed:.0f}s ===")
        for i in range(1, N_ACTIVE_PAIRS + 1):
            ci = coeffs.get(f"c{i}", None)
            mi = coeffs.get(f"m{i}", None)
            if ci is not None and mi is not None:
                print(f"  pair {i}: c{i}={ci:.6e} MPa, m{i}={mi:.4f}" + (" (fixed)" if i in FIXED_PAIRS else ""))

        err = objective_coeffs(coeffs, timeout=FEBIO_TIMEOUT, threads=THREADS)

        # Log it
        append_log_row(coeffs, err)

        # Store for dedupe (future) + cache (this run)
        self.logged[key] = err
        self.cache[key] = err

        if err >= 1e8:
            print("WARNING: penalty returned (FEBio failed/timeout). Consider tighter bounds or higher timeout.")
        print(f"Error: {err:.6f}%")

        if err < self.best_err:
            self.best_err = err
            self.best_coeffs = dict(coeffs)
            print(f"NEW BEST: {err:.6f}%")

        # Stopping conditions
        if err <= TARGET_ERR:
            raise StopIteration(f"Reached target error <= {TARGET_ERR}%")
        if self.eval_count >= MAX_EVALS:
            raise StopIteration(f"Reached MAX_EVALS={MAX_EVALS}")

        return float(err)


def main():
    # Create log if needed
    ensure_log_header()

    # Build problem definition
    x0, bounds, opt_pairs = build_x0_and_bounds()
    logged = load_logged_results()

    print("=== Configuration ===")
    print("N_ACTIVE_PAIRS:", N_ACTIVE_PAIRS)
    print("Fixed pairs:", FIXED_PAIRS if FIXED_PAIRS else "(none)")
    print("Optimizing pairs:", opt_pairs)
    print("THREADS:", THREADS, "TIMEOUT:", FEBIO_TIMEOUT, "MAX_EVALS:", MAX_EVALS)
    print("Log file:", RUN_LOG.resolve())

    runner = Runner(opt_pairs, logged)

    try:
        res = minimize(
            runner,
            x0=x0,
            method="Powell",
            bounds=bounds,
            options={"xtol": 1e-3, "ftol": 1e-3, "disp": True, "maxiter": 10**9},
        )
        print("\nOptimization finished normally.")
        print(res)

    except StopIteration as e:
        print(f"\nStopped early: {e}")

    if runner.best_coeffs is not None:
        print("\n=== BEST FOUND ===")
        for i in range(1, N_ACTIVE_PAIRS + 1):
            ci = runner.best_coeffs.get(f"c{i}", 0.0)
            mi = runner.best_coeffs.get(f"m{i}", 0.0)
            print(f"c{i} = {ci:.6e} MPa, m{i} = {mi:.6f}")
        print(f"error = {runner.best_err:.6f}%")
    else:
        print("\nNo successful evaluations (all runs failed / timed out).")


if __name__ == "__main__":
    main()