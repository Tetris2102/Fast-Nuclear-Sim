import pandas as pd

# 1. Load the CSV file
df = pd.read_csv("fission_coupling_table.csv")

# 2. Keep rows where the target column is NOT 0
df = df[df["delta_fission_rate_per_one_fission_per_s"] != 0]

# 3. Save the filtered data back to a CSV
df.to_csv("fission_coupling_table_2.csv", index=False)

