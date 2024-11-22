"""Goal: test GitHub workflows to run python"""

import argparse

import pandas as pd

# ----------

print("Hello world from this script.")

df = pd.DataFrame([[1, 2, 3], [4, 5, 1000]])
print(df)

# --- Write current date and time into a file
with open("datasets/hello_out.txt", "w") as fp:
    fp.write(f"Hello. It's {pd.Timestamp.now().isoformat()}\n")
