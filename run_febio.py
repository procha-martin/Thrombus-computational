from pathlib import Path
import subprocess

FEBIO_EXE = Path(
    r"C:\Program Files\FEBioStudio\bin\febio4.exe"
)

def run_febio(feb_file, workdir=None, timeout=120):
    """
    Run FEBio on a .feb file.

    Returns:
        completed_process
    """
    feb_file = Path(feb_file).resolve()

    if not feb_file.exists():
        raise FileNotFoundError(feb_file)

    if workdir is None:
        workdir = feb_file.parent
    else:
        workdir = Path(workdir).resolve()

    cmd = [
        str(FEBIO_EXE),
        "-i", str(feb_file)
    ]

    result = subprocess.run(
        cmd,
        cwd=workdir,
        capture_output=True,
        text=True,
        timeout=timeout
    )

    return result
