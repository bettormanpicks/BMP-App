import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
import time

BASE_URL = "https://betsapi.com/table-tennis/le/29128/TT-Elite-Series"

options = uc.ChromeOptions()
options.add_argument("--start-maximized")

driver = uc.Chrome(options=options, version_main=145)

driver.get(BASE_URL)

print("Solve Cloudflare if needed...")
time.sleep(30)

# Check if table loads
rows = driver.find_elements(By.CSS_SELECTOR, "table tbody tr")

print(f"Rows found: {len(rows)}")

input("Press Enter to close...")
driver.quit()