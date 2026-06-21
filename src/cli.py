#!/usr/bin/env python3
"""
═══════════════════════════════════════════════════════════════
  TASK WEEKLY — Unified OFD Transaction Pipeline
  Grab & Shopee in one CLI
═══════════════════════════════════════════════════════════════

Usage:
  python cli.py                      
  python cli.py grab  --start 2026-05-05 --end 2026-05-11
  python cli.py shopee --start 2026-05-05 --end 2026-05-11
  python cli.py all   --start 2026-05-05 --end 2026-05-11
"""

import argparse
import asyncio
import sys
import os
from datetime import datetime, timedelta

def normalize_date_string(date_str: str) -> str:
    """
    Parses a date string in various formats (DD-MM-YYYY, YYYY-MM-DD, etc.)
    and returns a standardized YYYY-MM-DD string.
    """
    for fmt in ("%d-%m-%Y", "%Y-%m-%d", "%d/%m/%Y", "%Y/%m/%d"):
        try:
            dt = datetime.strptime(date_str.strip(), fmt)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            continue
    raise ValueError(f"Format tanggal tidak valid: '{date_str}'. Gunakan DD-MM-YYYY atau YYYY-MM-DD.")


# ── Colour helpers (ANSI) ──────────────────────────────────────────────
RESET  = "\033[0m"
BOLD   = "\033[1m"
GREEN  = "\033[92m"
CYAN   = "\033[96m"
YELLOW = "\033[93m"
RED    = "\033[91m"
MAGENTA = "\033[95m"
DIM    = "\033[2m"


def banner():
    # Solid 3D Rounded Gradient Banner for OFD REPORT
    FONT = {
        'O': [" ▄██████▄ ", "██▀    ▀██", "██      ██", "██      ██", " ▀██████▀ "],
        'F': ["██████████", "██        ", "███████   ", "██        ", "██        "],
        'D': ["████████▄ ", "██     ▀██", "██      ██", "██     ▄██", "████████▀ "],
        'R': ["████████▄ ", "██     ▀██", "████████▀ ", "██     ▀██", "██      ██"],
        'E': ["██████████", "██        ", "███████   ", "██        ", "██████████"],
        'P': ["████████▄ ", "██     ▀██", "████████▀ ", "██        ", "██        "],
        'T': ["█████████", "    ██   ", "    ██   ", "    ██   ", "    ██   "]
    }

    def get_word_lines(word):
        widths = [len(FONT[char][0]) for char in word]
        letter_grids = []
        for char in word:
            grid = FONT[char]
            width = len(grid[0])
            comp_grid = [[' ' for _ in range(width + 1)] for _ in range(6)]
            for r in range(5):
                for c in range(width):
                    val = grid[r][c]
                    if val != ' ':
                        comp_grid[r][c] = val
            for r in range(5):
                for c in range(width):
                    val = grid[r][c]
                    if val != ' ':
                        if comp_grid[r+1][c+1] == ' ':
                            comp_grid[r+1][c+1] = '▒'
            letter_grids.append(comp_grid)
        return letter_grids, widths

    gradient_colors = [196, 197, 203, 204, 209, 210, 215, 216, 217, 223, 224, 225, 230, 231]
    
    # Render OFD
    t_grids, t_widths = get_word_lines("OFD")
    t_total = sum(t_widths) + 2 * 2
    
    # Render REPORT
    w_grids, w_widths = get_word_lines("REPORT")
    w_total = sum(w_widths) + 5 * 2

    print(f"  [90m=================================================================[0m")
    
    # Print OFD
    for r in range(6):
        line = "       "
        curr_col = 0
        for l_idx, grid in enumerate(t_grids):
            width = len(grid[0])
            for c in range(width):
                char = grid[r][c]
                factor = curr_col / max(1, t_total - 1)
                color_idx = min(len(gradient_colors) - 1, max(0, int(factor * (len(gradient_colors) - 1))))
                color_code = gradient_colors[color_idx]
                if char == '▒':
                    line += "[38;5;238m█[0m"
                elif char != ' ':
                    line += f"[38;5;{color_code}m{char}[0m"
                else:
                    line += ' '
                curr_col += 1
            line += "  "
            curr_col += 2
        print(line)
        
    print()
    
    # Print REPORT
    for r in range(6):
        line = "  "
        curr_col = 0
        for l_idx, grid in enumerate(w_grids):
            width = len(grid[0])
            for c in range(width):
                char = grid[r][c]
                factor = curr_col / max(1, w_total - 1)
                color_idx = min(len(gradient_colors) - 1, max(0, int(factor * (len(gradient_colors) - 1))))
                color_code = gradient_colors[color_idx]
                if char == '▒':
                    line += "[38;5;238m█[0m"
                elif char != ' ':
                    line += f"[38;5;{color_code}m{char}[0m"
                else:
                    line += ' '
                curr_col += 1
            line += "  "
            curr_col += 2
        print(line)
        
    print(f"  [90m=================================================================[0m")
    print()


# ── Helpers ────────────────────────────────────────────────────────────

def _resolve_python_executable() -> str:
    """
    Returns path to local .venv/bin/python if it exists,
    otherwise falls back to sys.executable.
    """
    base = os.path.dirname(os.path.abspath(__file__))
    venv_python = os.path.join(base, ".venv", "bin", "python")
    if os.path.isfile(venv_python):
        return venv_python
    return sys.executable


def _resolve_output_dir(platform_name: str, start_date: str, end_date: str) -> str:
    """
    Build an absolute output path under:
      task-weekly/src/laporan/{platform}/{start_date}_to_{end_date}
    """
    base = os.path.dirname(os.path.abspath(__file__))
    out = os.path.join(base, "laporan", platform_name, f"{start_date}_to_{end_date}")
    os.makedirs(out, exist_ok=True)
    return out


