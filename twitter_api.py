import requests
import time
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)


def get_new_tweets(username, api_key, last_tweet_id=None, delay=2, retries=3, timeout=30, count=100):
    url = "https://api.tweetscout.io/v2/user-tweets"
    new_tweets = []
    new_last_tweet_id = last_tweet_id or "0"
    cursor_val = None
    total_fetched = 0

    while total_fetched < count:
        payload = {"link": f"https://twitter.com/{username}"}
        if cursor_val:
            payload["cursor"] = cursor_val

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "ApiKey": api_key
        }

        for attempt in range(retries):
            try:
                response = requests.post(url, json=payload, headers=headers, timeout=timeout)

                if response.status_code == 200:
                    data = response.json()
                    tweets = data.get("tweets", [])
                    if not tweets:
                        # Если твитов нет, сразу возвращаем
                        return new_tweets, new_last_tweet_id

                    # Валидные твиты с числовым id
                    valid_tweets = [t for t in tweets if t.get("id_str") and t["id_str"].isdigit()]
                    if not valid_tweets:
                        return new_tweets, new_last_tweet_id

                    # Сортируем по убыванию ID
                    valid_tweets.sort(key=lambda x: int(x["id_str"]), reverse=True)

                    # Берём только новые твиты
                    new_page_tweets = []
                    for tweet in valid_tweets:
                        tid = tweet["id_str"]
                        if int(tid) > int(last_tweet_id or "0"):
                            new_page_tweets.append((tid, tweet["full_text"]))
                            new_last_tweet_id = max(new_last_tweet_id, tid)
                            total_fetched += 1
                            if total_fetched >= count:
                                break

                    if not new_page_tweets:
                        # Если на этой странице нет новых твитов, прекращаем поиск
                        return new_tweets, new_last_tweet_id

                    new_tweets.extend(new_page_tweets)

                    # Переходим к следующей странице только если есть курсор
                    cursor_val = data.get("next_cursor")
                    if not cursor_val:
                        break
                    else:
                        break  # успешный запрос, идём на следующую итерацию while

                elif response.status_code in (429, 403):
                    logger.warning(f"Rate limit / доступ запрещён @{username}, ждём 7 секунд...")
                    time.sleep(7)
                    continue
                elif response.status_code in (400, 404):
                    logger.warning(f"Ошибка {response.status_code} для @{username}")
                    return new_tweets, new_last_tweet_id
                else:
                    logger.warning(f"Неизвестная ошибка {response.status_code} для @{username}")
                    return new_tweets, new_last_tweet_id

            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError):
                if attempt < retries - 1:
                    time.sleep(delay)
                else:
                    logger.warning(f"Ошибка запроса для @{username} после {retries} попыток")
                    return new_tweets, new_last_tweet_id
            except requests.exceptions.RequestException as e:
                if attempt < retries - 1:
                    time.sleep(delay)
                else:
                    logger.warning(f"Ошибка запроса для @{username}: {str(e)}")
                    return new_tweets, new_last_tweet_id

        else:
            # если после всех попыток не удалось
            return new_tweets, new_last_tweet_id

        # Если на странице новых твитов нет, прерываем основной while
        if total_fetched == 0 or total_fetched >= count:
            break

    return new_tweets, new_last_tweet_id
