import csv
import asyncio
import os
from datetime import datetime, timedelta
from pathlib import Path
from playwright.async_api import async_playwright
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from grab_api_scraper import validate_credentials

async def load_credentials():
    """Load username and password from environment variables"""
    username = os.getenv('GRAB_USERNAME')
    password = os.getenv('GRAB_PASSWORD')
    
    if not username or not password:
        print("Error: GRAB_USERNAME or GRAB_PASSWORD not found in .env file")
        return None, None
        
    return username, password


async def get_90_days_date_range():
    """Get start and end dates for last 90 days"""
    today = datetime.now()
    
    # Calculate 90 days ago
    start_date = today - timedelta(days=90)
    end_date = today
    
    start_date_str = start_date.strftime("%d/%m/%y")
    end_date_str = end_date.strftime("%d/%m/%y")
    
    print(f"DEBUG: 90 days range - from {start_date_str} to {end_date_str}")
    
    return {
        'start_date': start_date_str,
        'end_date': end_date_str,
        'label': f"90_days_{start_date.strftime('%d%m%y')}_to_{end_date.strftime('%d%m%y')}"
    }


async def get_last_3_months_dates():
    """Get start and end dates for last 3 months combined into one range"""
    today = datetime.now()
    
    # Get current month's first day
    current_month_first = today.replace(day=1)
    
    # Go back 3 months to get the first day of 3 months ago
    if current_month_first.month - 3 <= 0:
        # Handle year transition
        month = current_month_first.month - 3 + 12
        year = current_month_first.year - 1
    else:
        month = current_month_first.month - 3
        year = current_month_first.year
    
    first_day = datetime(year, month, 1)
    
    # Get last day of previous month (yesterday)
    last_day = current_month_first - timedelta(days=1)
    
    start_date = first_day.strftime("%d/%m/%y")
    end_date = last_day.strftime("%d/%m/%y")
    month_range = f"{first_day.strftime('%B %Y')} to {last_day.strftime('%B %Y')}"
    
    print(f"DEBUG: 3 months range - from {start_date} to {end_date}")
    
    return {
        'start_date': start_date,
        'end_date': end_date,
        'label': month_range
    }


