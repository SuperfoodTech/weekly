import pandas as pd
import requests
import io

CSV_URL = "https://docs.google.com/spreadsheets/d/14eCb8DAEXhmbYj9MFj2KzC7AhkulbCbSNPltN2m-go0/export?format=csv&gid=0"

try:
    print("Fetching sheet...")
    resp = requests.get(CSV_URL, timeout=30)
    resp.raise_for_status()
    df = pd.read_csv(io.StringIO(resp.text))
    print(f"Total rows fetched: {len(df)}")
    print("Columns in sheet:", df.columns.tolist())
    
    # Let's search for "krispy" or "superfood" in any column
    matches = []
    for idx, row in df.iterrows():
        row_str = str(row.values).lower()
        if "krispy" in row_str or "superfood" in row_str:
            matches.append(row)
            
    print(f"\nFound {len(matches)} matching rows:")
    for idx, match in enumerate(matches):
        print(f"\nMatch #{idx+1}:")
        for col in df.columns:
            print(f"  {col}: {match[col]}")
            
except Exception as e:
    print(f"Error: {e}")