def _resolve_shopee_merchant(outlet_name: str, branch_name: str = None, task_choice: str = "2") -> str:
    """
    Lookup 'Merchant Name' Shopee dari Google Sheets berdasarkan 'Nama Outlet'
    dan opsional 'Cabang'.

    Logika:
      1. Jika branch_name diberikan → cari baris dengan Nama Outlet + Cabang cocok
         (cabang di Discord form = kolom 'Cabang' di GSheets)
         Ambil Merchant Name dari baris tersebut.
      2. Jika tidak ada match dengan cabang, atau branch_name tidak diberikan
         → fallback ke lookup Nama Outlet saja (ambil merchant pertama)
      3. Jika tidak ada match sama sekali → fallback ke outlet_name asli

    Returns:
        str: Merchant Name yang bersih (tanpa trailing underscore/spasi)
    """
    base = os.path.dirname(os.path.abspath(__file__))
    if task_choice == "1":
        GSHEETS_URL = (
            "https://docs.google.com/spreadsheets/d/14eCb8DAEXhmbYj9MFj2KzC7AhkulbCbSNPltN2m-go0"
            "/export?format=csv&gid=880434015"
        )
        cache_path = os.path.join(base, "baseline", "shopee", "data", "master_merchants_cache.csv")
    else:
        GSHEETS_URL = (
            "https://docs.google.com/spreadsheets/d/14eCb8DAEXhmbYj9MFj2KzC7AhkulbCbSNPltN2m-go0"
            "/export?format=csv&gid=0"
        )
        cache_path = os.path.join(base, "shopee-omzet-automation", "data", "master_merchants_cache.csv")

    def _clean(name: str) -> str:
        return str(name).strip().rstrip('_').strip()

    try:
        import pandas as pd
        import io
        import time
        import requests

        df = None
        loaded_from_cache = False
        if task_choice == "1":
            # Baseline: selalu coba unduh data segar terlebih dahulu
            try:
                resp = requests.get(GSHEETS_URL, timeout=10)
                resp.raise_for_status()
                df = pd.read_csv(io.StringIO(resp.text))
                os.makedirs(os.path.dirname(cache_path), exist_ok=True)
                df.to_csv(cache_path, index=False)
            except Exception as download_err:
                print(f"  {YELLOW}[SHOPEE LOOKUP] Gagal mengunduh GSheets: {download_err}. Menggunakan cache jika ada...{RESET}")
                if os.path.exists(cache_path):
                    df = pd.read_csv(cache_path)
                    loaded_from_cache = True
        else:
            # Weekly: tetap gunakan cache 24 jam jika ada
            if os.path.exists(cache_path):
                age_hours = (time.time() - os.path.getmtime(cache_path)) / 3600
                if age_hours < 24:
                    df = pd.read_csv(cache_path)
                    loaded_from_cache = True

            if df is None:
                resp = requests.get(GSHEETS_URL, timeout=15)
                df = pd.read_csv(io.StringIO(resp.text))
                os.makedirs(os.path.dirname(cache_path), exist_ok=True)
                df.to_csv(cache_path, index=False)

        def do_lookup(dataframe):
            # Base filter: ShopeeFood + Nama Outlet cocok
            outlet_lower = outlet_name.strip().lower()
            if task_choice == "1":
                b_filter = (
                    (dataframe['Aplikasi'].str.contains("Shopee", na=False, case=False)) &
                    (dataframe['Nama Outlet'].str.strip().str.lower() == outlet_lower)
                )
            else:
                b_filter = (
                    (dataframe['Aplikasi'] == 'ShopeeFood') &
                    (dataframe['Status'] == 'Live') &
                    (dataframe['Nama Outlet'].str.strip().str.lower() == outlet_lower)
                )

            # ── Strategi 1: Lookup dengan Cabang (paling presisi) ──────────
            if branch_name:
                branch_lower = branch_name.strip().lower()
                branch_col = 'Cabang' if 'Cabang' in dataframe.columns else 'Brand'
                if branch_col in dataframe.columns:
                    sf_with_branch = dataframe[
                        b_filter &
                        (dataframe[branch_col].str.strip().str.lower() == branch_lower)
                    ]
                else:
                    sf_with_branch = pd.DataFrame()
                if not sf_with_branch.empty:
                    m_name = _clean(sf_with_branch.iloc[0]['Merchant Name'])
                    if m_name and m_name not in ('-', 'nan'):
                        print(f"  {CYAN}[SHOPEE LOOKUP] Outlet+Cabang '{outlet_name} / {branch_name}'"
                              f" → Merchant: '{m_name}'{RESET}")
                        return m_name

            # ── Strategi 2: Lookup hanya Nama Outlet ───────────────────────
            sf_df = dataframe[b_filter]
            if not sf_df.empty:
                # Hapus duplikat Merchant Name (satu outlet bisa banyak row per merchant)
                unique_merchants = (
                    sf_df['Merchant Name']
                    .apply(_clean)
                    .loc[lambda s: (s != '-') & (s != 'nan') & (s != '')]
                    .drop_duplicates()
                    .tolist()
                )
                if unique_merchants:
                    if task_choice == "1":
                        merchants_str = "|".join(unique_merchants)
                        print(f"  {CYAN}[SHOPEE LOOKUP] Outlet '{outlet_name}' punya"
                              f" {len(unique_merchants)} merchant Shopee: {unique_merchants}."
                              f" Menggunakan semuanya: '{merchants_str}'{RESET}")
                        return merchants_str
                    else:
                        if len(unique_merchants) == 1:
                            print(f"  {CYAN}[SHOPEE LOOKUP] Outlet '{outlet_name}'"
                                  f" → Merchant: '{unique_merchants[0]}'{RESET}")
                            return unique_merchants[0]
                        else:
                            # Beberapa merchant Shopee untuk outlet ini → ambil yang pertama
                            # (biasanya semua di bawah satu akun Shopee yang sama)
                            print(f"  {CYAN}[SHOPEE LOOKUP] Outlet '{outlet_name}' punya"
                                  f" {len(unique_merchants)} merchant Shopee: {unique_merchants}."
                                  f" Menggunakan: '{unique_merchants[0]}'{RESET}")
                            return unique_merchants[0]
            return None

        result = do_lookup(df)
        if result is None and loaded_from_cache:
            print(f"  {YELLOW}[SHOPEE LOOKUP] Cache returned no merchants. Downloading fresh data...{RESET}")
            resp = requests.get(GSHEETS_URL, timeout=15)
            df = pd.read_csv(io.StringIO(resp.text))
            os.makedirs(os.path.dirname(cache_path), exist_ok=True)
            df.to_csv(cache_path, index=False)
            result = do_lookup(df)

        if result is not None:
            return result

        print(f"  {YELLOW}[SHOPEE LOOKUP] Tidak ditemukan Merchant Name untuk '{outlet_name}',"
              f" fallback ke nama outlet.{RESET}")
    except Exception as e:
        print(f"  {YELLOW}[SHOPEE LOOKUP] Gagal lookup GSheets: {e}. Fallback ke nama outlet.{RESET}")

    return outlet_name


# ── Runners ────────────────────────────────────────────────────────────

def run_grab(start_date: str, end_date: str, user_filter: str = None, outlet_filter: str = None, branch_filter: str = None):
    """
    Delegates to the existing Grab weekly pipeline.
    Working directory is set to grab-reportperformance/weekly so that
    relative paths (browser_data/, downloads/) resolve correctly.
    Output is routed to task-weekly/src/laporan/grab/{start}_to_{end}.
    """
    grab_weekly_dir = os.path.join(os.path.dirname(__file__), "grab-reportperformance", "weekly")
    
    if not os.path.isdir(grab_weekly_dir):
        print(f"{RED}[ERROR]{RESET} Grab weekly directory not found: {grab_weekly_dir}")
        return False

    output_dir = _resolve_output_dir("grab", start_date, end_date)

    import subprocess
    
    python_exe = _resolve_python_executable()
    cmd = [
        python_exe, "main.py",
        "--start-date", start_date,
        "--end-date", end_date,
        "--output-dir", output_dir,
    ]
    if user_filter:
        cmd.extend(["--user", user_filter])
    if outlet_filter:
        cmd.extend(["--outlet", outlet_filter])
    if branch_filter:
        cmd.extend(["--branch", branch_filter])

    print(f"\n{GREEN}{BOLD}▶ GRAB PIPELINE{RESET}")
    print(f"  {DIM}Directory : {grab_weekly_dir}{RESET}")
    print(f"  {DIM}Output    : {output_dir}{RESET}")
    print(f"  {DIM}Date Range: {start_date} → {end_date}{RESET}")
    print()

    result = subprocess.run(cmd, cwd=grab_weekly_dir)
    
    if result.returncode == 0:
        print(f"\n{GREEN}✓ Grab pipeline completed successfully.{RESET}")
        return True
    else:
        print(f"\n{RED}✗ Grab pipeline exited with code {result.returncode}.{RESET}")
        return False

def run_grab_vb(start_date: str, end_date: str, user_filter: str = None, outlet_filter: str = None, branch_filter: str = None):
    """
    Delegates to the Grab VB pipeline.
    Output is routed to task-weekly/src/laporan/grab_vb/{start}_to_{end}.
    """
    grab_vb_dir = os.path.join(os.path.dirname(__file__), "VB", "grab")
    
    if not os.path.isdir(grab_vb_dir):
        print(f"{RED}[ERROR]{RESET} Grab VB directory not found: {grab_vb_dir}")
        return False

    output_dir = _resolve_output_dir("grab_vb", start_date, end_date)

    import subprocess
    
    python_exe = _resolve_python_executable()
    cmd = [
        python_exe, "run_baseline.py",
        "--start-date", start_date,
        "--end-date", end_date,
        "--output-dir", output_dir,
    ]
    if user_filter:
        cmd.extend(["--user", user_filter])
    if outlet_filter:
        cmd.extend(["--outlet", outlet_filter])
    if branch_filter:
        cmd.extend(["--branch", branch_filter])

    print(f"\n{MAGENTA}{BOLD}▶ GRAB VB PIPELINE{RESET}")
    print(f"  {DIM}Directory : {grab_vb_dir}{RESET}")
    print(f"  {DIM}Output    : {output_dir}{RESET}")
    print(f"  {DIM}Date Range: {start_date} → {end_date}{RESET}")
    print()

    result = subprocess.run(cmd, cwd=grab_vb_dir)
    
    if result.returncode == 0:
        print(f"\n{GREEN}✓ Grab VB pipeline completed successfully.{RESET}")
        return True
    else:
        print(f"\n{RED}✗ Grab VB pipeline exited with code {result.returncode}.{RESET}")
        return False



def run_grab_baseline(start_date: str, end_date: str, user_filter: str = None, outlet_filter: str = None, branch_filter: str = None):
    grab_baseline_dir = os.path.join(os.path.dirname(__file__), "baseline", "grab")
    
    if not os.path.isdir(grab_baseline_dir):
        print(f"{RED}[ERROR]{RESET} Grab baseline directory not found: {grab_baseline_dir}")
        return False

    output_dir = _resolve_output_dir("grab_baseline", start_date, end_date)

    import subprocess
    
    python_exe = _resolve_python_executable()
    cmd = [
        python_exe, "run_baseline.py",
        "--start-date", start_date,
        "--end-date", end_date,
        "--output-dir", output_dir,
    ]
    if user_filter:
        cmd.extend(["--user", user_filter])
    if outlet_filter:
        cmd.extend(["--outlet", outlet_filter])
    if branch_filter:
        cmd.extend(["--branch", branch_filter])

    print(f"\n{GREEN}{BOLD}▶ GRAB BASELINE PIPELINE{RESET}")
    print(f"  {DIM}Directory : {grab_baseline_dir}{RESET}")
    print(f"  {DIM}Output    : {output_dir}{RESET}")
    print(f"  {DIM}Date Range: {start_date} → {end_date}{RESET}")
    print()

    result = subprocess.run(cmd, cwd=grab_baseline_dir)
    
    if result.returncode == 0:
        print(f"\n{GREEN}✓ Grab Baseline completed successfully.{RESET}")
        return True
    else:
        print(f"\n{RED}✗ Grab Baseline exited with code {result.returncode}.{RESET}")
        return False