async def download_3months_data(page, start_date, end_date, label):
    """Download data for 3 months combined"""
    try:
        print(f"\n{'='*50}")
        print(f"Downloading 3 months data")
        print(f"Date range: {start_date} to {end_date}")
        print(f"Label: {label}")
        print(f"{'='*50}")
        
        # Navigate to finances page with specific dates
        url = f"https://merchant.grab.com/finances?page=tx&startDate={start_date}&endDate={end_date}"
        print(f"Navigating to: {url}")
        await page.goto(url, wait_until="load")
        await page.wait_for_timeout(3000)
        
        print("Waiting for data to load...")
        await page.wait_for_load_state("networkidle", timeout=15000)
        await page.wait_for_timeout(2000)
        
        # Close any pop-ups that appear on finances page
        print("Checking for pop-ups on finance page...")
        await close_popup(page)
        await page.wait_for_timeout(1000)
        
        # Look for download button
        print("Looking for download button...")
        
        # Try different selectors for download button
        download_button = None
        
        # Try common download button selectors
        selectors = [
            'button:has-text("Download")',
            'button:has-text("download")',
            'button[aria-label*="download" i]',
            'button[title*="download" i]',
            'a[aria-label*="download" i]',
            'a[title*="download" i]',
        ]
        
        for selector in selectors:
            try:
                button = await page.locator(selector).first.element_handle()
                if button:
                    download_button = button
                    print(f"Found download button with selector: {selector}")
                    break
            except:
                continue
        #trademarkradi
        # If still not found, look for any button with download-like appearance
        if not download_button:
            all_buttons = await page.locator('button').all()
            for btn in all_buttons:
                try:
                    text = await btn.text_content()
                    aria_label = await btn.get_attribute('aria-label')
                    title = await btn.get_attribute('title')
                    
                    if text and ('download' in text.lower() or 'unduh' in text.lower()):
                        print(f"Found download button with text: {text}")
                        download_button = btn
                        break
                    elif aria_label and ('download' in aria_label.lower()):
                        print(f"Found download button with aria-label: {aria_label}")
                        download_button = btn
                        break
                    elif title and ('download' in title.lower()):
                        print(f"Found download button with title: {title}")
                        download_button = btn
                        break
                except:
                    continue
        
        if download_button:
            print("Clicking download button...")
            await download_button.click()
            await page.wait_for_timeout(3000)  # Increased wait time
            
            # Wait for modal dialog to appear
            print("Waiting for download options modal...")
            try:
                await page.wait_for_selector('[role="dialog"]', timeout=5000)
                print("Modal appeared")
                await page.wait_for_timeout(1000)
            except:
                print("Modal selector not found, checking for alternative selectors...")
                try:
                    await page.wait_for_selector('.modal, [class*="modal"], [class*="dialog"]', timeout=3000)
                    print("Modal found with alternative selector")
                    await page.wait_for_timeout(1000)
                except:
                    print("Modal not found, trying to locate download options another way...")
            
            await page.wait_for_timeout(500)
            
            # Find and click "All transaction details" radio button
            print("Looking for 'All transaction details' option...")
            
            # Wait a moment for the modal to fully load
            await page.wait_for_timeout(500)
            
            # Try to find the radio button for all transaction details
            all_radios = await page.locator('input[type="radio"]').all()
            radio_selected = False
            
            print(f"Found {len(all_radios)} radio buttons")
            
            for idx, radio in enumerate(all_radios):
                try:
                    # Get the radio button's parent container and text
                    # Try multiple approaches to get associated text
                    parent = await radio.locator('..').element_handle()
                    if parent:
                        parent_text = await parent.text_content()
                    else:
                        parent_text = ""
                    
                    parent_text_lower = parent_text.lower()
                    print(f"Radio {idx}: {parent_text_lower[:100]}...")
                    
                    if 'all transaction' in parent_text_lower and 'details' in parent_text_lower:
                        print(f"✓ Found 'All transaction details' option!")
                        is_checked = await radio.is_checked()
                        if not is_checked:
                            print("Clicking 'All transaction details' radio button...")
                            await radio.click()
                            await page.wait_for_timeout(500)
                            print("✓ 'All transaction details' selected")
                        else:
                            print("✓ 'All transaction details' already selected")
                        radio_selected = True
                        break
                except Exception as e:
                    print(f"Error checking radio {idx}: {str(e)}")
                    continue
            
            if not radio_selected:
                print("⚠ 'All transaction details' option not found by text, trying second radio button...")
                try:
                    # If we can't find by text, try clicking the second radio (usually it's the all details option)
                    if len(all_radios) > 1:
                        second_radio = all_radios[1]
                        is_checked = await second_radio.is_checked()
                        if not is_checked:
                            print("Clicking second radio button (should be 'All transaction details')...")
                            await second_radio.click()
                            await page.wait_for_timeout(500)
                            print("✓ Second radio button selected")
                        radio_selected = True
                except Exception as e:
                    print(f"Error clicking second radio: {str(e)}")
            
            await page.wait_for_timeout(1000)
            
            # Find and click the Download button inside the modal
            print("Looking for Download button in modal...")
            modal_download_button = None
            
            modal_buttons = await page.locator('[role="dialog"] button').all()
            for btn in modal_buttons:
                try:
                    text = await btn.text_content()
                    if text and 'download' in text.lower():
                        print(f"Found modal download button: {text}")
                        modal_download_button = btn
                        break
                except:
                    continue
            
            if modal_download_button:
                print("Clicking Download button in modal...")
                # Start waiting for download before clicking
                async with page.expect_download() as download_info:
                    await modal_download_button.click()
                
                download = await download_info.value
                
                # Create downloads folder if it doesn't exist
                downloads_folder = "downloads"
                os.makedirs(downloads_folder, exist_ok=True)
                
                # Save with meaningful filename
                safe_start_date = start_date.replace('/', '-')
                safe_end_date = end_date.replace('/', '-')
                filename = f"{downloads_folder}/grab_transactions_3months_({safe_start_date}_to_{safe_end_date}).csv"
                await download.save_as(filename)
                print(f"✓ Downloaded successfully: {filename}")
                await page.wait_for_timeout(2000)  # Wait after download
                
            else:
                print("⚠ Download button in modal not found")
                # Take screenshot for debugging
                await page.screenshot(path="screenshot_3months.png")
                print("Screenshot saved: screenshot_3months.png")
        
        else:
            print("⚠ Download button not found on page")
            # Take screenshot for debugging
            await page.screenshot(path="screenshot_3months.png")
            print("Screenshot saved: screenshot_3months.png")
        
        await page.wait_for_timeout(2000)
        
    except Exception as e:
        print(f"✗ Error downloading 3 months data: {str(e)}")
        import traceback
        traceback.print_exc()
        await page.screenshot(path="error_3months_download.png")


