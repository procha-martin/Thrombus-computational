# from febio_xml import read_coeffs_from_feb, get_logfile_path

# FEB_PATH = r"C:\Users\Pedro\Documents\VS code\.venv\Febio_optimizer\Simple Shear Cube_120525_modelrun.feb"

# names = ["c1","c2","c3","c4","c5","c6","m1","m2","m3","m4","m5","m6"]

# coeffs = read_coeffs_from_feb(FEB_PATH, names)
# print(coeffs)

# print(get_logfile_path(FEB_PATH))

# from parsing import (
#     parse_reaction_text,
#     read_experiment,
#     align_by_step,
#     percent_error
# )

# sim = parse_reaction_text("shit2.txt")
# exp = read_experiment("shear_Sample35_.csv")

# sim2, exp2 = align_by_step(sim, exp)
# err = percent_error(sim2, exp2)

# print(f"Percent error = {err:.3f}%")

# import parsing
# print(dir(parsing))

# from parsing import (
#     parse_reaction_text,
#     read_experiment,
#     align_by_step,
#     percent_error
# )

# sim = parse_reaction_text("shit2.txt")
# exp = read_experiment("shear_Sample35_.csv")

# sim2, exp2 = align_by_step(sim, exp)
# err = percent_error(sim2, exp2)

# print(f"Percent error = {err:.3f}%")

# print(sim.head())
# print(exp.head())
# print(sim.tail())
# print(exp.tail())

from run_febio import run_febio

result = run_febio(
    "Simple Shear Cube_120525_modelrun.feb"
)

print("Return code:", result.returncode)
print("STDOUT (last 20 lines):")
print("\n".join(result.stdout.splitlines()[-20:]))

print("STDERR:")
print(result.stderr)


