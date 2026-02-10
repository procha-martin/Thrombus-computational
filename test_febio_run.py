from run_febio import run_febio

result = run_febio(
    "Simple Shear Cube_120525_modelrun.feb"
)

print("Return code:", result.returncode)
print("STDOUT (last 20 lines):")
print("\n".join(result.stdout.splitlines()[-20:]))

print("STDERR:")
print(result.stderr)
