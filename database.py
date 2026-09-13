import sqlite3

DATABASE = 'her.db'

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()

    # User Accounts
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            display_name TEXT DEFAULT 'Medha'
        )
    ''')

    # Living Profile Card
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS about_me (
            user_id INTEGER PRIMARY KEY,
            full_name TEXT,
            birthday TEXT,
            fav_color TEXT,
            fav_song TEXT,
            things_i_love TEXT,
            things_i_dislike TEXT,
            personality TEXT,
            values_text TEXT,
            current_era TEXT,
            what_makes_me_happy TEXT,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    ''')

    # Daily Hub & Calendar Memories
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS daily_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            entry_date TEXT NOT NULL,
            mood TEXT,
            sleep_hours REAL DEFAULT 0,
            sleep_quality TEXT,
            study_hours REAL DEFAULT 0,
            money_spent REAL DEFAULT 0,
            journal_entry TEXT,
            song_title TEXT,
            song_artist TEXT,
            UNIQUE(user_id, entry_date),
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    ''')

    # Daily Habits
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS habits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            entry_date TEXT NOT NULL,
            habit_name TEXT NOT NULL,
            is_done INTEGER DEFAULT 0,
            UNIQUE(user_id, entry_date, habit_name),
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    ''')

    # Categorized Spending
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            entry_date TEXT NOT NULL,
            title TEXT NOT NULL,
            category TEXT NOT NULL,
            amount REAL NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    ''')

    # Checklist Tasks
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            task_date TEXT NOT NULL,
            title TEXT NOT NULL,
            is_completed INTEGER DEFAULT 0,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    ''')

    # Bucket List, Places, Wishlist, Skills & Vision Pins
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS life_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            category TEXT NOT NULL,
            title TEXT NOT NULL,
            subtitle TEXT,
            progress INTEGER DEFAULT 0,
            image_path TEXT,
            extra_meta TEXT,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    ''')

    # Sidebar Music Player Track
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS custom_music (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            audio_source TEXT NOT NULL,
            is_active INTEGER DEFAULT 1,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    ''')

    conn.commit()
    conn.close()

if __name__ == '__main__':
    init_db()