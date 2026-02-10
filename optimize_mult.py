from scipy.optimize import minimize
from objective import objective

x0 = [10, 0, 0, 0, 0, 0]

res = minimize(
    objective,
    x0=x0,
    bounds=[(0,50)] * 6,
    method="L-BFGS-B"
)

print(res)
