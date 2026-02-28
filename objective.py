from pathlib import Path
import tempfile
import shutil
import uuid
import csv

from edit_feb import write_coeffs
from run_febio import run_febio
from parsing import (
    parse_febio_log_by_step,
    read_experiment,
    percent_error,
)

from febio_xml import update_log_data_file, extract_surface_node_ids
from parsing import resample_to_n_points
from parsing import nrmse
import subprocess
import time

CALL_COUNT = 0
MAX_CALLS = 30          # match maxiter in optimize.py
FEBIO_TIMEOUT = 120     # seconds


# ---------------- Paths ----------------
BASE_DIR = Path(__file__).resolve().parent
TEMPLATE_FEB = BASE_DIR / "Simple Shear Cube_120525_modelrun.feb"
EXPERIMENT_FILE = BASE_DIR / "shear_Sample35_.csv"

# ---------------- Experiment (load once) ----------------
EXP_DATA = read_experiment(EXPERIMENT_FILE)

# ---------------- Node IDs (extract from FEB automatically) ----------------
TOP_FACE_NODE_IDS = extract_surface_node_ids(TEMPLATE_FEB, "PrescribedDisplacement4")


# ---------------- Logging ----------------
LOG_CSV = BASE_DIR / "run_log.csv"
LOG_HEADER = ["c1", "m1", "error_percent"]

if not LOG_CSV.exists():
    with LOG_CSV.open("w", newline="") as f:
        csv.writer(f).writerow(LOG_HEADER)


def objective_c1(c1):
    global CALL_COUNT
    CALL_COUNT += 1

    print(f"\n=== Optimization iteration {CALL_COUNT}/{MAX_CALLS} ===")
    print(f"[objective] Testing c1 = {c1:.3e}")

    run_id = uuid.uuid4().hex[:8]
    run_dir = Path(tempfile.mkdtemp(prefix=f"febio_{run_id}_"))

    try:
        feb_file = run_dir / "model.feb"
        reaction_file = run_dir / "node_rx force.txt"

        write_coeffs(
            template_feb=TEMPLATE_FEB,
            output_feb=feb_file,
            coeffs={"c1": float(c1)},
            #reaction_file=reaction_file
        )

        # Force logfile to write into this run folder
        update_log_data_file(
            feb_file,
            tag="node_data",
            data_name="Rx",
            new_file=reaction_file,
        )
        
        start_time = time.time()
        print(f"[objective] Running FEBio...")

        try:
            result = run_febio(
                feb_file,
                workdir=run_dir,
                timeout=FEBIO_TIMEOUT,
                threads=4
            )
        except subprocess.TimeoutExpired:
            elapsed = time.time() - start_time
            print(f"[objective] FEBio TIMEOUT after {elapsed:.1f} s")

            err = 1e9
            with LOG_CSV.open("a", newline="") as f:
                csv.writer(f).writerow([float(c1), err])

            return err
        
        elapsed = time.time() - start_time
        print(f"[objective] FEBio finished in {elapsed:.1f} s")

        if result.returncode != 0:
            print("[objective] FEBio returned non-zero exit code")
            err = 1e9
            with LOG_CSV.open("a", newline="") as f:
                csv.writer(f).writerow([float(c1), err])
            return err

        print("\n=== FEBio run diagnostics ===")
        print("Run dir:", run_dir)
        print("Files in run dir:", [p.name for p in run_dir.glob("*")])

        # Show the logfile section FEBio actually sees (from the written model.feb)
        try:
            feb_txt = feb_file.read_text(errors="ignore")
            lo = feb_txt.lower().find("<logfile")
            hi = feb_txt.lower().find("</logfile>")
            if lo != -1 and hi != -1:
                print("\n<logfile> section in model.feb:")
                print("Expecting Rx logfile at:", reaction_file)
                print(feb_txt[lo:hi+10])
            else:
                print("\nCould not find <logfile> section in model.feb")
        except Exception as e:
            print("Could not read model.feb:", e)

        # If expected Rx logfile missing, print any warnings/errors from model.log
        if not reaction_file.exists():
            log_path = run_dir / "model.log"
            print("\nRx logfile missing:", reaction_file)
            if log_path.exists():
                log_txt = log_path.read_text(errors="ignore").splitlines()
                print("\nLast ~80 lines of model.log:")
                for line in log_txt[-80:]:
                    print(line)
            else:
                print("model.log not found.")

            # Keep folder so you can inspect it manually
            raise FileNotFoundError(f"Expected logfile not found: {reaction_file}")
            

        
        sim = parse_febio_log_by_step(
            reaction_file,
            ids_keep=TOP_FACE_NODE_IDS,
            agg="sum",
        )

        # Drop step 0 from sim if it is just a zero preload (optional but common)
        sim_use = sim[sim["Step"] > 0].reset_index(drop=True)

        # Resample experiment to match simulation length
        exp_use = resample_to_n_points(
            EXP_DATA.rename(columns={"X": "Step"}),
            n=len(sim_use),
        )

        # --- Compute error (NRMSE-based) ---
        err = 100.0 * nrmse(sim_use["Value"], exp_use["Value"])

        print(f"[objective] c1={c1:.3e} → error={err:.3e}")

        # --- Log result ---
        with LOG_CSV.open("a", newline="") as f:
            csv.writer(f).writerow([float(c1), err])

        return err

    finally:
        # 🔥 Cleanup everything
        shutil.rmtree(run_dir, ignore_errors=True)

