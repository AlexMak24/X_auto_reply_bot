import random
import logging
import time
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, StaleElementReferenceException
from auth import open_twitter_profile
from db.models import AccountModel, Database

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logging.getLogger('selenium.webdriver.remote.remote_connection').setLevel(logging.WARNING)
logging.getLogger('seleniumwire').setLevel(logging.WARNING)
logging.getLogger('urllib3').setLevel(logging.WARNING)
logging.getLogger('http.client').setLevel(logging.WARNING)


def random_sleep(min_sec, max_sec):
    duration = random.uniform(min_sec, max_sec)
    logging.info(f"Задержка на {duration:.2f} секунд.")
    time.sleep(duration)


def wait_clickable(driver, selector, timeout=20, retries=3):
    for i in range(retries):
        try:
            element = WebDriverWait(driver, timeout).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
            )
            return element
        except (TimeoutException, StaleElementReferenceException) as e:
            logging.warning(f"Попытка {i+1}/{retries} - элемент {selector} не кликабелен: {e}")
            time.sleep(1)
    raise TimeoutException(f"Элемент {selector} не стал кликабельным за {timeout} секунд")


def wait_presence(driver, selector, timeout=20, retries=3):
    for i in range(retries):
        try:
            element = WebDriverWait(driver, timeout).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, selector))
            )
            return element
        except TimeoutException as e:
            logging.warning(f"Попытка {i+1}/{retries} - элемент {selector} не найден: {e}")
            time.sleep(1)
    raise TimeoutException(f"Элемент {selector} не найден за {timeout} секунд")


def check_sign_in_page(driver):
    try:
        body_text = driver.find_element(By.TAG_NAME, 'body').text
        if "Sign in" in body_text or "Log in" in body_text or "Ошибка авторизации" in body_text:
            logging.error("Не получилось сделать действие, авторизуйтесь заново.")
            print("⚠️ Не получилось сделать действие, авторизуйтесь заново.")
            return True
        return False
    except Exception as e:
        logging.warning(f"Ошибка при проверке страницы на 'Sign in': {e}")
        return False


def open_tweet_with_proxy_like_bookmark_and_reply(
    profile_user_name: str,
    target_user_name: str,
    tweet_id: str,
    reply_text="Тестовый ответ",
    min_delay=2.0,
    max_delay=5.0,
    headed=False,
    db=None,
    close_after_action=True  # <--- новый параметр
):
    logging.info(f"Запуск для аккаунта '{profile_user_name}', твиттер пользователя '{target_user_name}', твит ID {tweet_id}")

    local_db = None
    if db is None:
        local_db = Database()
        db = local_db

    driver = None
    try:
        account_model = AccountModel(db)
        account = account_model.get_account_by_username(profile_user_name)

        if account and account.get("proxy"):
            proxy_url = account["proxy"]
            logging.info(f"Используется прокси: {proxy_url}")
            driver = open_twitter_profile(profile_user_name, use_proxy=True, proxy_url=proxy_url, headed=headed)
        else:
            logging.info("Прокси не найден, открываем без прокси")
            driver = open_twitter_profile(profile_user_name, headed=headed)

        tweet_url = f"https://x.com/{target_user_name}/status/{tweet_id}"
        logging.info(f"Переход на твит: {tweet_url}")
        driver.get(tweet_url)

        if check_sign_in_page(driver):
            return None

        tweet_element = wait_presence(driver, '[data-testid="tweetText"]')
        logging.info(f"Текст твита от @{target_user_name}: {tweet_element.text}")

        like_button = wait_clickable(driver, '[data-testid="like"]')
        like_button.click()
        logging.info("Лайк поставлен.")
        random_sleep(min_delay, max_delay)

        bookmark_button = wait_clickable(driver, '[data-testid="bookmark"]')
        bookmark_button.click()
        logging.info("Добавлено в закладки.")
        random_sleep(min_delay, max_delay)

        reply_field = wait_clickable(driver, '[data-testid="tweetTextarea_0"]')
        reply_field.click()
        reply_field.clear()
        reply_field.send_keys(reply_text)
        logging.info("Текст ответа введен.")
        random_sleep(min_delay, max_delay)

        reply_button = wait_clickable(driver, '[data-testid="tweetButtonInline"]')
        reply_button.click()
        logging.info("Ответ отправлен.")

    except Exception as e:
        logging.error(f"Ошибка при работе с твитом: {e}")

    finally:
        if local_db:
            local_db.close()

        if driver and close_after_action:
            driver.quit()
            logging.info("Браузер закрыт после выполнения действий.")

    return driver


if __name__ == "__main__":
    open_tweet_with_proxy_like_bookmark_and_reply(
        "gelosebastian_",
        "",
        "1968370591511232556",
        reply_text="Awesome bro!!! Really liked it, looks like that you are really good at math, teach me",
        min_delay=3.0,
        max_delay=6.0,
        headed=True,
        close_after_action=True  # <--- браузер закроется автоматически
    )
