import time
import random
from dotenv import load_dotenv
import os
from datetime import datetime, timedelta
from twitter_api import get_new_tweets
from gpt.gpt_main import generate_reply
from twitter_operator_test import open_tweet_with_proxy_like_bookmark_and_reply
from db.models import (
    Database, SettingsModel, InfluencerModel,
    TweetModel, AccountInfluencerModel, LogModel, ReplyModel
)

load_dotenv()
def log_message(log_queue, message: str, log_model: LogModel = None, account_id: int = None, event_type: str = "info"):
    """Логирует и в очередь, и в БД (если есть log_model и account_id)."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    formatted = f"[{now}] {message}"
    log_queue.put(formatted)

    if log_model and account_id:
        log_model.add_log(account_id, event_type, message)


def safe_generate_reply(tweet_text, gen_settings, log_queue, log_model, account_id, max_attempts=3):
    for attempt in range(1, max_attempts + 1):
        try:
            reply_data = generate_reply(tweet_text, gen_settings)
            reply_text = reply_data.get("reply", "")
            if reply_text and reply_text.strip():
                return reply_data

            wait_time = random.uniform(5, 10) * attempt
            log_message(
                log_queue,
                f"⚠️ Попытка {attempt} вернула пустой ответ, повтор через {wait_time:.1f} сек...",
                log_model, account_id, "warning"
            )
            time.sleep(wait_time)

        except Exception as e:
            wait_time = random.uniform(5, 10) * attempt
            log_message(
                log_queue,
                f"❌ Ошибка генерации (попытка {attempt}): {e}. Повтор через {wait_time:.1f} сек...",
                log_model, account_id, "error"
            )
            time.sleep(wait_time)

    return {"reply": "⚠️ Не удалось сгенерировать ответ", "model": None, "tone": gen_settings.get("tone")}


def monitor_account(account_info: dict, log_queue, db_name: str = "bot_database.db"):
    account_id = account_info["id"]
    account_username = account_info["username"]

    db = Database(db_name)
    settings_model = SettingsModel(db)
    influencer_model = InfluencerModel(db)
    tweet_model = TweetModel(db)
    account_influencer_model = AccountInfluencerModel(db)
    log_model = LogModel(db)
    reply_model = ReplyModel(db)

    log_message(log_queue, f"🔹 Мониторинг запущен для @{account_username} (account_id={account_id})",
                log_model, account_id, "start")

    settings = settings_model.get_settings(account_id) or {}
    post_check_interval = int(settings.get("post_check_interval", 120))
    daily_influencers_limit = int(settings.get("daily_influencers_limit", 2))
    update_period_minutes = int(settings.get("update_period_minutes", 5))
    gen_settings = {"tone": settings.get("tone", "friendly")}
    api_key = settings.get("tweetscout_api_key") or os.getenv("TWEETSCOUT_API_KEY")

    min_delay = int(settings.get("min_reply_delay", 3))
    max_delay = int(settings.get("max_reply_delay", 8))

    try:
        while True:
            daily_influencers = account_influencer_model.get_influencers_with_flag(account_id, checked=0)
            if not daily_influencers:
                account_influencer_model.reset_checked_flags(account_id)
                log_message(log_queue, f"🔄 [{account_username}] Все инфлюенсеры проверены, сброшены флаги is_checked",
                            log_model, account_id, "reset_flags")
                daily_influencers = account_influencer_model.get_influencers_with_flag(account_id, checked=0)

            daily_influencers = daily_influencers[:daily_influencers_limit]
            influencer_list = [f"@{inf['username']}" for inf in daily_influencers]
            log_message(log_queue, f"🔄 [{account_username}] Выбраны для проверки: {', '.join(influencer_list)}",
                        log_model, account_id, "select_influencers")

            batch_end_time = datetime.now() + timedelta(minutes=update_period_minutes)
            first_batch = True

            while datetime.now() < batch_end_time:
                for inf in daily_influencers:
                    inf_id = inf["influencer_id"]
                    inf_username = inf["username"]

                    inf_row = influencer_model.get_influencer_by_id(inf_id)
                    last_known_id = inf_row.get("last_tweet_id") if inf_row else None
                    fetch_count = 20 if last_known_id is None else 100

                    new_tweets, new_last = get_new_tweets(
                        username=inf_username,
                        api_key=api_key,
                        last_tweet_id=last_known_id,
                        count=fetch_count
                    )

                    if new_tweets:
                        for tw_id, tw_text in new_tweets:
                            existing = tweet_model.get_tweet_by_id(tw_id)
                            if not existing:
                                tweet_model.add_tweet(
                                    tweet_id=tw_id,
                                    influencer_id=inf_id,
                                    influencer_username=inf_username,
                                    content=tw_text,
                                    created_at=datetime.now()
                                )
                                log_message(log_queue, f"🆕 [{account_username}] Новый твит от @{inf_username}: {tw_text}",
                                            log_model, account_id, "new_tweet")

                                if not first_batch:
                                    reply_data = safe_generate_reply(tw_text, gen_settings, log_queue, log_model, account_id)
                                    reply_text = reply_data.get("reply", "⚠️ Не удалось сгенерировать ответ")

                                    reply_model.add_reply(
                                        account_id=account_id,
                                        tweet_id=tw_id,
                                        influencer_id=inf_id,
                                        tweet_content=tw_text,
                                        reply_text=reply_text,
                                        model_used=reply_data.get("model"),
                                        tone=reply_data.get("tone"),
                                        draft=False
                                    )

                                    log_message(log_queue,
                                                f"💬 [{account_username}] Ответ на твит {tw_id} от @{inf_username}: {reply_text}",
                                                log_model, account_id, "reply")

                                    try:
                                        open_tweet_with_proxy_like_bookmark_and_reply(
                                            profile_user_name=account_username,
                                            target_user_name=inf_username,
                                            tweet_id=tw_id,
                                            reply_text=reply_text,
                                            min_delay=min_delay,
                                            max_delay=max_delay,
                                            headed=True,
                                            db=db
                                        )
                                        log_message(log_queue,
                                                    f"✅ [{account_username}] Лайк/реплай/закладка выполнены для твита {tw_id}",
                                                    log_model, account_id, "action_done")
                                    except Exception as e:
                                        log_message(log_queue,
                                                    f"❌ [{account_username}] Ошибка при выполнении действий: {e}",
                                                    log_model, account_id, "error")

                                    time.sleep(random.uniform(min_delay, max_delay))

                        if new_last:
                            influencer_model.update_last_tweet_id(inf_id, new_last)
                            log_message(log_queue,
                                        f"ℹ️ [{account_username}] Обновлен last_tweet_id для @{inf_username}: {new_last}",
                                        log_model, account_id, "update_last_id")

                    else:
                        log_message(log_queue, f"ℹ️ [{account_username}] Нет новых твитов от @{inf_username}",
                                    log_model, account_id, "no_tweets")

                    time.sleep(random.uniform(min_delay, max_delay))

                first_batch = False
                log_message(log_queue,
                            f"⏳ [{account_username}] Ждем {post_check_interval} сек до следующей проверки...",
                            log_model, account_id, "sleep")
                time.sleep(post_check_interval)

            influencer_ids = [inf["influencer_id"] for inf in daily_influencers]
            account_influencer_model.set_checked_flags(influencer_ids)
            log_message(log_queue,
                        f"✔️ [{account_username}] Помечены как checked: {', '.join(influencer_list)}",
                        log_model, account_id, "checked")

    except Exception as e:
        log_message(log_queue, f"❌ [{account_username}] Ошибка мониторинга: {e}",
                    log_model, account_id, "error")
    finally:
        try:
            db.close()
        except Exception:
            pass
        log_message(log_queue, f"🛑 [{account_username}] Процесс мониторинга завершен.",
                    log_model, account_id, "stopped")