def run_shopee(start_date: str, end_date: str, merchant_filter: str = None):
    """
    Delegates to the existing Shopee weekly pipeline.
    Working directory is set to shopee-omzet-automation so that
    relative paths (core/) resolve correctly.
    Output is routed to task-weekly/src/laporan/shopee/{start}_to_{end}.
    """
    shopee_dir = os.path.join(os.path.dirname(__file__), "shopee-omzet-automation")
    
    if not os.path.isdir(shopee_dir):
        print(f"{RED}[ERROR]{RESET} Shopee directory not found: {shopee_dir}")
        return False

    output_dir = _resolve_output_dir("shopee", start_date, end_date)

    import subprocess
    
    python_exe = _resolve_python_executable()
    cmd = [
        python_exe, "weekly/run_weekly.py",
        "--start", start_date,
        "--end", end_date,
        "--output-dir", output_dir,
    ]
    if merchant_filter:
        cmd.extend(["--merchant", merchant_filter])

    print(f"\n{MAGENTA}{BOLD}▶ SHOPEE PIPELINE{RESET}")
    print(f"  {DIM}Directory : {shopee_dir}{RESET}")
    print(f"  {DIM}Output    : {output_dir}{RESET}")
    print(f"  {DIM}Date Range: {start_date} → {end_date}{RESET}")
    print()

    result = subprocess.run(cmd, cwd=shopee_dir)
    
    if result.returncode == 0:
        print(f"\n{GREEN}✓ Shopee pipeline completed successfully.{RESET}")
        return True
    else:
        print(f"\n{RED}✗ Shopee pipeline exited with code {result.returncode}.{RESET}")
        return False


def run_shopee_baseline(start_date: str, end_date: str, merchant_filter: str = None, bd_filter: str = None):
    shopee_baseline_dir = os.path.join(os.path.dirname(__file__), "baseline", "shopee")
    
    if not os.path.isdir(shopee_baseline_dir):
        print(f"{RED}[ERROR]{RESET} Shopee baseline directory not found: {shopee_baseline_dir}")
        return False

    output_dir = _resolve_output_dir("shopee_baseline", start_date, end_date)

    import subprocess
    
    python_exe = _resolve_python_executable()
    cmd = [
        python_exe, "run_baseline.py",
        "--start", start_date,
        "--end", end_date,
        "--output-dir", output_dir,
    ]
    if merchant_filter:
        cmd.extend(["--merchant", merchant_filter])
    if bd_filter:
        cmd.extend(["--bd", bd_filter])

    print(f"\n{MAGENTA}{BOLD}▶ SHOPEE BASELINE PIPELINE{RESET}")
    print(f"  {DIM}Directory : {shopee_baseline_dir}{RESET}")
    print(f"  {DIM}Output    : {output_dir}{RESET}")
    print(f"  {DIM}Date Range: {start_date} → {end_date}{RESET}")
    print()

    result = subprocess.run(cmd, cwd=shopee_baseline_dir)
    
    if result.returncode == 0:
        print(f"\n{GREEN}✓ Shopee Baseline completed successfully.{RESET}")
        return True
    else:
        print(f"\n{RED}✗ Shopee Baseline exited with code {result.returncode}.{RESET}")
        return False


def run_shopee_vb(start_date: str, end_date: str, merchant_filter: str = None):
    shopee_vb_dir = os.path.join(os.path.dirname(__file__), "VB", "shopee")
    
    if not os.path.isdir(shopee_vb_dir):
        print(f"{RED}[ERROR]{RESET} Shopee VB directory not found: {shopee_vb_dir}")
        return False

    output_dir = _resolve_output_dir("shopee_vb", start_date, end_date)

    import subprocess
    
    python_exe = _resolve_python_executable()
    cmd = [
        python_exe, "run_baseline.py",
        "--start", start_date,
        "--end", end_date,
        "--output-dir", output_dir,
    ]
    if merchant_filter:
        cmd.extend(["--merchant", merchant_filter])

    print(f"\n{MAGENTA}{BOLD}▶ SHOPEE VB PIPELINE{RESET}")
    print(f"  {DIM}Directory : {shopee_vb_dir}{RESET}")
    print(f"  {DIM}Output    : {output_dir}{RESET}")
    print(f"  {DIM}Date Range: {start_date} → {end_date}{RESET}")
    print()

    result = subprocess.run(cmd, cwd=shopee_vb_dir)
    
    if result.returncode == 0:
        print(f"\n{GREEN}✓ Shopee VB completed successfully.{RESET}")
        return True
    else:
        print(f"\n{RED}✗ Shopee VB exited with code {result.returncode}.{RESET}")
        return False


def run_gofood(start_date: str, end_date: str, outlet_filter: str = None, branch_filter: str = None, task_choice: str = "2", no_sheet: bool = False, clear_cache: bool = False):
    """
    Delegates to the GoFood Login/Dashboard utility.
    Working directory is set to goscrapperv2 so that
    relative paths and imports resolve correctly.
    """
    gofood_dir = os.path.join(os.path.dirname(__file__), "goscrapperv2")
    
    if not os.path.isdir(gofood_dir):
        print(f"{RED}[ERROR]{RESET} GoFood directory not found: {gofood_dir}")
        return False

    if task_choice == "1":
        output_dir = _resolve_output_dir("gofood_baseline", start_date, end_date)
    else:
        output_dir = _resolve_output_dir("gofood", start_date, end_date)

    import subprocess
    
    python_exe = _resolve_python_executable()
    # Menjalankan gofood.py untuk otomatis login (jika perlu) dan scrape data
    cmd = [
        python_exe, "gofood.py",
        "--start-date", start_date,
        "--end-date", end_date,
        "--output-dir", output_dir,
        "--task", task_choice
    ]
    if outlet_filter:
        cmd.extend(["--outlet", outlet_filter])
    if branch_filter:
        cmd.extend(["--branch", branch_filter])
    if no_sheet:
        cmd.append("--no-sheet")
    if clear_cache:
        cmd.append("--clear-cache")

    print(f"\n{YELLOW}{BOLD}▶ GOFOOD AUTO LOGIN & SCRAPE PIPELINE{RESET}")
    print(f"  {DIM}Directory : {gofood_dir}{RESET}")
    if outlet_filter:
        print(f"  {DIM}Outlet    : {outlet_filter}{RESET}")
    if branch_filter:
        print(f"  {DIM}Cabang    : {branch_filter}{RESET}")
    print(f"  {DIM}Output Dir: {output_dir}{RESET}")
    print(f"  {DIM}Date Range: {start_date} → {end_date}{RESET}")
    print()

    result = subprocess.run(cmd, cwd=gofood_dir)
    
    if result.returncode == 0:
        print(f"\n{GREEN}✓ GoFood login dan scrape data berhasil.{RESET}")
        return True
    else:
        print(f"\n{RED}✗ GoFood login/scrape data keluar dengan kode {result.returncode}.{RESET}")
        return False


# ── Interactive Mode ──────────────────────────────────────────────────

