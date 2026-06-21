import pandas as pd
import os

file_path = "downloads/grab_transactions_api_penyetanmbaksussuperfood_2026-02-05_to_2026-05-06.csv"
df = pd.read_csv(file_path)

print(f"Total Rows: {len(df)}")
print("\nValue Counts for Category:")
print(df["Category"].value_counts())

print("\nValue Counts for Status:")
print(df["Status"].value_counts())

# Analysis of Category vs Status
print("\nCategory vs Status Cross-tab:")
print(pd.crosstab(df["Category"], df["Status"]))

# Check for rows with Net Sales but not Category 'payment'
non_payment_sales = df[df["Category"].str.strip().str.lower() != "payment"]["Net Sales"].sum()
print(f"\nTotal Net Sales from NON-payment categories: {non_payment_sales}")

# Check for duplicated Long Order IDs
dup_ids = df[df["Long Order ID"].duplicated(keep=False)].sort_values("Long Order ID")
if not dup_ids.empty:
    print(f"\nNumber of duplicated Long Order IDs: {dup_ids['Long Order ID'].nunique()}")
    print("Example of duplicates (first 5 IDs):")
    print(dup_ids[["Long Order ID", "Category", "Status", "Net Sales"]].head(10))

# Check for rows where Net Sales is NaN or 0 but status is Completed/Transferred
anomaly_sales = df[(df["Net Sales"].isna() | (df["Net Sales"] == 0)) & (df["Status"].isin(["Completed", "Transferred"]))]
print(f"\nRows with 0/NaN Net Sales but valid Status: {len(anomaly_sales)}")

# Summary by Month using the same logic as result.py
df["Created On"] = pd.to_datetime(df["Created On"], errors="coerce", format="%d %b %Y %I:%M %p")
df["Month"] = df["Created On"].dt.to_period("M")
monthly_all = df.groupby("Month")["Net Sales"].sum()
print("\nMonthly Net Sales (ALL rows):")
print(monthly_all)

# Monthly using result.py logic (Payment only)
payment_only = df[df["Category"].str.strip().str.lower() == "payment"]
monthly_payment = payment_only.groupby("Month")["Net Sales"].sum()
print("\nMonthly Net Sales (Payment category only):")
print(monthly_payment)
