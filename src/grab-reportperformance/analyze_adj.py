import pandas as pd
import os

files = [f for f in os.listdir("downloads") if "penyetanmbaksussuperfood" in f and f.endswith(".csv")]
files.sort(key=lambda x: os.path.getmtime(os.path.join("downloads", x)), reverse=True)
file_path = os.path.join("downloads", files[0])

df = pd.read_csv(file_path)
df["Updated On DT"] = pd.to_datetime(df["Updated On"], errors="coerce", format="%d %b %Y %I:%M %p")
df["Category"] = df["Category"].fillna("").astype(str).str.strip().str.lower()
df["Status"] = df["Status"].fillna("").astype(str).str.strip().str.lower()
df["Net Sales"] = pd.to_numeric(df["Net Sales"], errors="coerce").fillna(0)

feb = df[(df["Updated On DT"] >= "2026-02-01") & (df["Updated On DT"] < "2026-03-01")]

# Categories
print("Category counts in Feb:")
print(feb["Category"].value_counts())

# Check for Adjustments
adj = feb[feb["Category"] == "adjustment"]
print("\nAdjustment rows in Feb:")
print(adj[["Created On", "Updated On", "Category", "Status", "Long Order ID", "Net Sales", "Description"]])

# Check for Payments
payments = feb[feb["Category"] == "payment"]
print(f"\nUnique Order IDs in Payment category: {payments['Long Order ID'].nunique()}")

# If we combine Payment and Adjustment
combined = feb[feb["Category"].isin(["payment", "adjustment"])]
print(f"Unique Order IDs in Payment + Adjustment: {combined['Long Order ID'].nunique()}")
print(f"Total Net Sales in Payment + Adjustment: {combined['Net Sales'].sum()}")
