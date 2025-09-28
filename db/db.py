import sqlite3

def create_tables(db_name="bot_database.db"):
    sql_statements = [
        """
        CREATE TABLE IF NOT EXISTS accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            profile_dir TEXT NOT NULL,
            proxy TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id INTEGER UNIQUE NOT NULL,
            tone TEXT DEFAULT 'friendly',
            min_reply_delay INTEGER DEFAULT 10,
            max_reply_delay INTEGER DEFAULT 120,
            daily_influencers_limit INTEGER DEFAULT 20,
            post_check_interval INTEGER DEFAULT 60,
            update_period_minutes INTEGER DEFAULT 1440,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (account_id) REFERENCES accounts(id) ON DELETE CASCADE
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS influencers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            description TEXT,
            active BOOLEAN DEFAULT 1,
            last_tweet_id TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS influencer_posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            influencer_id INTEGER NOT NULL,
            post_id TEXT NOT NULL UNIQUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (influencer_id) REFERENCES influencers(id) ON DELETE CASCADE
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS account_influencers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id INTEGER NOT NULL,
            influencer_id INTEGER NOT NULL,
            assigned_date DATE DEFAULT CURRENT_DATE,
            active BOOLEAN DEFAULT 1,
            is_global BOOLEAN DEFAULT 0,
            is_checked BOOLEAN DEFAULT 0,
            short_list_index INTEGER DEFAULT 0,
            last_update TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (account_id) REFERENCES accounts(id) ON DELETE CASCADE,
            FOREIGN KEY (influencer_id) REFERENCES influencers(id) ON DELETE CASCADE,
            UNIQUE (account_id, influencer_id)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS tweets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tweet_id TEXT UNIQUE NOT NULL,
            influencer_id INTEGER NOT NULL,
            influencer_username TEXT NOT NULL,
            content TEXT,
            likes_count INTEGER DEFAULT 0,
            replies_count INTEGER DEFAULT 0,
            created_at TIMESTAMP,
            checked_at TIMESTAMP,
            reply_posted BOOLEAN DEFAULT 0,
            processing BOOLEAN DEFAULT 0,
            failed_count INTEGER DEFAULT 0,
            FOREIGN KEY (influencer_id) REFERENCES influencers(id) ON DELETE CASCADE
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS replies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id INTEGER NOT NULL,
            tweet_id INTEGER NOT NULL,
            influencer_id INTEGER NOT NULL,
            tweet_content TEXT,
            reply_text TEXT NOT NULL,
            model_used TEXT,
            tone TEXT,
            draft BOOLEAN DEFAULT 1,
            posted_at TIMESTAMP,
            FOREIGN KEY (account_id) REFERENCES accounts(id) ON DELETE CASCADE,
            FOREIGN KEY (tweet_id) REFERENCES tweets(id) ON DELETE CASCADE,
            FOREIGN KEY (influencer_id) REFERENCES influencers(id) ON DELETE CASCADE
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id INTEGER NOT NULL,
            event_type TEXT NOT NULL,
            event_data TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (account_id) REFERENCES accounts(id) ON DELETE CASCADE
        )
        """
    ]

    with sqlite3.connect(db_name) as conn:
        cursor = conn.cursor()
        for sql in sql_statements:
            cursor.execute(sql)
        conn.commit()
