from pathlib import Path
import subprocess
import os

FEBIO_EXE = Path(r"C:\Program Files\FEBioStudio\bin\febio4.exe")

def run_febio(feb_file, workdir=None, timeout=600, threads=4):
    feb_file = Path(feb_file).resolve()
    if not feb_file.exists():
        raise FileNotFoundError(feb_file)

    workdir = Path(workdir).resolve() if workdir else feb_file.parent

    cmd = [str(FEBIO_EXE), "-i", str(feb_file)]

    env = os.environ.copy()
    env["OMP_NUM_THREADS"] = str(threads)

    # These don’t hurt and sometimes help if any BLAS is involved:
    env["MKL_NUM_THREADS"] = "1"
    env["OPENBLAS_NUM_THREADS"] = "1"
    env["NUMEXPR_NUM_THREADS"] = "1"

    return subprocess.run(
        cmd,
        cwd=workdir,
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env,
    )
