import sqlite3
from contextlib import closing
from datetime import datetime
from typing import Any, Dict, List, Optional

# ---------------- Database ----------------
class Database:
    """SQLite wrapper with context manager support."""
    def __init__(self, db_name: str = "bot_database.db"):
        self.conn = sqlite3.connect(db_name, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row

    def cursor(self) -> sqlite3.Cursor:
        return self.conn.cursor()

    def commit(self) -> None:
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if exc_type is None:
            self.commit()
        self.close()


# ---------------- BaseModel ----------------
class BaseModel:
    def __init__(self, db: Database):
        self.db = db

    def _fetchone(self, sql: str, params: tuple = ()) -> Optional[Dict[str, Any]]:
        with closing(self.db.cursor()) as cursor:
            cursor.execute(sql, params)
            row = cursor.fetchone()
            return dict(row) if row else None

    def _fetchall(self, sql: str, params: tuple = ()) -> List[Dict[str, Any]]:
        with closing(self.db.cursor()) as cursor:
            cursor.execute(sql, params)
            return [dict(row) for row in cursor.fetchall()]

    def _execute(self, sql: str, params: tuple = ()) -> int:
        with closing(self.db.cursor()) as cursor:
            cursor.execute(sql, params)
            self.db.commit()
            return cursor.lastrowid

    def _update(self, table: str, identifier_field: str, identifier_value: Any, **fields) -> int:
        """Generic update with automatic updated_at field."""
        if not fields:
            return 0
        columns = ", ".join(f"{k} = ?" for k in fields.keys())
        values = list(fields.values()) + [identifier_value]
        sql = f"UPDATE {table} SET {columns}, updated_at = CURRENT_TIMESTAMP WHERE {identifier_field} = ?"
        with closing(self.db.cursor()) as cursor:
            cursor.execute(sql, values)
            self.db.commit()
            return cursor.rowcount


# ---------------- Accounts ----------------
class AccountModel(BaseModel):
    def add_account(self, username: str, profile_dir: str, proxy: Optional[str] = None) -> int:
        return self._execute(
            "INSERT OR IGNORE INTO accounts (username, profile_dir, proxy) VALUES (?, ?, ?)",
            (username, profile_dir, proxy)
        )

    def update_account(self, username: str, profile_dir: Optional[str] = None, proxy: Optional[str] = None) -> int:
        return self._update("accounts", "username", username, profile_dir=profile_dir, proxy=proxy)

    def get_account_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        return self._fetchone("SELECT * FROM accounts WHERE username = ?", (username,))

    def get_all_accounts(self) -> List[Dict[str, Any]]:
        return self._fetchall("SELECT * FROM accounts")


# ---------------- Settings ----------------
class SettingsModel(BaseModel):
    allowed_fields = {"tone", "min_reply_delay", "max_reply_delay",
                      "daily_influencers_limit", "post_check_interval", "update_period_minutes"}

    def add_settings_for_account(self, account_id: int) -> int:
        return self._execute("INSERT OR IGNORE INTO settings (account_id) VALUES (?)", (account_id,))

    def get_settings(self, account_id: int) -> Optional[Dict[str, Any]]:
        return self._fetchone("SELECT * FROM settings WHERE account_id = ?", (account_id,))

    def update_settings(self, account_id: int, **kwargs) -> bool:
        fields = {k: v for k, v in kwargs.items() if k in self.allowed_fields and v is not None}
        return bool(self._update("settings", "account_id", account_id, **fields))


# ---------------- Influencers ----------------
class InfluencerModel(BaseModel):
    def add_influencer(self, username: str, description: Optional[str] = None, active: bool = True) -> int:
        return self._execute(
            "INSERT OR IGNORE INTO influencers (username, description, active, last_tweet_id) VALUES (?, ?, ?, NULL)",
            (username, description, int(active))
        )

    def update_influencer(self, influencer_id: int, **kwargs) -> int:
        return self._update("influencers", "id", influencer_id, **kwargs)

    def get_influencer_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        return self._fetchone("SELECT * FROM influencers WHERE username = ?", (username,))

    def get_influencer_by_id(self, influencer_id: int) -> Optional[Dict[str, Any]]:
        return self._fetchone("SELECT * FROM influencers WHERE id = ?", (influencer_id,))

    def get_all_influencers(self) -> List[Dict[str, Any]]:
        return self._fetchall("SELECT * FROM influencers")

    def get_influencer_id_by_username(self, username: str) -> Optional[int]:
        row = self._fetchone("SELECT id FROM influencers WHERE username = ?", (username,))
        return row["id"] if row else None

    def update_last_tweet_id(self, influencer_id: int, last_tweet_id: str) -> int:
        return self._update("influencers", "id", influencer_id, last_tweet_id=last_tweet_id)


# ---------------- Tweets ----------------
class TweetModel(BaseModel):
    def add_tweet(self, tweet_id: str, influencer_id: int, influencer_username: str,
                  content: Optional[str] = None, likes_count: int = 0,
                  replies_count: int = 0, created_at: Optional[str] = None) -> int:
        return self._execute(
            """INSERT OR IGNORE INTO tweets 
            (tweet_id, influencer_id, influencer_username, content, likes_count, replies_count, created_at, processing, failed_count) 
            VALUES (?, ?, ?, ?, ?, ?, ?, 0, 0)""",
            (tweet_id, influencer_id, influencer_username, content, likes_count, replies_count, created_at)
        )

    def update_tweet(self, tweet_id: str, **kwargs) -> int:
        return self._update("tweets", "tweet_id", tweet_id, **kwargs)

    def get_tweet_by_id(self, tweet_id: str) -> Optional[Dict[str, Any]]:
        return self._fetchone("SELECT * FROM tweets WHERE tweet_id = ?", (tweet_id,))

    def get_unreplied_tweets(self) -> List[Dict[str, Any]]:
        return self._fetchall("SELECT * FROM tweets WHERE reply_posted = 0 AND processing = 0")

    def claim_tweet(self, tweet_id: str) -> bool:
        sql = "UPDATE tweets SET processing=1 WHERE tweet_id=? AND reply_posted=0 AND processing=0"
        with closing(self.db.cursor()) as cursor:
            cursor.execute(sql, (tweet_id,))
            self.db.commit()
            return cursor.rowcount == 1


# ---------------- Replies ----------------
class ReplyModel(BaseModel):
    def add_reply(self, account_id: int, tweet_id: str, influencer_id: int,
                  tweet_content: str, reply_text: str,
                  model_used: Optional[str] = None, tone: Optional[str] = None, draft: bool = True) -> int:
        return self._execute(
            """INSERT INTO replies 
            (account_id, tweet_id, influencer_id, tweet_content, reply_text, model_used, tone, draft) 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (account_id, tweet_id, influencer_id, tweet_content, reply_text, model_used, tone, int(draft))
        )

    def get_replies_for_tweet(self, tweet_id: str) -> List[Dict[str, Any]]:
        return self._fetchall("SELECT * FROM replies WHERE tweet_id = ?", (tweet_id,))

    def get_replies_for_account(self, account_id: int) -> List[Dict[str, Any]]:
        return self._fetchall("SELECT * FROM replies WHERE account_id = ?", (account_id,))

    def mark_posted(self, reply_id: int) -> int:
        return self._update("replies", "id", reply_id, draft=0, posted_at="CURRENT_TIMESTAMP")


# ---------------- Logs ----------------
class LogModel(BaseModel):
    def add_log(self, account_id: int, event_type: str, event_data: Optional[str] = None) -> int:
        return self._execute(
            "INSERT INTO logs (account_id, event_type, event_data) VALUES (?, ?, ?)",
            (account_id, event_type, event_data)
        )


    def get_logs_for_account(self, account_id: int) -> List[Dict[str, Any]]:
        return self._fetchall("SELECT * FROM logs WHERE account_id = ?", (account_id,))



# ---------------- AccountInfluencers ----------------
class AccountInfluencerModel(BaseModel):
    def assign_influencer(self, account_id: int, influencer_id: int,
                          is_global: bool = False, is_checked: bool = False, active: bool = True) -> int:
        return self._execute(
            """INSERT OR IGNORE INTO account_influencers 
            (account_id, influencer_id, is_global, is_checked, active, last_update) 
            VALUES (?, ?, ?, ?, ?, NULL)""",
            (account_id, influencer_id, int(is_global), int(is_checked), int(active))
        )

    def update_assignment(self, assignment_id: int, **kwargs) -> int:
        return self._update("account_influencers", "id", assignment_id, **kwargs)

    def clear_global_list(self, account_id: int) -> None:
        with closing(self.db.cursor()) as cursor:
            cursor.execute(
                "DELETE FROM account_influencers WHERE account_id = ? AND is_global = 1",
                (account_id,)
            )
            self.db.commit()

    def add_to_global_list(self, account_id: int, influencer_ids: list[int]) -> None:
        with closing(self.db.cursor()) as cursor:
            for inf_id in influencer_ids:
                cursor.execute(
                    """INSERT OR IGNORE INTO account_influencers 
                    (account_id, influencer_id, is_global, is_checked, active, last_update)
                    VALUES (?, ?, 1, 0, 1, NULL)""",
                    (account_id, inf_id)
                )
            self.db.commit()

    def get_assignments_for_account(self, account_id: int) -> list[dict]:
        return self._fetchall("SELECT * FROM account_influencers WHERE account_id = ?", (account_id,))

    def get_global_list(self, account_id: int) -> list[dict]:
        return self._fetchall(
            "SELECT * FROM account_influencers WHERE account_id=? AND is_global=1 AND active=1 ORDER BY id",
            (account_id,)
        )

    def get_checked_influencers(self, account_id: int) -> list[dict]:
        return self._fetchall(
            """SELECT ai.*, i.username 
            FROM account_influencers ai 
            JOIN influencers i ON ai.influencer_id = i.id 
            WHERE ai.account_id=? AND ai.is_checked=1 AND ai.active=1
            ORDER BY ai.id""",
            (account_id,)
        )

    def get_all_influencers_for_account(self, account_id: int) -> list[dict]:
        return self._fetchall(
            """SELECT i.id AS influencer_id, i.username
            FROM account_influencers ai
            JOIN influencers i ON ai.influencer_id = i.id
            WHERE ai.account_id = ? AND ai.active = 1
            ORDER BY i.username""",
            (account_id,)
        )

    def rotate_checked_influencers(self, account_id: int, limit: int) -> int:
        """Ротация инфлюенсеров для daily/checked списка"""
        with closing(self.db.cursor()) as cursor:
            cursor.execute(
                "SELECT id FROM account_influencers WHERE account_id=? AND is_checked=0 AND active=1 ORDER BY id ASC LIMIT ?",
                (account_id, limit)
            )
            candidates = cursor.fetchall()

            if not candidates:
                # Сброс всех для повторного выбора
                cursor.execute("UPDATE account_influencers SET is_checked=0 WHERE account_id=?", (account_id,))
                self.db.commit()

                cursor.execute(
                    "SELECT id FROM account_influencers WHERE account_id=? AND is_checked=0 AND active=1 ORDER BY id ASC LIMIT ?",
                    (account_id, limit)
                )
                candidates = cursor.fetchall()

            if not candidates:
                return 0

            ids = [row["id"] for row in candidates]
            placeholders = ",".join("?" for _ in ids)
            sql = f"UPDATE account_influencers SET is_checked=1, last_update=CURRENT_TIMESTAMP WHERE id IN ({placeholders})"
            cursor.execute(sql, ids)
            self.db.commit()
            return len(ids)

    def set_checked_flags(self, influencer_ids):
        """Помечаем инфлюенсеров как уже выбранных"""
        query = "UPDATE account_influencers SET is_checked = 1 WHERE influencer_id IN ({})".format(
            ",".join("?" * len(influencer_ids))
        )
        self.db.cursor().execute(query, influencer_ids)
        self.db.commit()

    def reset_checked_flags(self, account_id):
        """Сбрасываем is_checked для всех инфлюенсеров аккаунта"""
        query = "UPDATE account_influencers SET is_checked = 0 WHERE account_id = ?"
        self.db.cursor().execute(query, (account_id,))
        self.db.commit()

    # ---------------- Новый метод ----------------
    def get_influencers_with_flag(self, account_id: int, checked: int = 0) -> list[dict]:
        """Возвращает инфлюенсеров с указанным флагом is_checked."""
        return self._fetchall(
            """SELECT ai.influencer_id, i.username
               FROM account_influencers ai
               JOIN influencers i ON ai.influencer_id = i.id
               WHERE ai.account_id = ? AND ai.is_checked = ? AND ai.active = 1
               ORDER BY ai.id""",
            (account_id, checked)
        )

    def set_checked_flags(self, influencer_ids: list[int]):
        """Помечаем инфлюенсеров как уже выбранных."""
        if not influencer_ids:
            return
        query = "UPDATE account_influencers SET is_checked = 1, last_update=CURRENT_TIMESTAMP WHERE influencer_id IN ({})".format(
            ",".join("?" * len(influencer_ids))
        )
        with closing(self.db.cursor()) as cursor:
            cursor.execute(query, influencer_ids)
            self.db.commit()