def interactive_mode():
    """Let the user pick task, platform & dates interactively."""
    # Clear screen to hide dependency check details
    os.system('cls' if os.name == 'nt' else 'clear')
    banner()

    # ─ Task selection ─
    print(f"  {BOLD}Pilih Task:{RESET}")
    print(f"    {GREEN}[1]{RESET} Baseline")
    print(f"    {CYAN}[2]{RESET} Weekly")
    print(f"    {MAGENTA}[3]{RESET} Virtual Brand (VB)")
    print()

    while True:
        task_choice = input(f"  {BOLD}Pilihan (1/2/3):{RESET} ").strip()
        if task_choice in ("1", "2", "3"):
            break
        print(f"  {RED}Input tidak valid. Masukkan 1, 2, atau 3.{RESET}")

    if task_choice == "1":
        print(f"\n  {GREEN}[INFO] Mengaktifkan Mode Baseline.{RESET}")
        import pandas as pd
        import requests
        import io

        print(f"\n  {CYAN}[INFO] Mengunduh daftar outlet terbaru dari Google Sheets...{RESET}")
        CSV_URL = "https://docs.google.com/spreadsheets/d/14eCb8DAEXhmbYj9MFj2KzC7AhkulbCbSNPltN2m-go0/export?format=csv&gid=880434015"
        try:
            resp = requests.get(CSV_URL, timeout=30)
            resp.raise_for_status()
            df = pd.read_csv(io.StringIO(resp.text))
        except Exception as e:
            print(f"  {RED}[ERROR] Gagal mengunduh Google Sheets: {e}{RESET}")
            sys.exit(1)
            
        df_live = df.copy()
        outlets = sorted(df_live["Nama Outlet"].dropna().unique())
        print(f"\n  {BOLD}Pilih Outlet untuk Baseline (Menarik seluruh cabang Grab, Shopee, & GoFood sekaligus):{RESET}")
        for idx, o_name in enumerate(outlets):
            print(f"    {GREEN}[{idx + 1}]{RESET} {o_name}")
        print()
        while True:
            try:
                o_choices = input(f"  {BOLD}Pilih nomor outlet (contoh: 1,3 atau 'all'):{RESET} ").strip()
                if o_choices.lower() == "all":
                    unified_outlet = outlets
                    break
                else:
                    indices = [int(x.strip()) for x in o_choices.split(",") if x.strip()]
                    if all(1 <= i <= len(outlets) for i in indices):
                        unified_outlet = [outlets[i - 1] for i in indices]
                        break
            except ValueError: pass
            print(f"  {RED}Pilihan tidak valid.{RESET}")

        print(f"\n  {BOLD}Pilih Platform untuk ditarik Baseline-nya:{RESET}")
        print(f"    {GREEN}[1]{RESET} GrabFood")
        print(f"    {GREEN}[2]{RESET} ShopeeFood")
        print(f"    {GREEN}[3]{RESET} GoFood")
        print(f"    {GREEN}[4]{RESET} Semua (Grab + Shopee + GoFood)")
        print()
        while True:
            plat_choice = input(f"  {BOLD}Pilihan (contoh: 1,3 atau 4):{RESET} ").strip()
            if plat_choice == "4" or plat_choice.lower() == "all":
                platform = "all"
                break
            else:
                indices = [x.strip() for x in plat_choice.split(",") if x.strip()]
                if all(i in ("1", "2", "3") for i in indices) and indices:
                    plat_map = {"1": "grab", "2": "shopee", "3": "gofood"}
                    platform = ",".join([plat_map[i] for i in indices])
                    break
            print(f"  {RED}Input tidak valid.{RESET}")

        scope_choice = "2"
        outlet = unified_outlet
        branch = None

        # Terjemahkan Nama Outlet ke Merchant Name (nama toko spesifik di ShopeeFood)
        shopee_merchant = unified_outlet
        try:
            if isinstance(unified_outlet, list):
                shopee_rows = df_live[df_live["Nama Outlet"].isin(unified_outlet) & (df_live["Aplikasi"].str.contains("Shopee", na=False, case=False))]
            else:
                shopee_rows = df_live[(df_live["Nama Outlet"] == unified_outlet) & (df_live["Aplikasi"].str.contains("Shopee", na=False, case=False))]
            
            if not shopee_rows.empty:
                merchants_list = []
                for _, r in shopee_rows.iterrows():
                    val = r.get("Merchant Name", "")
                    if pd.notna(val) and str(val).strip() != "-" and str(val).strip() != "":
                        merchants_list.append(str(val).strip().rstrip('_').strip())
                # Deduplicate preserving order
                seen = set()
                merchants_list = [x for x in merchants_list if not (x in seen or seen.add(x))]
                if merchants_list:
                    shopee_merchant = merchants_list

        except Exception:
            pass

    else:
        # ─ Platform selection ─
        print(f"\n  {BOLD}Pilih platform:{RESET}")
        print(f"    {GREEN}[1]{RESET} Grab")
        print(f"    {MAGENTA}[2]{RESET} Shopee")
        if task_choice != "3":
            print(f"    {YELLOW}[3]{RESET} GoFood")
            print(f"    {CYAN}[4]{RESET} Semua Platform (Grab + Shopee + GoFood)")
        else:
            print(f"    {CYAN}[4]{RESET} Kedua Platform (Grab + Shopee)")
        print()

        while True:
            choice = input(f"  {BOLD}Pilihan (contoh: 1,2 atau 4):{RESET} ").strip()
            if choice == "4" or choice.lower() == "all":
                platform = "all"
                break
            else:
                indices = [x.strip() for x in choice.split(",") if x.strip()]
                valid_choices = ("1", "2", "3") if task_choice != "3" else ("1", "2")
                if all(i in valid_choices for i in indices) and indices:
                    plat_map = {"1": "grab", "2": "shopee", "3": "gofood"}
                    platform = ",".join([plat_map[i] for i in indices])
                    break
            print(f"  {RED}Input tidak valid.{RESET}")

        # ─ Scope selection ─
        print(f"\n  {BOLD}Pilih cakupan outlet:{RESET}")
        print(f"    {GREEN}[1]{RESET} Pilih semua outlet")
        print(f"    {YELLOW}[2]{RESET} Pilih custom (Filter spesifik){RESET}")
        print()

        while True:
            scope_choice = input(f"  {BOLD}Pilihan (1/2):{RESET} ").strip()
            if scope_choice in ("1", "2"):
                break
            print(f"  {RED}Input tidak valid. Masukkan 1 atau 2.{RESET}")

        outlet = []
        branch = []
        shopee_merchant = []

        if scope_choice == "2":
            import pandas as pd
            import requests
            import io

            print(f"\n  {CYAN}[INFO] Mengunduh daftar merchant terbaru dari Google Sheets...{RESET}")
            CSV_URL_MAIN = "https://docs.google.com/spreadsheets/d/14eCb8DAEXhmbYj9MFj2KzC7AhkulbCbSNPltN2m-go0/export?format=csv&gid=0"
            CSV_URL_VB = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRYSUnKOqk29LCktTxdb0wPLbWMbRaWRP3eC_UA4AwYod1FW6zDMhtLMC5ghIvot2B8upCDfBsn-TCP/pub?gid=565510790&single=true&output=csv"
            
            try:
                resp_main = requests.get(CSV_URL_MAIN, timeout=30)
                resp_main.raise_for_status()
                df_main = pd.read_csv(io.StringIO(resp_main.text))
            except Exception as e:
                print(f"  {RED}[ERROR] Gagal mengunduh Google Sheets utama: {e}{RESET}")
                sys.exit(1)
                
            df_vb = pd.DataFrame()
            if task_choice == "3" and ("shopee" in platform or platform == "all"):
                try:
                    resp_vb = requests.get(CSV_URL_VB, timeout=30)
                    resp_vb.raise_for_status()
                    df_vb = pd.read_csv(io.StringIO(resp_vb.text))
                except Exception as e:
                    print(f"  {RED}[ERROR] Gagal mengunduh Google Sheets VB: {e}{RESET}")
                    sys.exit(1)

            # --- FILTER CUSTOM GRAB ---
            if "grab" in platform or platform == "all":
                if task_choice == "3":
                    CSV_URL_VB_GRAB = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRYSUnKOqk29LCktTxdb0wPLbWMbRaWRP3eC_UA4AwYod1FW6zDMhtLMC5ghIvot2B8upCDfBsn-TCP/pub?gid=978201567&single=true&output=csv"
                    try:
                        resp_grab_vb = requests.get(CSV_URL_VB_GRAB, timeout=30)
                        resp_grab_vb.raise_for_status()
                        df_grab_vb = pd.read_csv(io.StringIO(resp_grab_vb.text))
                        if "Notes" in df_grab_vb.columns:
                            df_grab = df_grab_vb[~df_grab_vb["Notes"].astype(str).str.contains("restricted", na=False, case=False)].copy()
                        else:
                            df_grab = df_grab_vb.copy()
                        # Map Portal to Nama Outlet
                        if "Portal" in df_grab.columns:
                            df_grab["Nama Outlet"] = df_grab["Portal"]
                        else:
                            df_grab["Nama Outlet"] = "Unknown"
                    except Exception as e:
                        print(f"  {RED}[ERROR] Gagal mengunduh Google Sheets Grab VB: {e}{RESET}")
                        sys.exit(1)
                else:
                    df_grab = df_main[df_main["Aplikasi"].str.contains("Grab", na=False, case=False) & df_main["Status"].str.contains("Live", na=False, case=False)]
                
                if not df_grab.empty:
                    outlets_list = sorted(df_grab["Nama Outlet"].dropna().unique())
                    print(f"\n  {BOLD}Pilih Outlet Grab:{RESET}")
                    for idx, o_name in enumerate(outlets_list):
                        print(f"    {GREEN}[{idx + 1}]{RESET} {o_name}")
                    print()
                    while True:
                        try:
                            o_choices = input(f"  {BOLD}Pilih nomor outlet Grab (contoh: 1,3 atau 'all'):{RESET} ").strip()
                            if o_choices.lower() == "all":
                                outlet = outlets_list
                                break
                            else:
                                indices = [int(x.strip()) for x in o_choices.split(",") if x.strip()]
                                if all(1 <= i <= len(outlets_list) for i in indices):
                                    outlet = [outlets_list[i - 1] for i in indices]
                                    break
                        except ValueError: pass
                        print(f"  {RED}Pilihan tidak valid.{RESET}")

                    if len(outlet) == 1:
                        if task_choice == "3":
                            branch = []
                        else:
                            df_branch = df_grab[df_grab["Nama Outlet"] == outlet[0]]
                            branch_col = "Cabang" if "Cabang" in df_branch.columns else "Brand"
                            branches = sorted(df_branch[branch_col].dropna().unique()) if branch_col in df_branch.columns else []
                            print(f"\n  {BOLD}Pilih Cabang Grab untuk '{outlet[0]}':{RESET}")
                            for idx, b_name in enumerate(branches):
                                print(f"    {GREEN}[{idx + 1}]{RESET} {b_name}")
                            print()
                            while True:
                                try:
                                    b_choices = input(f"  {BOLD}Pilih nomor cabang Grab (contoh: 1,2 atau 'all'):{RESET} ").strip()
                                    if b_choices.lower() == "all":
                                        branch = branches
                                        break
                                    else:
                                        indices = [int(x.strip()) for x in b_choices.split(",") if x.strip()]
                                        if all(1 <= i <= len(branches) for i in indices):
                                            branch = [branches[i - 1] for i in indices]
                                            break
                                except ValueError: pass
                                print(f"  {RED}Pilihan tidak valid.{RESET}")
                    else:
                        # Multiple outlets chosen -> all branches for those outlets
                        branch = []
                else:
                    print(f"  {RED}[ERROR] Tidak ada outlet Grab yang berstatus Live di Google Sheets.{RESET}")
                    sys.exit(1)

            # --- FILTER CUSTOM SHOPEE ---
            if "shopee" in platform or platform == "all":
                if task_choice == "3":
                    df_shopee = df_vb
                else:
                    df_shopee = df_main[df_main["Aplikasi"].str.contains("Shopee", na=False, case=False) & df_main["Status"].str.contains("Live", na=False, case=False)]
                    
                if not df_shopee.empty:
                    merchants = sorted(df_shopee["Merchant Name"].dropna().unique())
                    print(f"\n  {BOLD}Pilih Merchant ShopeeFood:{RESET}")
                    for idx, m_name in enumerate(merchants):
                        print(f"    {GREEN}[{idx + 1}]{RESET} {m_name}")
                    print()
                    while True:
                        try:
                            m_choices = input(f"  {BOLD}Pilih nomor merchant Shopee (contoh: 1,2 atau 'all'):{RESET} ").strip()
                            if m_choices.lower() == "all":
                                shopee_merchant = merchants
                                break
                            else:
                                indices = [int(x.strip()) for x in m_choices.split(",") if x.strip()]
                                if all(1 <= i <= len(merchants) for i in indices):
                                    shopee_merchant = [merchants[i - 1] for i in indices]
                                    break
                        except ValueError: pass
                        print(f"  {RED}Pilihan tidak valid.{RESET}")
                else:
                    print(f"  {RED}[ERROR] Tidak ada merchant Shopee di Google Sheets.{RESET}")
                    sys.exit(1)

            # --- FILTER CUSTOM GOFOOD ---
            if ("gofood" in platform or platform == "all") and task_choice != "3":
                df_gofood = df_main[df_main["Aplikasi"].str.contains("GoFood", na=False, case=False) & df_main["Status"].str.contains("Live", na=False, case=False)]
                if not df_gofood.empty:
                    gofood_outlets = sorted(df_gofood["Nama Outlet"].dropna().unique())
                    print(f"\n  {BOLD}Pilih Outlet GoFood:{RESET}")
                    for idx, o_name in enumerate(gofood_outlets):
                        print(f"    {GREEN}[{idx + 1}]{RESET} {o_name}")
                    print()
                    while True:
                        try:
                            o_choices = input(f"  {BOLD}Pilih nomor outlet GoFood (contoh: 1,3 atau 'all'):{RESET} ").strip()
                            if o_choices.lower() == "all":
                                if not outlet: # If user selected all in platform prompt, we append
                                    outlet = gofood_outlets
                                else:
                                    outlet.extend([x for x in gofood_outlets if x not in outlet])
                                break
                            else:
                                indices = [int(x.strip()) for x in o_choices.split(",") if x.strip()]
                                if all(1 <= i <= len(gofood_outlets) for i in indices):
                                    selected_go = [gofood_outlets[i - 1] for i in indices]
                                    if not outlet:
                                        outlet = selected_go
                                    else:
                                        outlet.extend([x for x in selected_go if x not in outlet])
                                    break
                        except ValueError: pass
                        print(f"  {RED}Pilihan tidak valid.{RESET}")
                else:
                    print(f"  {RED}[ERROR] Tidak ada outlet GoFood yang berstatus Live di Google Sheets.{RESET}")
                    sys.exit(1)

    # ─ Date input ─
    print()
    
    # Calculate dynamic shortcut dates
    today = datetime.now()
    if task_choice == "3":
        # VB: Senin ke Senin
        days_since_monday = today.weekday()
        recent_monday = today - timedelta(days=days_since_monday)
        previous_monday = recent_monday - timedelta(days=7)
        
        default_end = recent_monday.strftime("%Y-%m-%d")
        default_start = previous_monday.strftime("%Y-%m-%d")
        shortcut_label = "Senin-Senin"
    else:
        # Weekly/Baseline: Senin ke Minggu
        days_to_last_sunday = today.weekday() + 1
        last_sunday = today - timedelta(days=days_to_last_sunday)
        last_monday = last_sunday - timedelta(days=6)
        
        default_end = last_sunday.strftime("%Y-%m-%d")
        default_start = last_monday.strftime("%Y-%m-%d")
        shortcut_label = "Senin-Minggu"
    
    while True:
        date_choice = input(f"  {BOLD}Gunakan tanggal 7 hari terakhir ({shortcut_label}: {default_start} s/d {default_end})? (y/n):{RESET} ").strip().lower()
        if date_choice in ("y", "yes", "n", "no"):
            break
        print(f"  {RED}Input tidak valid. Masukkan y atau n.{RESET}")

    if date_choice in ("y", "yes"):
        start_date = default_start
        end_date = default_end
    else:
        print()
        start_input = input(f"  {BOLD}Start date (YYYY-MM-DD){RESET} [{default_start}]: ").strip()
        end_input   = input(f"  {BOLD}End date   (YYYY-MM-DD){RESET} [{default_end}]: ").strip()

        start_date = start_input or default_start
        end_date   = end_input or default_end

    # Validate dates
    try:
        s = datetime.strptime(start_date, "%Y-%m-%d")
        e = datetime.strptime(end_date, "%Y-%m-%d")
        if s > e:
            print(f"\n  {RED}[ERROR] Start date harus sebelum atau sama dengan end date.{RESET}")
            sys.exit(1)
    except ValueError as err:
        print(f"\n  {RED}[ERROR] Format tanggal tidak valid: {err}{RESET}")
        sys.exit(1)

    # ─ Headless Mode ─
    while True:
        headless_choice = input(f"\n  {BOLD}Jalankan mode headless (tanpa GUI browser)? (Y/n):{RESET} ").strip().lower()
        if headless_choice in ("y", "yes", "", "true", "1"):
            is_headless = True
            break
        elif headless_choice in ("n", "no", "false", "0"):
            is_headless = False
            break
        print(f"  {RED}Input tidak valid. Masukkan y atau n.{RESET}")

    # ─ No Sheet Mode (GoFood) ─
    no_sheet = False
    if "gofood" in platform or platform == "all":
        while True:
            sheet_choice = input(f"\n  {BOLD}Matikan pengiriman data ke Google Sheets (GoFood)? (y/N):{RESET} ").strip().lower()
            if sheet_choice in ("y", "yes", "1", "true"):
                no_sheet = True
                break
            elif sheet_choice in ("n", "no", "", "0", "false"):
                no_sheet = False
                break
            print(f"  {RED}Input tidak valid. Masukkan y atau n.{RESET}")

    # ─ Confirmation ─
    if platform == "all":
        if task_choice == "3":
            platform_label = "Kedua Platform (Grab + Shopee)"
        else:
            platform_label = "Semua Platform (Grab + Shopee + GoFood)"
    else:
        labels = {"grab": "Grab", "shopee": "Shopee", "gofood": "GoFood"}
        platform_label = " + ".join([labels[p] for p in platform.split(",") if p in labels])
    date_folder = f"{start_date}_to_{end_date}"
    
    print(f"\n  {CYAN}{'─'*50}{RESET}")
    print(f"  Platform : {BOLD}{platform_label}{RESET}")
    if scope_choice == "2":
        if outlet:
            print(f"  Grab Outlet : {BOLD}{outlet} ({branch}){RESET}")
        if shopee_merchant:
            print(f"  Shopee Merchant : {BOLD}{shopee_merchant}{RESET}")
    else:
        print(f"  Outlet   : {BOLD}Semua Outlet{RESET}")
    print(f"  Start    : {BOLD}{start_date}{RESET}")
    print(f"  End      : {BOLD}{end_date}{RESET}")
    print(f"  Headless : {BOLD}{'Ya' if is_headless else 'Tidak (Dengan GUI)'}{RESET}")
    print(f"  Output   : {DIM}laporan/{{platform}}/{date_folder}/{RESET}")
    print(f"  {CYAN}{'─'*50}{RESET}")
    
    confirm = input(f"\n  {BOLD}Lanjutkan? (Y/n):{RESET} ").strip().lower()
    if confirm in ("n", "no"):
        print(f"\n  {YELLOW}Dibatalkan.{RESET}")
        sys.exit(0)

    return task_choice, platform, start_date, end_date, outlet, branch, shopee_merchant, is_headless, no_sheet


