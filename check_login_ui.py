from playwright.sync_api import sync_playwright
import time

def check_login_page():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        print("Navigating to http://localhost:3000/login...")
        try:
            page.goto("http://localhost:3000/login", timeout=30000)
            page.wait_for_load_state("networkidle")
            
            # Check if inputs exist
            email_input = page.locator('input[type="email"]')
            password_input = page.locator('input[type="password"]')
            
            print(f"Email input visible: {email_input.is_visible()}")
            print(f"Password input visible: {password_input.is_visible()}")
            
            # Check if we can type
            print("Attempting to type into email field...")
            email_input.fill("test@example.com")
            print(f"Email value after fill: {email_input.input_value()}")
            
            print("Attempting to type into password field...")
            password_input.fill("password123")
            print(f"Password value after fill: {password_input.input_value()}")
            
            # Check if there is any overlay
            # Sometimes a transparent div blocks interaction
            print("Checking for blocking overlays...")
            element_at_center = page.evaluate("document.elementFromPoint(window.innerWidth / 2, window.innerHeight / 2).outerHTML")
            print(f"Element at center of screen: {element_at_center[:200]}...")
            
            page.screenshot(path="/home/droid/.gemini/tmp/easy-books/login_interactivity_check.png")
            print("Screenshot saved.")
            
        except Exception as e:
            print(f"Error: {e}")
        finally:
            browser.close()

if __name__ == "__main__":
    check_login_page()
