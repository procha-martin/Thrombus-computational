import pandas as pd
import numpy as np

df = pd.read_csv("run_log.csv")

# Example computations
best = df.loc[df["percent_error"].idxmin()]
mean_err = df["percent_error"].mean()
std_err = df["percent_error"].std()

print("Best run:")
print(best)

print("Mean error:", mean_err)
print("Std error:", std_err)