# ── Discord Webhook Notifier ───────────────────────────────────────────

def _notify_discord_pdf(outlet, start_date, end_date, aplikator,
                        pdf_url, pdf_name, omzet_gr, omzet_sf,
                        order_gr, order_sf, omzet_go="Rp 0", order_go="0"):
    """
    Kirim embed notifikasi PDF ke Discord channel via webhook.
    Hanya aktif ketika OFD_DISCORD_MODE=1 dan OFD_WEBHOOK_URL tersedia.
    Saat dijalankan manual, fungsi ini tidak melakukan apa-apa.
    """
    return  # Disabled by user request

    try:
        import requests as _req

        omzet_lines = []
        order_lines = []
        lower_app = aplikator.lower()
        if "go" in lower_app or "all" in lower_app:
            omzet_lines.append(f"GoFood: **{omzet_go}**")
            order_lines.append(f"GoFood: **{order_go}**")
        if "grab" in lower_app or "all" in lower_app:
            omzet_lines.append(f"GrabFood: **{omzet_gr}**")
            order_lines.append(f"GrabFood: **{order_gr}**")
        if "shopee" in lower_app or "all" in lower_app:
            omzet_lines.append(f"ShopeeFood: **{omzet_sf}**")
            order_lines.append(f"ShopeeFood: **{order_sf}**")
            
        omzet_str = "\n".join(omzet_lines) if omzet_lines else "-"
        order_str = "\n".join(order_lines) if order_lines else "-"

        embed = {
            "title"      : "📄 Laporan Baseline Selesai!",
            "description": (
                f"Laporan untuk **{outlet}** telah berhasil dibuat dan siap diunduh.\n\n"
                f"🔗 **[Klik di sini untuk membuka PDF]({pdf_url})**"
            ),
            "color"      : 0x00C853,  # hijau
            "fields"     : [
                {"name": "📍 Outlet",          "value": outlet,                              "inline": True},
                {"name": "📱 Aplikator",        "value": aplikator,                           "inline": True},
                {"name": "📅 Rentang Tanggal",  "value": f"`{start_date}` → `{end_date}`",   "inline": False},
                {"name": "📊 Rata-rata Omzet",  "value": omzet_str,                           "inline": True},
                {"name": "🛒 Rata-rata Order",  "value": order_str,                           "inline": True},
                {"name": "📁 Nama File",        "value": f"`{pdf_name}`",                    "inline": False},
            ],
            "footer"     : {"text": "Sistem Rekap Laporan Otomatis • OFD Report"},
            "timestamp"  : datetime.now().isoformat(),
        }

        payload = {"embeds": [embed]}
        resp = _req.post(webhook_url, json=payload, timeout=15)
        if resp.status_code in (200, 204):
            print(f"  {GREEN}✓ Notifikasi PDF berhasil dikirim ke Discord channel.{RESET}")
        else:
            print(f"  {YELLOW}⚠ Discord webhook response: {resp.status_code}{RESET}")
    except Exception as exc:
        print(f"  {YELLOW}⚠ Gagal kirim notifikasi Discord: {exc}{RESET}")


