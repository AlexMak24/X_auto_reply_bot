# main.py
import logging
import sys
import time
from multiprocessing import Process, Manager
from threading import Thread
import queue
from db.db import create_tables
from db.models import Database, SettingsModel
from account_manager.manager import AccountManager
from monitoring import monitor_account   # файл выше

# ---------------- Настройка логирования ----------------
logging.basicConfig(
    level=logging.WARNING,  # оставляем только WARNING и выше
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    stream=sys.stdout
)

# Глушим сторонние логгеры, чтобы WebDriver Manager, Selenium и urllib3 не спамили INFO
for noisy_logger in ("WDM", "seleniumwire", "selenium", "urllib3"):
    logging.getLogger(noisy_logger).setLevel(logging.WARNING)

# ---------------- Инициализация ----------------
create_tables()
db = Database()
manager = AccountManager(db)

active_monitors = {}  # account_id -> Process

# ---------------- Мониторинг ----------------
def handle_start_monitoring(log_queue):
    user_name = input("Введите имя аккаунта для мониторинга: ").strip()
    account = manager.account_model.get_account_by_username(user_name)
    if not account:
        print(f"⚠️ Аккаунт {user_name} не найден.", flush=True)
        return

    account_id = account["id"]
    if account_id in active_monitors:
        print("❌ Мониторинг уже запущен.", flush=True)
        return

    # ensure settings exist
    settings_model = SettingsModel(db)
    settings = settings_model.get_settings(account_id)
    if not settings:
        settings_model.add_settings_for_account(account_id)
        settings = settings_model.get_settings(account_id)
        print(f"⚠️ Настройки для @{user_name} не найдены — созданы значения по умолчанию.", flush=True)

    account_info = {"id": account_id, "username": account["username"]}
    p = Process(target=monitor_account, args=(account_info, log_queue), daemon=True)
    p.start()
    active_monitors[account_id] = p
    print(f"✅ Мониторинг запущен для {user_name} (PID: {p.pid})", flush=True)

def handle_stop_monitoring():
    user_name = input("Введите имя аккаунта для остановки мониторинга: ").strip()
    account = manager.account_model.get_account_by_username(user_name)
    if not account:
        print(f"⚠️ Аккаунт {user_name} не найден.", flush=True)
        return

    account_id = account["id"]
    if account_id not in active_monitors:
        print("❌ Мониторинг для этого аккаунта не запущен.", flush=True)
        return

    p = active_monitors[account_id]
    p.terminate()
    p.join()
    del active_monitors[account_id]
    print(f"✅ Мониторинг остановлен для {user_name}", flush=True)

# ---------------- Просмотр логов ----------------
def input_reader(stop_flag):
    try:
        line = input().strip().lower()
        if line == "q":
            stop_flag.value = True
    except Exception:
        stop_flag.value = True

def view_logs(log_queue, stop_flag):
    print("\n=== Просмотр логов (введите 'q' + Enter для выхода) ===", flush=True)
    stop_flag.value = False
    t = Thread(target=input_reader, args=(stop_flag,), daemon=True)
    t.start()
    try:
        while not stop_flag.value:
            try:
                msg = log_queue.get(timeout=0.5)
                if msg == "__STOP__":
                    break
                print(msg, flush=True)
            except queue.Empty:
                continue
    except KeyboardInterrupt:
        print("\nВыход из просмотра логов (Ctrl+C).", flush=True)
    finally:
        stop_flag.value = True
        t.join()
        print("Выход из просмотра логов.\n", flush=True)

# ---------------- Главное меню ----------------
def main_menu():
    print("\n=== Twitter Bot — Главное меню ===", flush=True)
    print("1. Зарегистрировать новый аккаунт", flush=True)
    print("2. Проверить аккаунт", flush=True)
    print("3. Настроить аккаунт", flush=True)
    print("4. Начать мониторинг", flush=True)
    print("5. Остановить мониторинг", flush=True)
    print("6. Просмотреть логи", flush=True)
    print("7. Выход", flush=True)
    return input("Выберите действие: ").strip()

# ---------------- Основной цикл ----------------
if __name__ == "__main__":
    with Manager() as mgr:
        log_queue = mgr.Queue()
        stop_flag = mgr.Value('b', False)

        try:
            while True:
                choice = main_menu()
                if choice == "1":
                    manager.register_account()
                elif choice == "2":
                    manager.check_account()
                elif choice == "3":
                    manager.settings_menu()
                elif choice == "4":
                    handle_start_monitoring(log_queue)
                elif choice == "5":
                    handle_stop_monitoring()
                elif choice == "6":
                    view_logs(log_queue, stop_flag)
                elif choice == "7":
                    print("👋 Выход.", flush=True)
                    break
                else:
                    print("❌ Неверный ввод, попробуйте снова.", flush=True)
        except KeyboardInterrupt:
            print("\nПрограмма завершена через Ctrl+C.", flush=True)
        finally:
            # Завершим все мониторинги
            for p in list(active_monitors.values()):
                try:
                    p.terminate()
                    p.join(timeout=2)
                except Exception:
                    pass
            active_monitors.clear()
            # сигналим логам на остановку
            try:
                log_queue.put("__STOP__")
            except Exception:
                pass
            db.close()