def objective_coeffs(coeffs: dict, *, timeout=120, threads=2, debug=False):
    run_id = uuid.uuid4().hex[:8]
    run_dir = Path(tempfile.mkdtemp(prefix=f"febio_{run_id}_"))

    try:
        feb_file = run_dir / "model.feb"
        reaction_file = run_dir / "node_rx force.txt"
        model_log = run_dir / "model.log"

        write_coeffs(
            template_feb=TEMPLATE_FEB,
            output_feb=feb_file,
            coeffs={k: float(v) for k, v in coeffs.items()},
        )

        update_log_data_file(
            feb_file,
            tag="node_data",
            data_name="Rx",
            new_file=reaction_file,
        )

        if debug:
            print("\n[debug] run_dir:", run_dir)
            print("[debug] coeffs:", coeffs)

        try:
            result = run_febio(feb_file, workdir=run_dir, timeout=timeout, threads=6)
            t0 = time.time()
        except subprocess.TimeoutExpired:
            if debug:
                print("[debug] TIMEOUT")
            return 1e9
        except Exception as e:
            if debug:
                print("[debug] Exception launching/running FEBio:", repr(e))
            return 1e9
        except subprocess.TimeoutExpired:
            if debug:
                print(f"[debug] TIMEOUT after {time.time() - t0:.1f}s")
            return 1e9

        if debug:
            print("[debug] returncode:", result.returncode)
            print("[debug] files:", [p.name for p in run_dir.glob("*")])
            print("reaction_file exists:", reaction_file.exists())

        if result.returncode != 0:
            if debug and model_log.exists():
                tail = model_log.read_text(errors="ignore").splitlines()[-60:]
                print("[debug] model.log tail:\n" + "\n".join(tail))
            return 1e9
            

        if not reaction_file.exists():
            if debug:
                print("[debug] reaction file missing:", reaction_file)
                if model_log.exists():
                    tail = model_log.read_text(errors="ignore").splitlines()[-60:]
                    print("[debug] model.log tail:\n" + "\n".join(tail))
            return 1e9

        sim = parse_febio_log_by_step(reaction_file, ids_keep=TOP_FACE_NODE_IDS, agg="sum")
        sim_use = sim[sim["Step"] > 0].reset_index(drop=True)
        exp_use = resample_to_n_points(EXP_DATA.rename(columns={"X": "Step"}), n=len(sim_use))

        err = 100.0 * nrmse(sim_use["Value"], exp_use["Value"])
        return float(err)

    finally:
        # Keep failed folders if debug=True so you can inspect them
        if debug:
            print("[debug] keeping run folder:", run_dir)
        else:
            shutil.rmtree(run_dir, ignore_errors=True)
