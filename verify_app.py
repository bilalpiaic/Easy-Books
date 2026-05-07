from playwright.sync_api import sync_playwright
import time

def verify_app():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={'width': 1280, 'height': 720})
        page = context.new_page()
        
        print("Navigating to http://localhost:3000/login...")
        try:
            page.goto('http://localhost:3000/login', timeout=60000)
            page.wait_for_load_state('networkidle')
            
            print(f"Page title: {page.title()}")
            page.screenshot(path='/home/droid/.gemini/tmp/easy-books/login_page.png')
            print("Login page screenshot saved to /home/droid/.gemini/tmp/easy-books/login_page.png")
            
            # Try to login
            print("Attempting login...")
            page.fill('input[type="email"]', 'admin@malik.com')
            page.fill('input[type="password"]', 'admin123')
            page.click('button[type="submit"]')
            
            page.wait_for_load_state('networkidle')
            time.sleep(2) # Wait for redirect
            
            print(f"Current URL after login attempt: {page.url}")
            if '/dashboard' in page.url:
                print("Successfully logged in!")
                page.screenshot(path='/home/droid/.gemini/tmp/easy-books/dashboard_page.png')
                print("Dashboard screenshot saved to /home/droid/.gemini/tmp/easy-books/dashboard_page.png")
            else:
                print("Login failed or redirect did not happen.")
                page.screenshot(path='/home/droid/.gemini/tmp/easy-books/failed_login.png')
                
        except Exception as e:
            print(f"An error occurred: {e}")
            page.screenshot(path='/home/droid/.gemini/tmp/easy-books/error_state.png')
        
        browser.close()

if __name__ == "__main__":
    verify_app()