async def close_popup(page):
    """Detect and close pop-ups or modals on the dashboard"""
    try:
        await page.wait_for_timeout(1500)  # Wait for modal to render
        
        # Look for modal/dialog elements - be more specific with Grab UI
        popup_selectors = [
            '[role="dialog"]',
            '.modal',
            '.popup',
            '[class*="Modal"]',
            '[class*="modal"]',
            '[class*="popup"]',
            '[class*="dialog"]',
            'div[style*="position"]',  # Generic positioned divs that might be modals
        ]
        
        popup_found = False
        
        # Check if any popup/modal exists
        for popup_sel in popup_selectors:
            try:
                popups = await page.locator(popup_sel).all()
                if popups and len(popups) > 0:
                    for idx, popup in enumerate(popups):
                        try:
                            # Check if it's visible
                            is_visible = await popup.is_visible()
                            if is_visible:
                                print(f"Found visible popup {idx} with selector: {popup_sel}")
                                popup_found = True
                                
                                # Strategy 1: Look for button with text "Close" using page-level selector
                                print("Strategy 1: Looking for 'Close' button on page...")
                                try:
                                    close_btn = await page.locator('button:text("Close")').first.element_handle()
                                    if close_btn:
                                        print("Found 'Close' button with text selector, clicking...")
                                        await page.locator('button:text("Close")').first.click()
                                        await page.wait_for_timeout(1000)
                                        print("✓ Pop-up closed with Close button")
                                        return True
                                except:
                                    pass
                                
                                # Strategy 2: Scan all buttons and match text
                                print("Strategy 2: Scanning all buttons for text match...")
                                all_buttons = await page.locator('button').all()
                                for btn in all_buttons:
                                    try:
                                        text = (await btn.text_content() or "").strip()
                                        
                                        # Look for Close button
                                        if text.lower() == "close":
                                            print(f"Found Close button with exact text match, clicking...")
                                            await btn.click()
                                            await page.wait_for_timeout(1000)
                                            print("✓ Pop-up closed successfully")
                                            return True
                                        
                                        # Look for X button
                                        if text in ['×', 'X', '✕', '✘']:
                                            print(f"Found X/close icon button: '{text}', clicking...")
                                            await btn.click()
                                            await page.wait_for_timeout(1000)
                                            print("✓ Pop-up closed successfully")
                                            return True
                                    except:
                                        continue
                                
                                # Strategy 3: Try specific dialog button selector
                                print("Strategy 3: Looking for dialog buttons with has-text selector...")
                                close_buttons = await page.locator('[role="dialog"] button:has-text("Close")').all()
                                if close_buttons:
                                    print(f"Found {len(close_buttons)} Close button(s) in dialog")
                                    await close_buttons[0].click()
                                    await page.wait_for_timeout(1000)
                                    print("✓ Pop-up closed successfully")
                                    return True
                                
                                # Strategy 4: Try clicking outside modal (backdrop/overlay)
                                print("Strategy 4: Trying to click outside modal to close...")
                                try:
                                    backdrop = await page.locator('[role="presentation"]').first.element_handle()
                                    if backdrop:
                                        await page.locator('[role="presentation"]').first.click()
                                        await page.wait_for_timeout(1000)
                                        print("✓ Pop-up closed by clicking backdrop")
                                        return True
                                except:
                                    pass
                                
                                # Strategy 5: Escape key as final attempt
                                print("Strategy 5: Trying Escape key as final attempt...")
                                await page.press('Escape')
                                await page.wait_for_timeout(1000)
                                print("✓ Escape key pressed")
                                return True
                        except Exception as e:
                            print(f"Error processing popup {idx}: {str(e)}")
                            continue
            except:
                continue
        
        if not popup_found:
            print("No visible pop-up detected")
        
    except Exception as e:
        print(f"Error while checking for pop-ups: {str(e)}")
    
    return False


