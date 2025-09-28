import os
from seleniumwire import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

from db.models import Database, AccountModel, SettingsModel

# Подключаем БД и модели
db = Database()
account_model = AccountModel(db)
settings_model = SettingsModel(db)

def open_twitter_profile(user_name: str, mode: str = "login",
                         use_proxy: bool = False,
                         proxy_url: str = None,
                         extension_path: str = None,
                         headed: bool = True):

    account = account_model.get_account_by_username(user_name)

    if account:
        profile_dir = account["profile_dir"]
        proxy = account["proxy"]
    else:
        profile_dir = os.path.abspath(os.path.join("profiles", user_name))
        os.makedirs(profile_dir, exist_ok=True)
        proxy = proxy_url
        account_model.add_account(user_name, profile_dir, proxy)
        settings_model.add_settings_for_account(account_model.get_account_by_username(user_name)["id"])

    chrome_options = Options()
    chrome_options.add_argument(f"--user-data-dir={profile_dir}")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument("--disable-infobars")
    chrome_options.add_argument("--start-maximized")
    chrome_options.add_argument("--lang=en-US")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)

    if not headed:
        chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")

    seleniumwire_options = {}
    actual_proxy = None
    if use_proxy:
        actual_proxy = proxy_url if proxy_url else proxy
        if actual_proxy:
            seleniumwire_options = {
                'proxy': {
                    'http': f'http://{actual_proxy}',
                    'https': f'https://{actual_proxy}',
                    'no_proxy': 'localhost,127.0.0.1'
                }
            }

    if extension_path and extension_path.strip():
        chrome_options.add_argument(f"--load-extension={extension_path}")

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options, seleniumwire_options=seleniumwire_options)

    driver.get("https://x.com/home")

    try:
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, '[data-testid="AppTabBar_Home_Link"]'))
        )
        print(f"✅ {user_name} теперь авторизован.")
        account_model.update_account(user_name, profile_dir=profile_dir, proxy=actual_proxy)
    except Exception:
        print("⚠️ Вход не завершён или страница не загрузилась.")

    return driver
