import requests
from requests_oauthlib import OAuth1Session

# --- Заполни своими ключами ---
API_KEY = "YOUR_API_KEY"
API_SECRET = "YOUR_API_SECRET"
ACCESS_TOKEN = "YOUR_ACCESS_TOKEN"
ACCESS_TOKEN_SECRET = "YOUR_ACCESS_TOKEN_SECRET"
BEARER_TOKEN = "YOUR_BEARER_TOKEN"

# сколько новых твитов обрабатывать за один запуск
MAX_REPLIES_PER_RUN = 3

def get_user_tweets(user_id, since_id=None, max_results=10):
    """
    Получить твиты пользователя по ID
    """
    url = f"https://api.x.com/2/users/{user_id}/tweets"
    headers = {"Authorization": f"Bearer {BEARER_TOKEN}"}
    params = {"max_results": max_results}
    if since_id:
        params["since_id"] = since_id
    resp = requests.get(url, headers=headers, params=params)
    resp.raise_for_status()
    return resp.json().get("data", [])

def make_oauth_session():
    """
    Создать сессию для POST-запросов (лайки/реплаи)
    """
    return OAuth1Session(
        API_KEY,
        API_SECRET,
        ACCESS_TOKEN,
        ACCESS_TOKEN_SECRET
    )

def like_tweet(auth_session, user_id, tweet_id):
    url = f"https://api.x.com/2/users/{user_id}/likes"
    payload = {"tweet_id": tweet_id}
    resp = auth_session.post(url, json=payload)
    resp.raise_for_status()
    return resp.json()

def reply_to_tweet(auth_session, text, in_reply_to_tweet_id):
    url = "https://api.x.com/2/tweets"
    payload = {
        "text": text,
        "reply": {"in_reply_to_tweet_id": in_reply_to_tweet_id}
    }
    resp = auth_session.post(url, json=payload)
    resp.raise_for_status()
    return resp.json()

def monitor_user(user_id, last_known_id=None, db_interface=None):
    tweets = get_user_tweets(user_id, since_id=last_known_id, max_results=20)
    if not tweets:
        print("Нет новых твитов")
        return

    auth = make_oauth_session()
    replies_done = 0

    for tweet in tweets:
        tw_id = tweet["id"]
        tw_text = tweet["text"]

        if last_known_id and int(tw_id) > int(last_known_id):
            print(f"🆕 Новый твит {tw_id}: {tw_text}")

            # лайкаем
            like_tweet(auth, user_id, tw_id)
            print("❤️ Лайк поставлен")

            # отвечаем только ограниченное число раз
            if replies_done < MAX_REPLIES_PER_RUN:
                reply_text = "🔥 Крутой пост!"  # тут можно вставить текст от модели
                reply_to_tweet(auth, reply_text, tw_id)
                print("💬 Ответ отправлен")
                replies_done += 1
        else:
            print("⚠️ Первый запуск или твиты старые — сохраняем без ответа")

    # обновляем last_known_id
    max_id = max(int(t["id"]) for t in tweets)
    if db_interface:
        db_interface.set_last_tweet_id(user_id, str(max_id))

# --- пример использования ---
class DummyDB:
    def __init__(self):
        self.store = {}
    def get_last_tweet_id(self, user_id):
        return self.store.get(user_id)
    def set_last_tweet_id(self, user_id, tweet_id):
        self.store[user_id] = tweet_id

if __name__ == "__main__":
    user_id = "44196397"  # например, id Илон Маска
    db = DummyDB()
    monitor_user(user_id, db.get_last_tweet_id(user_id), db)