async def grab_dashboard_login(user=None, pwd=None):
    """Automate Grab merchant dashboard login using Playwright"""
    if user and pwd:
        username, password = user, pwd
    else:
        username, password = await load_credentials()
    
    if not username or not password:
        print(f"Error: Credentials not provided and not found in .env")
        return
        
    is_valid, err_msg = validate_credentials(username, password)
    if not is_valid:
        print(f"Error: Invalid credentials for {username}: {err_msg}")
        return

    
    async with async_playwright() as p:
        # Launch browser
        # Load headless setting from config.json walk-up
        headless_env = True
        try:
            import json
            for parent in Path(__file__).resolve().parents:
                config_file = parent / "config.json"
                if config_file.exists():
                    with open(config_file, "r") as f:
                        headless_env = json.load(f).get("headless_grab", True)
                    break
        except Exception:
            pass
        browser = await p.chromium.launch(headless=headless_env)
        page = await browser.new_page()
        
        try:
            # Navigate to dashboard
            print("Navigating to Grab merchant dashboard...")
            await page.goto("https://merchant.grab.com/dashboard", wait_until="load")
            print("Page loaded, waiting for content to settle...")
            await page.wait_for_timeout(3000)
            
            # Wait for username field to be visible
            print("Waiting for username field...")
            username_input = await page.locator('input[type="email"], input[name="email"], input[type="text"]').first.element_handle()
            if not username_input:
                username_input = await page.locator('input').first.element_handle()
            
            await page.wait_for_selector('input[type="email"], input[name="email"], input[type="text"]', timeout=15000)
            
            # Click on username field
            print("Clicking on username field...")
            await page.click('input[type="email"], input[name="email"], input[type="text"]')
            await page.wait_for_timeout(500)
            
            # Clear and fill username
            print(f"Entering username: {username}")
            await page.fill('input[type="email"], input[name="email"], input[type="text"]', username)
            print("Username entered successfully")
            await page.wait_for_timeout(1000)
            
            # Click continue button for username
            print("Looking for continue button...")
            continue_buttons = await page.locator('button').all()
            continue_clicked = False
            
            for btn in continue_buttons:
                text = await btn.text_content()
                if text and ('continue' in text.lower() or 'lanjut' in text.lower()):
                    print(f"Clicking continue button with text: {text}")
                    await btn.click()
                    continue_clicked = True
                    break
            
            if not continue_clicked:
                print("Continue button not found, trying submit button...")
                await page.press('input[type="email"], input[name="email"], input[type="text"]', 'Enter')
            
            print("Waiting for password field...")
            await page.wait_for_timeout(2000)
            await page.wait_for_selector('input[type="password"]', timeout=15000)
            
            # Click on password field
            print("Clicking on password field...")
            await page.click('input[type="password"]')
            await page.wait_for_timeout(500)
            
            # Fill password
            print("Entering password...")
            await page.fill('input[type="password"]', password)
            print("Password entered successfully")
            await page.wait_for_timeout(1000)
            
            # Click continue button for password
            print("Looking for continue button to submit password...")
            continue_buttons = await page.locator('button').all()
            continue_clicked = False
            
            for btn in continue_buttons:
                text = await btn.text_content()
                if text and ('continue' in text.lower() or 'lanjut' in text.lower()):
                    print(f"Clicking continue button with text: {text}")
                    await btn.click()
                    continue_clicked = True
                    break
            
            if not continue_clicked:
                print("Continue button not found, trying submit button...")
                await page.press('input[type="password"]', 'Enter')
            
            # Wait for dashboard to load
            print("Waiting for dashboard to load...")
            await page.wait_for_load_state("networkidle", timeout=15000)
            print("Dashboard accessed successfully!")
            
            # Wait a bit longer for all elements to settle
            await page.wait_for_timeout(3000)
            
            # Verify we're on dashboard
            current_url = page.url
            print(f"Current URL: {current_url}")
            
            # Close any pop-ups that appear on dashboard
            print("Checking for pop-ups to close...")
            await close_popup(page)
            await page.wait_for_timeout(2000)
            
            # Get last 3 months dates as a single range
            print("\nCalculating last 3 months...")
            date_range = await get_last_3_months_dates()
            
            # Download all 3 months data in one request
            await download_3months_data(
                page,
                date_range['start_date'],
                date_range['end_date'],
                date_range['label']
            )
            
            print("\n" + "="*50)
            print("All downloads completed!")
            print("="*50)
            
            # Keep browser open for inspection
            await page.wait_for_timeout(3000)
            
        except Exception as e:
            print(f"Error during automation: {str(e)}")
            # Take screenshot for debugging
            await page.screenshot(path="error_screenshot.png")
            print("Error screenshot saved as 'error_screenshot.png'")
            import traceback
            traceback.print_exc()
        
        finally:
            await browser.close()


if __name__ == "__main__":
    asyncio.run(grab_dashboard_login())