# ── Main ──────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Unified Weekly OFD Transaction Pipeline — Grab & Shopee",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python cli.py                                    # Interactive mode
  python cli.py grab  --start 2026-05-05 --end 2026-05-11
  python cli.py shopee --start 2026-05-05 --end 2026-05-11
  python cli.py all   --start 2026-05-05 --end 2026-05-11
        """,
    )
    parser.add_argument(
        "platform",
        nargs="?",
        type=lambda x: x.lower(),
        default=None,
        help="Platform to run: grab, shopee, gofood, all",
    )
    parser.add_argument("--start", type=str, default=None, help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end",   type=str, default=None, help="End date (YYYY-MM-DD)")
    parser.add_argument("--user",  type=str, default=None, help="Filter specific username (Grab only)")
    parser.add_argument("--task",  type=str, choices=["1", "2", "3"], default=None, help="Task type: 1 for Baseline, 2 for Weekly, 3 for VB")
    parser.add_argument("--outlet", type=str, default=None, help="Filter specific outlet name")
    parser.add_argument("--branch", type=str, default=None, help="Filter specific branch name")
    parser.add_argument("--bd", type=str, default=None, help="Filter specific BD name (Shopee Baseline)")
    parser.add_argument("--headless", type=str, choices=["true", "false", "1", "0", "yes", "no"], default=None, help="Set headless mode (true/false)")
    parser.add_argument("--no-sheet", action="store_true", help="Nonaktifkan pengiriman data ke Google Sheets (GoFood)")

    args = parser.parse_args()

    # ── Discord Bridge Mode ─────────────────────────────────────────────
    # Dipanggil dari bridge/run_pipeline.js — bypass interactive mode.
    # Ketika dijalankan manual dari terminal, blok ini diabaikan sepenuhnya.
    bd = None
    if os.environ.get("OFD_DISCORD_MODE") == "1":
        task_choice     = os.environ.get("OFD_TASK_CHOICE", "2")
        platform        = os.environ.get("OFD_PLATFORM", args.platform or "all")
        start_date      = args.start or os.environ.get("OFD_START", "")
        end_date        = args.end   or os.environ.get("OFD_END", "")
        outlet          = os.environ.get("OFD_OUTLET") or None
        branch          = os.environ.get("OFD_CABANG") or None
        bd              = os.environ.get("OFD_BD") or None
        # Lookup Merchant Name Shopee dari GSheets berdasarkan Nama Outlet
        # Ini mengatasi mismatch nama outlet (Discord) vs merchant name Shopee (GSheets)
        shopee_merchant = _resolve_shopee_merchant(outlet, branch_name=branch, task_choice=task_choice) if outlet else None
        
        is_headless_str = os.environ.get("OFD_HEADLESS", "true")
        is_headless = is_headless_str.lower() in ("true", "1", "yes")
        no_sheet_str = os.environ.get("OFD_NO_SHEET", "false")
        no_sheet = no_sheet_str.lower() in ("true", "1", "yes")

        print(f"\n{CYAN}[DISCORD MODE] Task={task_choice} | Platform={platform} | Outlet={outlet} | Brand={branch} | BD={bd} | Headless={is_headless} | NoSheet={no_sheet}{RESET}")
        banner()
    # ── Normal CLI Mode ─────────────────────────────────────────────────
    elif args.platform is None or args.start is None or args.end is None:
        task_choice, platform, start_date, end_date, outlet, branch, shopee_merchant, is_headless, no_sheet = interactive_mode()
    else:
        task_choice = args.task or "2"
        platform   = args.platform.lower()
        start_date = args.start
        end_date   = args.end
        outlet     = args.outlet
        branch     = args.branch
        shopee_merchant = _resolve_shopee_merchant(outlet, branch_name=branch, task_choice=task_choice) if outlet else None
        
        if args.headless is not None:
            is_headless = args.headless.lower() in ("true", "1", "yes")
        else:
            is_headless = True
            
        no_sheet = args.no_sheet
            
        banner()

    # Set HEADLESS env var for sub-scripts
    os.environ["HEADLESS"] = "True" if is_headless else "False"

    # Standardize/Normalize date strings to YYYY-MM-DD
    try:
        start_date = normalize_date_string(start_date)
        end_date   = normalize_date_string(end_date)
    except ValueError as err:
        print(f"\n  {RED}[ERROR] {err}{RESET}")
        sys.exit(1)

    # Convert singles to lists for uniform handling if passed via args
    if not isinstance(outlet, list): outlet = [outlet] if outlet else []
    if not isinstance(branch, list): branch = [branch] if branch else []
    if not isinstance(shopee_merchant, list):
        shopee_merchant = [shopee_merchant] if shopee_merchant else []
    else:
        # If it is a list of lists or similar, flatten it
        new_list = []
        for item in shopee_merchant:
            if isinstance(item, list):
                new_list.extend(item)
            else:
                new_list.append(item)
        shopee_merchant = new_list

    # Split any pipe-separated strings in the list to individual merchants
    temp_shopee = []
    for m in shopee_merchant:
        if m:
            temp_shopee.extend([x.strip() for x in m.split("|") if x.strip()])
    shopee_merchant = temp_shopee

    # ── Execute ──
    results = {}
    start_time = datetime.now()

    if "grab" in platform or platform == "all":
        o_str = "|".join(outlet) if outlet else None
        b_str = "|".join(branch) if branch else None
        name_key = "Grab"
        if task_choice == "1":
            results[name_key] = run_grab_baseline(start_date, end_date, user_filter=args.user, outlet_filter=o_str, branch_filter=b_str)
        elif task_choice == "3":
            results[name_key] = run_grab_vb(start_date, end_date, user_filter=args.user, outlet_filter=o_str, branch_filter=b_str)
        else:
            results[name_key] = run_grab(start_date, end_date, user_filter=args.user, outlet_filter=o_str, branch_filter=b_str)

    if "shopee" in platform or platform == "all":
        if task_choice == "3":
            # For VB, pass all selected merchants as a pipe-separated string to utilize its internal parallel ThreadPoolExecutor
            m_str = "|".join(shopee_merchant) if shopee_merchant else None
            results["Shopee_VB"] = run_shopee_vb(start_date, end_date, merchant_filter=m_str)
        else:
            m_str = "|".join(shopee_merchant) if shopee_merchant else None
            name_key = "Shopee"
            if task_choice == "1":
                results[name_key] = run_shopee_baseline(start_date, end_date, merchant_filter=m_str, bd_filter=args.bd or bd)
            elif task_choice == "2":
                results[name_key] = run_shopee(start_date, end_date, merchant_filter=m_str)

    if ("gofood" in platform or platform == "all") and task_choice != "3":
        outlets_to_run = outlet if outlet else [None]
        branches_to_run = branch if branch else [None]
        for o in outlets_to_run:
            for b in branches_to_run:
                name_key = f"GoFood_{o}_{b}" if o and b else (f"GoFood_{o}" if o else "GoFood")
                results[name_key] = run_gofood(start_date, end_date, outlet_filter=o, branch_filter=b, task_choice=task_choice, no_sheet=no_sheet)

    # ── Summary ──
    elapsed = datetime.now() - start_time
    minutes = int(elapsed.total_seconds() // 60)
    seconds = int(elapsed.total_seconds() % 60)

    date_folder = f"{start_date}_to_{end_date}"
    base_dir = os.path.dirname(os.path.abspath(__file__))
    
    # ── Merge Baseline Outputs ──
    if task_choice == "1":
        print(f"\n{YELLOW}{BOLD}▶ PENGGABUNGAN LAPORAN BASELINE{RESET}")
        try:
            import pandas as pd
            frames = []
            
            outlet_safe = str(outlet or "").strip().replace(" ", "_").replace("/", "_").replace("\\", "_")
            
            # Find Grab Baseline output
            grab_paths_to_check = []
            o_str = "|".join(outlet) if outlet else None
            b_str = "|".join(branch) if branch else None
            outlet_safe = str(o_str or "").strip().replace(" ", "_").replace("/", "_").replace("\\", "_").replace("|", "_")
            if b_str:
                branch_safe = str(b_str).strip().replace(" ", "_").replace("/", "_").replace("\\", "_").replace("|", "_")
                filename_prefix = f"BASELINE_CUSTOM_{outlet_safe}_{branch_safe}"
            else:
                filename_prefix = f"BASELINE_CUSTOM_{outlet_safe}_"
            
            if len(filename_prefix) > 50:
                filename_prefix = "BASELINE_CUSTOM_MULTIPLE_OUTLETS"
            
            grab_paths_to_check.append(os.path.join(base_dir, "laporan", "grab_baseline", date_folder, f"{filename_prefix}.xlsx"))
            
            # Fallback glob pattern for any BASELINE_CUSTOM_{outlet_safe}_*.xlsx
            import glob
            glob_pattern = os.path.join(base_dir, "laporan", "grab_baseline", date_folder, f"BASELINE_CUSTOM_{outlet_safe}*.xlsx")
            for gp in glob.glob(glob_pattern):
                if gp not in grab_paths_to_check:
                    grab_paths_to_check.append(gp)

            grab_path = None
            for p_check in grab_paths_to_check:
                if os.path.exists(p_check):
                    grab_path = p_check
                    break
                    
            if grab_path:
                print(f"  [INFO] Menemukan file Grab baseline: {grab_path}")
                frames.append(pd.read_excel(grab_path))
            else:
                print(f"  [INFO] File Grab baseline tidak ditemukan untuk: {outlet_safe}")
            
            # Find Shopee Baseline output
            shopee_paths_to_check = []
            m_str = "|".join(shopee_merchant) if shopee_merchant else None
            shopee_safe = str(m_str or "").strip().replace(" ", "_").replace("/", "_").replace("\\", "_").replace("|", "_")
            if len(shopee_safe) > 50:
                shopee_safe = "MULTIPLE_MERCHANTS"
            shopee_paths_to_check.append(os.path.join(base_dir, "laporan", "shopee_baseline", date_folder, f"BASELINE_CUSTOM_{shopee_safe}.xlsx"))
            shopee_paths_to_check.append(os.path.join(base_dir, "laporan", "shopee_baseline", date_folder, f"BASELINE_CUSTOM_{shopee_safe}_.xlsx"))
            
            # Fallback glob pattern for any BASELINE_CUSTOM_{shopee_safe}*.xlsx
            glob_pattern_sf = os.path.join(base_dir, "laporan", "shopee_baseline", date_folder, f"BASELINE_CUSTOM_{shopee_safe}*.xlsx")
            for gp in glob.glob(glob_pattern_sf):
                if gp not in shopee_paths_to_check:
                    shopee_paths_to_check.append(gp)
                    
            # Check for BASELINE_MASTER_SHOPEE.xlsx
            shopee_paths_to_check.append(os.path.join(base_dir, "laporan", "shopee_baseline", date_folder, "BASELINE_MASTER_SHOPEE.xlsx"))
                    
            shopee_path = None
            for p_check in shopee_paths_to_check:
                if os.path.exists(p_check):
                    shopee_path = p_check
                    break
                    
            if shopee_path:
                print(f"  [INFO] Menemukan file Shopee baseline: {shopee_path}")
                sf_df = pd.read_excel(shopee_path)
                if "BASELINE_MASTER_SHOPEE" in shopee_path and shopee_merchant:
                    m_lower = [str(m).strip().lower() for m in shopee_merchant]
                    sf_df = sf_df[sf_df['Merchant'].astype(str).str.strip().str.rstrip('_').str.strip().str.lower().isin(m_lower)]
                if not sf_df.empty:
                    frames.append(sf_df)
            else:
                print(f"  [INFO] File Shopee baseline tidak ditemukan untuk: {shopee_safe}")

            # Find GoFood Baseline output
            gofood_paths_to_check = []
            
            o_str_go = "|".join(outlet) if outlet else None
            outlet_safe_go = str(o_str_go or "").strip().replace(" ", "_").replace("/", "_").replace("\\", "_").replace("|", "_")
            if outlet_safe_go:
                gofood_paths_to_check.append(os.path.join(base_dir, "laporan", "gofood_baseline", date_folder, f"BASELINE_CUSTOM_GOFOOD_{outlet_safe_go}_{start_date}_to_{end_date}.xlsx"))
                import glob
                glob_pattern_gf = os.path.join(base_dir, "laporan", "gofood_baseline", date_folder, f"BASELINE_CUSTOM_GOFOOD_{outlet_safe_go}*.xlsx")
                for gp in glob.glob(glob_pattern_gf):
                    if gp not in gofood_paths_to_check:
                        gofood_paths_to_check.append(gp)

            gofood_paths_to_check.append(os.path.join(base_dir, "laporan", "gofood_baseline", date_folder, f"BASELINE_GOFOOD_{start_date}_to_{end_date}.xlsx"))
            
            gofood_path = None
            for p_check in gofood_paths_to_check:
                if os.path.exists(p_check):
                    gofood_path = p_check
                    break
                    
            if gofood_path:
                print(f"  [INFO] Menemukan file GoFood baseline: {gofood_path}")
                gf_df = pd.read_excel(gofood_path)
                
                # Only filter if it's the general MASTER file.
                # If it's the custom one, it's already pre-filtered.
                if outlet and "BASELINE_CUSTOM" not in os.path.basename(gofood_path):
                    o_lower = [str(o).strip().lower() for o in outlet]
                    gf_df = gf_df[gf_df['Merchant'].astype(str).str.strip().str.lower().isin(o_lower)]
                if not gf_df.empty:
                    frames.append(gf_df)
            else:
                print(f"  [INFO] File GoFood baseline tidak ditemukan untuk: {start_date} s/d {end_date}")
                
            if frames:
                combined_df = pd.concat(frames, ignore_index=True)
                final_baseline_dir = os.path.join(base_dir, "laporan", "baseline", date_folder)
                os.makedirs(final_baseline_dir, exist_ok=True)
                final_path = os.path.join(final_baseline_dir, f"BASELINE_GABUNGAN_{outlet_safe}.xlsx")
                
                with pd.ExcelWriter(final_path, engine="openpyxl") as writer:
                    combined_df.to_excel(writer, index=False, sheet_name="Baseline Summary")
                    
                print(f"  {GREEN}✓ File gabungan berhasil dibuat: {final_path}{RESET}")


                # ── Generate PDF via Webhook ──
                print(f"\n{YELLOW}{BOLD}▶ PEMBUATAN PDF BASELINE{RESET}")
                try:
                    import requests
                    import io
                    
                    # Hardcode URL Web App Anda di sini setelah di-deploy
                    webhook_url = "https://script.google.com/macros/s/AKfycbwOZkmUfTL1jsr1qPcJBNkdMYgGdJO2YaY4sB676G4svsZx06bJ0ZBo2GF7GKkVm1Il/exec"
                    if not webhook_url or "GANTI_DENGAN_URL_ANDA" in webhook_url:
                        print(f"  {YELLOW}⚠️ URL Webhook belum di-hardcode di cli.py.{RESET}")
                        print(f"  {DIM}Silakan deploy apps_script_pdf.js dan masukkan URL-nya ke variabel webhook_url di cli.py{RESET}")
                    else:
                        # 1. Fetch Owner dari Baseline sheet (gid=880434015)
                        CSV_URL = "https://docs.google.com/spreadsheets/d/14eCb8DAEXhmbYj9MFj2KzC7AhkulbCbSNPltN2m-go0/export?format=csv&gid=880434015"
                        owner_name = "-"
                        outlet_val = outlet[0] if isinstance(outlet, (list, tuple)) and len(outlet) > 0 else outlet
                        try:
                            resp = requests.get(CSV_URL, timeout=10)
                            if resp.status_code == 200:
                                df_cred = pd.read_csv(io.StringIO(resp.text))
                                outlet_lower = str(outlet_val).strip().lower()
                                # 1. Exact match (case-insensitive)
                                matched = df_cred[
                                    df_cred["Nama Outlet"].astype(str).str.strip().str.lower() == outlet_lower
                                ]
                                # 2. Fallback: partial/contains match jika exact tidak ditemukan
                                if matched.empty:
                                    matched = df_cred[
                                        df_cred["Nama Outlet"].astype(str).str.strip().str.lower().str.contains(
                                            outlet_lower, na=False, regex=False
                                        )
                                    ]
                                if not matched.empty:
                                    owner_row = matched.iloc[0]
                                    owner_name = str(owner_row.get("Owner", "-"))
                                else:
                                    print(f"  {DIM}Nama Owner tidak ditemukan untuk outlet: '{outlet_val}'{RESET}")
                        except Exception as e:
                            print(f"  {DIM}Gagal mengambil nama Owner: {e}{RESET}")

                        # 2. Extract metrics from combined DataFrame
                        # LOGIKA BENAR: akumulasi semua portal per bulan terlebih dahulu,
                        # baru hasil akumulasi tersebut dirata-rata (bukan jumlah rata-rata per portal)
                        omzet_go, order_go = 0.0, 0.0
                        omzet_gr, order_gr = 0.0, 0.0
                        omzet_sf, order_sf = 0.0, 0.0

                        order_month_cols = sorted([c for c in combined_df.columns if c.startswith("Order Bulan ke-")])
                        omzet_month_cols = sorted([c for c in combined_df.columns if c.startswith("Omzet Bulan ke-")])
                        num_months_bl = len(order_month_cols) if order_month_cols else 1

                        def _platform_monthly_avg(df, cols, grab_m, shopee_m, go_m):
                            """Sum all portals per month across platform, then average across months."""
                            if not cols or num_months_bl == 0:
                                return 0.0, 0.0, 0.0
                            def _avg(mask):
                                grp = df.loc[mask, cols].copy()
                                grp = grp.apply(pd.to_numeric, errors="coerce").fillna(0)
                                if grp.empty:
                                    return 0.0
                                # Sum all portals per month (axis=0), then average across months
                                return float(grp.sum(axis=0).sum()) / num_months_bl
                            return _avg(grab_m), _avg(shopee_m), _avg(go_m)

                        app_lower = combined_df["Aplikasi"].astype(str).str.lower().str.strip()
                        grab_mask   = app_lower.str.contains("grab",   na=False)
                        shopee_mask = app_lower.str.contains("shopee", na=False)
                        go_mask     = (~grab_mask) & (~shopee_mask) & app_lower.str.contains("go", na=False)

                        omzet_gr, omzet_sf, omzet_go = _platform_monthly_avg(combined_df, omzet_month_cols, grab_mask, shopee_mask, go_mask)
                        order_gr, order_sf, order_go = _platform_monthly_avg(combined_df, order_month_cols, grab_mask, shopee_mask, go_mask)
                                
                        def format_rp(val):
                            return f"Rp {int(val):,}".replace(",", ".")
                            
                        total_omzet = omzet_go + omzet_gr + omzet_sf
                        total_order = order_go + order_gr + order_sf
                            
                        indo_months = ["Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli", "Agustus", "September", "Oktober", "November", "Desember"]
                        now = datetime.now()
                        
                        payload = {
                            "action": "generate_baseline_pdf",
                            "tanggal": str(now.day),
                            "bulan": indo_months[now.month - 1],
                            "tahun": str(now.year),
                            "owner": owner_name,
                            "nama_outlet": str(outlet_val),
                            "omzet_go": format_rp(omzet_go),
                            "order_go": str(round(order_go)),
                            "omzet_gr": format_rp(omzet_gr),
                            "order_gr": str(round(order_gr)),
                            "omzet_sf": format_rp(omzet_sf),
                            "order_sf": str(round(order_sf)),
                            "total_omzet": format_rp(total_omzet),
                            "total_order": str(round(total_order))
                        }
                        
                        print(f"  {CYAN}[INFO] Mengirim data agregasi ke Google Apps Script...{RESET}")
                        res = requests.post(webhook_url, json=payload, timeout=30)
                        if res.status_code == 200:
                            data = res.json()
                            if data.get("success"):
                                pdf_url = data.get('pdf_url', '')
                                print(f"  {GREEN}✓ PDF berhasil dibuat!{RESET}")
                                print(f"  {GREEN}  URL: {pdf_url}{RESET}")
                                
                                # Print DISCORD_NOTIF_JSON for Node.js bridge/bot
                                import json
                                notif_data = {
                                    "outlet": str(outlet_val),
                                    "start_date": start_date,
                                    "end_date": end_date,
                                    "aplikator": os.environ.get("OFD_APLIKATOR", "Grab + Shopee"),
                                    "pdf_url": pdf_url,
                                    "pdf_name": data.get('pdf_name', 'Baseline Report'),
                                    "omzet_gr": format_rp(omzet_gr),
                                    "omzet_sf": format_rp(omzet_sf),
                                    "order_gr": str(round(order_gr)),
                                    "order_sf": str(round(order_sf)),
                                    "omzet_go": format_rp(omzet_go),
                                    "order_go": str(round(order_go))
                                }
                                print(f"DISCORD_NOTIF_JSON: {json.dumps(notif_data)}")

                                # ── Kirim notifikasi PDF ke Discord channel ──
                                _notify_discord_pdf(
                                    outlet=str(outlet_val),
                                    start_date=start_date,
                                    end_date=end_date,
                                    aplikator=os.environ.get("OFD_APLIKATOR", "Grab + Shopee"),
                                    pdf_url=pdf_url,
                                    pdf_name=data.get('pdf_name', 'Baseline Report'),
                                    omzet_gr=format_rp(omzet_gr),
                                    omzet_sf=format_rp(omzet_sf),
                                    order_gr=str(round(order_gr)),
                                    order_sf=str(round(order_sf)),
                                    omzet_go=format_rp(omzet_go),
                                    order_go=str(round(order_go)),
                                )
                            else:
                                print(f"  {RED}✗ Gagal membuat PDF: {data.get('error')}{RESET}")
                        else:
                            print(f"  {RED}✗ Error HTTP {res.status_code} saat menghubungi Webhook{RESET}")
                except Exception as e:
                    print(f"  {RED}✗ Terjadi kesalahan saat memproses Webhook PDF: {e}{RESET}")
            else:
                print(f"  {RED}✗ Tidak ditemukan file baseline untuk digabung.{RESET}")
        except Exception as e:
            print(f"  {RED}✗ Gagal menggabungkan laporan: {e}{RESET}")

    print(f"\n{CYAN}{BOLD}{'═'*58}{RESET}")
    print(f"{CYAN}{BOLD}  SUMMARY{RESET}")
    print(f"{CYAN}{BOLD}{'═'*58}{RESET}")
    print(f"  Date Range : {start_date} → {end_date}")
    print(f"  Duration   : {minutes}m {seconds}s")
    print()
    for name, success in results.items():
        status = f"{GREEN}✓ SUCCESS{RESET}" if success else f"{RED}✗ FAILED{RESET}"
        if task_choice == "1":
            out_folder = name.lower() + "_baseline"
        elif task_choice == "3":
            out_folder = name.lower() + "_vb"
        else:
            out_folder = name.lower()
            
        out_path = os.path.join(base_dir, "laporan", out_folder, date_folder)
        print(f"  {name:10s} : {status}")
        print(f"  {'':10s}   {DIM}→ {out_path}{RESET}")
    print(f"\n{CYAN}{'═'*58}{RESET}\n")


if __name__ == "__main__":
    main()
