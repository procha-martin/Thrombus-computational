from scipy.optimize import minimize_scalar
from objective import objective_c1

def objective_log_c1(log10_c1):
    c1 = 10 ** log10_c1
    return objective_c1(c1)

res = minimize_scalar(
    objective_log_c1,
    bounds=(-10, 0),  # c1 from 1e-10 to 1
    method="bounded",
    options={"xatol": 1e-3, "maxiter": 40}
)
print("best c1:", 10**res.x, "best err:", res.fun)


print("Optimization result:")
print(res)

