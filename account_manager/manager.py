from db.models import AccountModel
from db.models import SettingsModel
from db.models import InfluencerModel
from db.models import AccountInfluencerModel
from auth import open_twitter_profile

class AccountManager:
    def __init__(self, db):
        self.account_model = AccountModel(db)
        self.settings_model = SettingsModel(db)
        self.influencer_model = InfluencerModel(db)
        self.account_influencer_model = AccountInfluencerModel(db)

    # ---------------- Работа с аккаунтами ----------------
    def register_account(self):
        user_name = input("Введите имя профиля для регистрации: ").strip()
        use_proxy = input("Использовать прокси? (y/n): ").strip().lower() == "y"
        proxy_url = input("Прокси (user:pass@ip:port): ").strip() if use_proxy else None

        driver = open_twitter_profile(
            user_name=user_name,
            mode="signup",
            use_proxy=use_proxy,
            proxy_url=proxy_url,
            extension_path=None,
            headed=True
        )
        input("➡️ Войдите в ленту (home), затем нажмите Enter для продолжения...")

        account = self.account_model.get_account_by_username(user_name)
        if account:
            self.settings_model.add_settings_for_account(account["id"])
            print("✅ Аккаунт и настройки добавлены в базу.", flush=True)

        try:
            driver.quit()
        except Exception as e:
            print(f"Ошибка при закрытии браузера: {e}", flush=True)

    def check_account(self):
        user_name = input("Введите имя аккаунта для проверки: ").strip()
        account = self.account_model.get_account_by_username(user_name)
        if not account:
            print(f"⚠️ Аккаунт {user_name} не найден.", flush=True)
            return

        try:
            driver = open_twitter_profile(
                user_name=user_name,
                mode="login",
                use_proxy=bool(account["proxy"]),
                proxy_url=account["proxy"] if account["proxy"] else None,
                extension_path=None,
                headed=True
            )
            input("➡️ Когда окно аккаунта откроется, нажмите Enter для продолжения и закрытия браузера...")
            print(f"✅ Аккаунт {user_name} успешно открыт.", flush=True)
        except Exception as e:
            print(f"Ошибка при открытии аккаунта {user_name}: {e}", flush=True)
        finally:
            try:
                driver.quit()
            except Exception:
                pass

    def settings_menu(self):
        user_name = input("Введите имя аккаунта для настройки: ").strip()
        account = self.account_model.get_account_by_username(user_name)
        if not account:
            print(f"⚠️ Аккаунт {user_name} не найден.", flush=True)
            return

        account_id = account["id"]
        while True:
            print("\n=== Настройка аккаунта ===")
            print("1. Настроить тон и задержки реплая")
            print("2. Добавить (заменить) глобальный список инфлюенсеров")
            print("3. Расширить глобальный список инфлюенсеров")
            print("4. Назад в главное меню")
            choice = input("Выберите действие: ").strip()

            if choice == "1":
                self.update_tone_and_delays(account_id)
            elif choice == "2":
                self.add_influencer_list(account_id)
            elif choice == "3":
                self.extend_influencer_list(account_id)
            elif choice == "4":
                break
            else:
                print("❌ Неверный ввод, попробуйте снова.", flush=True)

    # ---------------- Методы настройки ----------------
    def update_tone_and_delays(self, account_id):
        try:
            new_tone = input("Новый тон (friendly, neutral, aggressive): ").strip()
            min_reply = int(input("Мин. задержка реплая (сек): ").strip())
            max_reply = int(input("Макс. задержка реплая (сек): ").strip())
            daily_limit = int(input("Дневной лимит инфлюенсеров: ").strip())
            interval = int(input("Интервал проверки постов (сек): ").strip())
            update_period = int(input("Период обновления (мин): ").strip())  # Запрашиваем в минутах
        except ValueError:
            print("❌ Введены неверные данные, попробуйте снова.", flush=True)
            return

        updated = self.settings_model.update_settings(
            account_id,
            tone=new_tone,
            min_reply_delay=min_reply,
            max_reply_delay=max_reply,
            daily_influencers_limit=daily_limit,
            post_check_interval=interval,
            update_period_minutes=update_period  # Передаем update_period_minutes
        )
        current = self.settings_model.get_settings(account_id)
        print("Текущие настройки:", current, flush=True)
        print("✅ Настройки успешно применены." if updated else "❌ Ошибка при обновлении настроек.", flush=True)

    # ---------------- Работа со списками инфлюенсеров ----------------
    def add_influencer_list(self, account_id: int):
        confirm = input("⚠️ Старый список инфлюенсеров будет удалён.\nПродолжить? (y/n): ").strip()
        if confirm.lower() != "y":
            return

        self.account_influencer_model.clear_global_list(account_id)
        print("Введите имена инфлюенсеров построчно. Чтобы закончить — оставьте строку пустой:", flush=True)

        usernames = []
        while True:
            name = input().strip()
            if not name:
                break
            usernames.append(name)

        if not usernames:
            print("⚠️ Список пуст — ничего не добавлено.", flush=True)
            return

        influencer_ids = []
        for username in usernames:
            existing = self.influencer_model.get_influencer_by_username(username)
            if existing:
                influencer_ids.append(existing["id"])
            else:
                influencer_id = self.influencer_model.add_influencer(username)
                influencer_ids.append(influencer_id)
                print(f"ℹ️ Добавлен новый инфлюенсер: {username}", flush=True)

        self.account_influencer_model.add_to_global_list(account_id, influencer_ids)
        print(f"✅ Добавлено {len(influencer_ids)} инфлюенсеров в глобальный список.", flush=True)

    def extend_influencer_list(self, account_id: int):
        print("Введите новые имена инфлюенсеров построчно. Чтобы закончить — оставьте строку пустой:", flush=True)

        usernames = []
        while True:
            name = input().strip()
            if not name:
                break
            usernames.append(name)

        if not usernames:
            print("⚠️ Список пуст — ничего не добавлено.", flush=True)
            return

        influencer_ids = []
        for username in usernames:
            existing = self.influencer_model.get_influencer_by_username(username)
            if existing:
                influencer_ids.append(existing["id"])
            else:
                influencer_id = self.influencer_model.add_influencer(username)
                influencer_ids.append(influencer_id)
                print(f"ℹ️ Добавлен новый инфлюенсер: {username}", flush=True)

        self.account_influencer_model.add_to_global_list(account_id, influencer_ids)
        print(f"✅ Добавлено {len(influencer_ids)} новых инфлюенсеров в глобальный список.", flush=True)