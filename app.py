import os
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, Response, send_from_directory
from flask_bcrypt import Bcrypt
from datetime import datetime
from dotenv import load_dotenv
import database

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'her_default_secure_key_fallback_2026')

app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

IMAGE_UPLOAD_FOLDER = os.path.join('static', 'uploads')
AUDIO_UPLOAD_FOLDER = os.path.join('static', 'uploads', 'audio')
os.makedirs(IMAGE_UPLOAD_FOLDER, exist_ok=True)
os.makedirs(AUDIO_UPLOAD_FOLDER, exist_ok=True)

app.config['UPLOAD_FOLDER'] = IMAGE_UPLOAD_FOLDER
app.config['AUDIO_FOLDER'] = AUDIO_UPLOAD_FOLDER
ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
ALLOWED_AUDIO_EXTENSIONS = {'mp3', 'wav', 'ogg', 'm4a', 'aac'}

def allowed_image(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_IMAGE_EXTENSIONS

def allowed_audio(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_AUDIO_EXTENSIONS

def current_user_id():
    return session.get('user_id')

@app.before_request
def setup_db_once():
    database.init_db()

@app.errorhandler(413)
def request_entity_too_large(error):
    return "<script>alert('File too large! Maximum allowed upload size is 16 MB. ♡'); window.history.back();</script>", 413

# --- PWA Service Worker Route ---
@app.route('/sw.js')
def service_worker():
    return send_from_directory('static', 'sw.js', mimetype='application/javascript')

# --- Auth Routes ---
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        display_name = request.form.get('display_name', '').strip() or 'Medha'

        if not username or not password:
            return render_template('signup.html', error='Please fill out all fields.')

        conn = database.get_db()
        existing = conn.execute('SELECT id FROM users WHERE username = ?', (username,)).fetchone()
        if existing:
            conn.close()
            return render_template('signup.html', error='Username already taken. Please choose another or login.')

        try:
            hashed_pw = bcrypt.generate_password_hash(password)
            if isinstance(hashed_pw, bytes):
                hashed_pw = hashed_pw.decode('utf-8')
        except Exception:
            hashed_pw = password

        conn.execute(
            'INSERT INTO users (username, password, display_name) VALUES (?, ?, ?)',
            (username, hashed_pw, display_name)
        )
        conn.commit()

        user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
        conn.execute(
            'INSERT INTO about_me (user_id, full_name, current_era) VALUES (?, ?, ?)',
            (user['id'], display_name, 'Soft Growth & Quiet Confidence ✨')
        )
        conn.commit()
        conn.close()

        session['user_id'] = user['id']
        session['display_name'] = user['display_name']
        return redirect(url_for('home'))

    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()

        conn = database.get_db()
        user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()

        if user:
            stored_pw = user['password']
            password_valid = False
            try:
                password_valid = bcrypt.check_password_hash(stored_pw, password)
            except Exception:
                password_valid = (stored_pw == password)

            if password_valid:
                session['user_id'] = user['id']
                session['display_name'] = user['display_name']
                conn.close()
                return redirect(url_for('home'))

        conn.close()
        return render_template('login.html', error='Invalid username or password.')

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# --- Home Dashboard ---
@app.route('/', methods=['GET', 'POST'])
def home():
    if not current_user_id():
        return redirect(url_for('login'))

    today_str = datetime.today().strftime('%Y-%m-%d')
    conn = database.get_db()

    if request.method == 'POST':
        title = request.form.get('title')
        if title:
            conn.execute(
                'INSERT INTO tasks (user_id, task_date, title) VALUES (?, ?, ?)',
                (current_user_id(), today_str, title)
            )
            conn.commit()
        conn.close()
        return redirect(url_for('home'))

    record = conn.execute(
        'SELECT * FROM daily_records WHERE user_id = ? AND entry_date = ?',
        (current_user_id(), today_str)
    ).fetchone()

    tasks = conn.execute(
        'SELECT * FROM tasks WHERE user_id = ? AND task_date = ? ORDER BY id DESC',
        (current_user_id(), today_str)
    ).fetchall()

    soundtracks = conn.execute(
        'SELECT * FROM custom_music WHERE user_id = ? ORDER BY id DESC',
        (current_user_id(),)
    ).fetchall()

    conn.close()
    return render_template('home.html', today=today_str, record=record, tasks=tasks, soundtracks=soundtracks)

# --- Soundtrack Upload Handler (Device-Only) ---
@app.route('/add-soundtrack', methods=['POST'])
def add_soundtrack():
    if not current_user_id():
        return redirect(url_for('login'))

    title = request.form.get('title', '').strip()
    artist = request.form.get('artist', '').strip()
    today_str = datetime.today().strftime('%Y-%m-%d')

    if 'audio_file' in request.files:
        file = request.files['audio_file']
        if file and file.filename != '' and allowed_audio(file.filename):
            original_stem = file.filename.rsplit('.', 1)[0]
            if not title:
                if '-' in original_stem:
                    parts = original_stem.split('-', 1)
                    title = parts[0].strip()
                    if not artist:
                        artist = parts[1].strip()
                else:
                    title = original_stem.replace('_', ' ').strip()

            if not artist:
                artist = 'Soundtrack'

            ext = file.filename.rsplit('.', 1)[1].lower()
            timestamp = int(datetime.now().timestamp())
            clean_name = f"song_{current_user_id()}_{timestamp}.{ext}"
            save_path = os.path.join(app.config['AUDIO_FOLDER'], clean_name)
            file.save(save_path)
            audio_source = f"/static/uploads/audio/{clean_name}"

            display_title = f"{title} • {artist}"

            conn = database.get_db()
            conn.execute(
                'INSERT INTO custom_music (user_id, title, audio_source) VALUES (?, ?, ?)',
                (current_user_id(), display_title, audio_source)
            )
            conn.execute('''
                INSERT INTO daily_records (user_id, entry_date, song_title, song_artist)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(user_id, entry_date) DO UPDATE SET
                    song_title = excluded.song_title,
                    song_artist = excluded.song_artist
            ''', (current_user_id(), today_str, title, artist))
            conn.commit()
            conn.close()

    return redirect(url_for('home'))

@app.route('/delete-soundtrack/<int:song_id>', methods=['POST'])
def delete_soundtrack(song_id):
    if not current_user_id():
        return jsonify({'error': 'Unauthorized'}), 401

    conn = database.get_db()
    song = conn.execute('SELECT audio_source FROM custom_music WHERE id = ? AND user_id = ?', (song_id, current_user_id())).fetchone()
    if song and song['audio_source'].startswith('/static/uploads/audio/'):
        rel = song['audio_source'].lstrip('/')
        if os.path.exists(rel):
            try:
                os.remove(rel)
            except OSError:
                pass

    conn.execute('DELETE FROM custom_music WHERE id = ? AND user_id = ?', (song_id, current_user_id()))
    conn.commit()
    conn.close()
    return jsonify({'status': 'success'})

@app.route('/set-mood', methods=['POST'])
def set_mood():
    if not current_user_id():
        return jsonify({'error': 'Unauthorized'}), 401

    data = request.get_json() or {}
    mood = data.get('mood')
    today_str = datetime.today().strftime('%Y-%m-%d')

    if mood:
        conn = database.get_db()
        conn.execute('''
            INSERT INTO daily_records (user_id, entry_date, mood)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id, entry_date) DO UPDATE SET
                mood = excluded.mood
        ''', (current_user_id(), today_str, mood))
        conn.commit()
        conn.close()

    return jsonify({'status': 'success'})

@app.route('/add-task', methods=['POST'])
def add_task():
    if not current_user_id():
        return redirect(url_for('login'))

    title = request.form.get('title')
    today_str = datetime.today().strftime('%Y-%m-%d')

    if title:
        conn = database.get_db()
        conn.execute(
            'INSERT INTO tasks (user_id, task_date, title) VALUES (?, ?, ?)',
            (current_user_id(), today_str, title)
        )
        conn.commit()
        conn.close()

    return redirect(url_for('home'))

@app.route('/toggle-task/<int:task_id>', methods=['POST'])
def toggle_task(task_id):
    if not current_user_id():
        return jsonify({'error': 'Unauthorized'}), 401

    conn = database.get_db()
    conn.execute('UPDATE tasks SET is_completed = 1 - is_completed WHERE id = ? AND user_id = ?', (task_id, current_user_id()))
    conn.commit()
    conn.close()
    return jsonify({'status': 'success'})

@app.route('/delete-task/<int:task_id>', methods=['POST'])
def delete_task(task_id):
    if not current_user_id():
        return jsonify({'error': 'Unauthorized'}), 401

    conn = database.get_db()
    conn.execute('DELETE FROM tasks WHERE id = ? AND user_id = ?', (task_id, current_user_id()))
    conn.commit()
    conn.close()
    return jsonify({'status': 'success'})

# --- Calendar APIs & Memory Dot Indicators ---
@app.route('/api/memory-indicators/<month_prefix>')
def get_memory_indicators(month_prefix):
    if not current_user_id():
        return jsonify({'error': 'Unauthorized'}), 401

    conn = database.get_db()
    rows = conn.execute('''
        SELECT entry_date FROM daily_records 
        WHERE user_id = ? AND entry_date LIKE ? 
        AND ((journal_entry IS NOT NULL AND journal_entry != '') 
             OR (mood IS NOT NULL AND mood != '') 
             OR (song_title IS NOT NULL AND song_title != ''))
    ''', (current_user_id(), f"{month_prefix}%")).fetchall()
    
    task_rows = conn.execute('''
        SELECT DISTINCT task_date FROM tasks
        WHERE user_id = ? AND task_date LIKE ?
    ''', (current_user_id(), f"{month_prefix}%")).fetchall()
    conn.close()

    active_dates = set([r['entry_date'] for r in rows] + [t['task_date'] for t in task_rows])
    return jsonify({'active_dates': list(active_dates)})

@app.route('/api/memory/<date>')
def get_memory(date):
    if not current_user_id():
        return jsonify({'error': 'Unauthorized'}), 401

    conn = database.get_db()
    record = conn.execute('SELECT * FROM daily_records WHERE user_id = ? AND entry_date = ?', (current_user_id(), date)).fetchone()
    tasks = conn.execute('SELECT title, is_completed FROM tasks WHERE user_id = ? AND task_date = ?', (current_user_id(), date)).fetchall()
    conn.close()

    if not record and not tasks:
        return jsonify({'found': False})

    return jsonify({
        'found': True,
        'date': date,
        'mood': record['mood'] if record else None,
        'song_title': record['song_title'] if record else None,
        'song_artist': record['song_artist'] if record else None,
        'journal': record['journal_entry'] if record else None,
        'study_hours': record['study_hours'] if record else 0,
        'sleep_hours': record['sleep_hours'] if record else 0,
        'spent': record['money_spent'] if record else 0,
        'tasks': [{'title': t['title'], 'done': bool(t['is_completed'])} for t in tasks]
    })

@app.route('/api/memory/<date>/note', methods=['POST'])
def save_memory_note(date):
    if not current_user_id():
        return jsonify({'error': 'Unauthorized'}), 401

    data = request.get_json() or {}
    note = data.get('note', '').strip()

    conn = database.get_db()
    conn.execute('''
        INSERT INTO daily_records (user_id, entry_date, journal_entry)
        VALUES (?, ?, ?)
        ON CONFLICT(user_id, entry_date) DO UPDATE SET
            journal_entry = excluded.journal_entry
    ''', (current_user_id(), date, note))
    conn.commit()
    conn.close()
    return jsonify({'status': 'success'})

# --- My Space ---
@app.route('/myspace')
def myspace():
    if not current_user_id():
        return redirect(url_for('login'))

    conn = database.get_db()
    about = conn.execute('SELECT * FROM about_me WHERE user_id = ?', (current_user_id(),)).fetchone()
    bucket_items = conn.execute("SELECT * FROM life_items WHERE user_id = ? AND category = 'bucket_list' ORDER BY id DESC", (current_user_id(),)).fetchall()
    journals = conn.execute("SELECT entry_date, mood, journal_entry FROM daily_records WHERE user_id = ? AND journal_entry IS NOT NULL AND journal_entry != '' ORDER BY entry_date DESC", (current_user_id(),)).fetchall()
    conn.close()
    return render_template('myspace.html', about=about, bucket_items=bucket_items, journals=journals)

@app.route('/update-about-me', methods=['POST'])
def update_about_me():
    if not current_user_id():
        return redirect(url_for('login'))

    conn = database.get_db()
    conn.execute('''
        INSERT INTO about_me (
            user_id, full_name, birthday, fav_color, fav_song, 
            things_i_love, things_i_dislike, personality, values_text, 
            current_era, what_makes_me_happy
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            full_name = excluded.full_name,
            birthday = excluded.birthday,
            fav_color = excluded.fav_color,
            fav_song = excluded.fav_song,
            things_i_love = excluded.things_i_love,
            things_i_dislike = excluded.things_i_dislike,
            personality = excluded.personality,
            values_text = excluded.values_text,
            current_era = excluded.current_era,
            what_makes_me_happy = excluded.what_makes_me_happy
    ''', (
        current_user_id(),
        request.form.get('full_name'),
        request.form.get('birthday'),
        request.form.get('fav_color'),
        request.form.get('fav_song'),
        request.form.get('things_i_love'),
        request.form.get('things_i_dislike'),
        request.form.get('personality'),
        request.form.get('values_text'),
        request.form.get('current_era'),
        request.form.get('what_makes_me_happy')
    ))
    conn.commit()
    conn.close()
    return redirect(url_for('myspace'))

@app.route('/add-bucket-item', methods=['POST'])
def add_bucket_item():
    if not current_user_id():
        return redirect(url_for('login'))

    title = request.form.get('title', '').strip()
    tag = request.form.get('tag', 'Personal 💗')

    if title:
        conn = database.get_db()
        conn.execute("INSERT INTO life_items (user_id, category, title, subtitle) VALUES (?, 'bucket_list', ?, ?)", (current_user_id(), title, tag))
        conn.commit()
        conn.close()

    return redirect(url_for('myspace'))

@app.route('/toggle-bucket/<int:item_id>', methods=['POST'])
def toggle_bucket(item_id):
    if not current_user_id():
        return jsonify({'error': 'Unauthorized'}), 401

    conn = database.get_db()
    conn.execute('UPDATE life_items SET progress = 100 - progress WHERE id = ? AND user_id = ?', (item_id, current_user_id()))
    conn.commit()
    conn.close()
    return jsonify({'status': 'success'})

@app.route('/delete-bucket-item/<int:item_id>', methods=['POST'])
def delete_bucket_item(item_id):
    if not current_user_id():
        return jsonify({'error': 'Unauthorized'}), 401

    conn = database.get_db()
    conn.execute('DELETE FROM life_items WHERE id = ? AND user_id = ? AND category = "bucket_list"', (item_id, current_user_id()))
    conn.commit()
    conn.close()
    return jsonify({'status': 'success'})

# --- Tracker & Analytics ---
@app.route('/tracker')
def tracker():
    if not current_user_id():
        return redirect(url_for('login'))

    today_str = datetime.today().strftime('%Y-%m-%d')
    current_month_prefix = today_str[:7]
    conn = database.get_db()

    default_habits = ['💧 Drink Water', '🧘‍♀️ 30m Movement', '📖 Reading', '🧴 Skincare Routine', '📚 Focus Study']
    for h in default_habits:
        conn.execute(
            'INSERT OR IGNORE INTO habits (user_id, entry_date, habit_name, is_done) VALUES (?, ?, ?, 0)',
            (current_user_id(), today_str, h)
        )
    conn.commit()

    habits = conn.execute('SELECT * FROM habits WHERE user_id = ? AND entry_date = ?', (current_user_id(), today_str)).fetchall()
    today_record = conn.execute('SELECT * FROM daily_records WHERE user_id = ? AND entry_date = ?', (current_user_id(), today_str)).fetchone()
    expenses = conn.execute('SELECT * FROM expenses WHERE user_id = ? AND entry_date LIKE ? ORDER BY id DESC', (current_user_id(), f"{current_month_prefix}%")).fetchall()
    total_spent = sum([e['amount'] for e in expenses])

    month_records = conn.execute(
        'SELECT study_hours, sleep_hours FROM daily_records WHERE user_id = ? AND entry_date LIKE ?',
        (current_user_id(), f"{current_month_prefix}%")
    ).fetchall()

    total_study = sum([r['study_hours'] or 0 for r in month_records])
    sleep_days = [r['sleep_hours'] for r in month_records if r['sleep_hours'] and r['sleep_hours'] > 0]
    avg_sleep = (sum(sleep_days) / len(sleep_days)) if sleep_days else 0

    top_cat_row = conn.execute('''
        SELECT category, SUM(amount) as cat_total 
        FROM expenses 
        WHERE user_id = ? AND entry_date LIKE ? 
        GROUP BY category 
        ORDER BY cat_total DESC LIMIT 1
    ''', (current_user_id(), f"{current_month_prefix}%")).fetchone()

    top_category = f"{top_cat_row['category']} (₹{top_cat_row['cat_total']:.0f})" if top_cat_row else "None yet"

    conn.close()
    return render_template(
        'tracker.html', 
        habits=habits, 
        record=today_record, 
        expenses=expenses, 
        total_spent=total_spent, 
        today=today_str,
        total_study=total_study,
        avg_sleep=avg_sleep,
        top_category=top_category
    )

@app.route('/toggle-habit/<int:habit_id>', methods=['POST'])
def toggle_habit(habit_id):
    if not current_user_id():
        return jsonify({'error': 'Unauthorized'}), 401

    conn = database.get_db()
    conn.execute('UPDATE habits SET is_done = 1 - is_done WHERE id = ? AND user_id = ?', (habit_id, current_user_id()))
    conn.commit()
    conn.close()
    return jsonify({'status': 'success'})

@app.route('/update-study-sleep', methods=['POST'])
def update_study_sleep():
    if not current_user_id():
        return redirect(url_for('login'))

    today_str = datetime.today().strftime('%Y-%m-%d')
    study_hours = float(request.form.get('study_hours', 0) or 0)
    sleep_hours = float(request.form.get('sleep_hours', 0) or 0)
    sleep_quality = request.form.get('sleep_quality', 'Peaceful ☁️')

    conn = database.get_db()
    conn.execute('''
        INSERT INTO daily_records (user_id, entry_date, study_hours, sleep_hours, sleep_quality)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(user_id, entry_date) DO UPDATE SET
            study_hours = excluded.study_hours,
            sleep_hours = excluded.sleep_hours,
            sleep_quality = excluded.sleep_quality
    ''', (current_user_id(), today_str, study_hours, sleep_hours, sleep_quality))
    conn.commit()
    conn.close()

    return redirect(url_for('tracker'))

@app.route('/add-expense', methods=['POST'])
def add_expense():
    if not current_user_id():
        return redirect(url_for('login'))

    today_str = datetime.today().strftime('%Y-%m-%d')
    title = request.form.get('title', '').strip()
    category = request.form.get('category', 'Other ✨')
    amount = float(request.form.get('amount', 0) or 0)

    if title and amount > 0:
        conn = database.get_db()
        conn.execute(
            'INSERT INTO expenses (user_id, entry_date, title, category, amount) VALUES (?, ?, ?, ?, ?)',
            (current_user_id(), today_str, title, category, amount)
        )
        conn.commit()

        day_total = conn.execute(
            'SELECT SUM(amount) as total FROM expenses WHERE user_id = ? AND entry_date = ?',
            (current_user_id(), today_str)
        ).fetchone()['total'] or 0

        conn.execute('''
            INSERT INTO daily_records (user_id, entry_date, money_spent)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id, entry_date) DO UPDATE SET
                money_spent = excluded.money_spent
        ''', (current_user_id(), today_str, day_total))
        conn.commit()
        conn.close()

    return redirect(url_for('tracker'))

@app.route('/delete-expense/<int:expense_id>', methods=['POST'])
def delete_expense(expense_id):
    if not current_user_id():
        return jsonify({'error': 'Unauthorized'}), 401

    conn = database.get_db()
    conn.execute('DELETE FROM expenses WHERE id = ? AND user_id = ?', (expense_id, current_user_id()))
    conn.commit()
    conn.close()
    return jsonify({'status': 'success'})

# --- Aesthetics Routes ---
@app.route('/aesthetics')
def aesthetics():
    if not current_user_id():
        return redirect(url_for('login'))

    conn = database.get_db()
    vision_items = conn.execute("SELECT * FROM life_items WHERE user_id = ? AND category = 'vision' ORDER BY id DESC", (current_user_id(),)).fetchall()
    places = conn.execute("SELECT * FROM life_items WHERE user_id = ? AND category = 'places' ORDER BY id DESC", (current_user_id(),)).fetchall()
    wishlist = conn.execute("SELECT * FROM life_items WHERE user_id = ? AND category = 'wishlist' ORDER BY id DESC", (current_user_id(),)).fetchall()
    skills = conn.execute("SELECT * FROM life_items WHERE user_id = ? AND category = 'skills' ORDER BY id DESC", (current_user_id(),)).fetchall()
    conn.close()

    return render_template('aesthetics.html', vision_items=vision_items, places=places, wishlist=wishlist, skills=skills)

@app.route('/add-aesthetic-item', methods=['POST'])
def add_aesthetic_item():
    if not current_user_id():
        return redirect(url_for('login'))

    category = request.form.get('category')
    title = request.form.get('title', '').strip()
    subtitle = request.form.get('subtitle', '').strip()
    image_path = ''

    if category == 'wishlist':
        try:
            total_price = float(subtitle) if subtitle else 0
            saved_amt = float(request.form.get('saved_amount', 0) or 0)
            progress = int((saved_amt / total_price) * 100) if total_price > 0 else 0
            progress = max(0, min(100, progress))
            extra_meta = str(saved_amt)
        except ValueError:
            progress = 0
            extra_meta = '0'

        product_link = request.form.get('product_link', '').strip()
        if product_link:
            image_path = product_link
    else:
        progress = int(request.form.get('progress', 0) or 0)
        extra_meta = None

    if 'image_file' in request.files:
        file = request.files['image_file']
        if file and file.filename != '' and allowed_image(file.filename):
            ext = file.filename.rsplit('.', 1)[1].lower()
            timestamp = int(datetime.now().timestamp())
            clean_name = f"vision_{current_user_id()}_{timestamp}.{ext}"
            save_path = os.path.join(app.config['UPLOAD_FOLDER'], clean_name)
            file.save(save_path)
            image_path = f"/static/uploads/{clean_name}"

    if title and category:
        conn = database.get_db()
        conn.execute('''
            INSERT INTO life_items (user_id, category, title, subtitle, progress, image_path, extra_meta)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (current_user_id(), category, title, subtitle, progress, image_path, extra_meta))
        conn.commit()
        conn.close()

    return redirect(url_for('aesthetics'))

@app.route('/delete-vision-item/<int:item_id>', methods=['POST'])
def delete_vision_item(item_id):
    if not current_user_id():
        return jsonify({'error': 'Unauthorized'}), 401

    conn = database.get_db()
    item = conn.execute('SELECT image_path FROM life_items WHERE id = ? AND user_id = ? AND category = "vision"', (item_id, current_user_id())).fetchone()
    if item and item['image_path'] and item['image_path'].startswith('/static/uploads/'):
        rel_path = item['image_path'].lstrip('/')
        if os.path.exists(rel_path):
            try:
                os.remove(rel_path)
            except OSError:
                pass

    conn.execute('DELETE FROM life_items WHERE id = ? AND user_id = ?', (item_id, current_user_id()))
    conn.commit()
    conn.close()
    return jsonify({'status': 'success'})

@app.route('/update-wishlist-money/<int:item_id>', methods=['POST'])
def update_wishlist_money(item_id):
    if not current_user_id():
        return jsonify({'error': 'Unauthorized'}), 401

    data = request.get_json() or {}
    saved_amt = float(data.get('saved_amount', 0))

    conn = database.get_db()
    item = conn.execute('SELECT subtitle FROM life_items WHERE id = ? AND user_id = ?', (item_id, current_user_id())).fetchone()
    if item:
        try:
            total_price = float(item['subtitle'])
            progress = int((saved_amt / total_price) * 100) if total_price > 0 else 0
            progress = max(0, min(100, progress))
        except ValueError:
            progress = 0

        conn.execute('UPDATE life_items SET progress = ?, extra_meta = ? WHERE id = ? AND user_id = ?', (progress, str(saved_amt), item_id, current_user_id()))
        conn.commit()

    conn.close()
    return jsonify({'status': 'success'})

@app.route('/update-skill-progress/<int:skill_id>', methods=['POST'])
def update_skill_progress(skill_id):
    if not current_user_id():
        return jsonify({'error': 'Unauthorized'}), 401

    data = request.get_json() or {}
    progress = int(data.get('progress', 0))

    conn = database.get_db()
    conn.execute('UPDATE life_items SET progress = ? WHERE id = ? AND user_id = ?', (progress, skill_id, current_user_id()))
    conn.commit()
    conn.close()
    return jsonify({'status': 'success'})

# --- One-Click Markdown Vault Export ---
@app.route('/export-backup')
def export_backup():
    if not current_user_id():
        return redirect(url_for('login'))

    conn = database.get_db()
    user = conn.execute('SELECT * FROM users WHERE id = ?', (current_user_id(),)).fetchone()
    about = conn.execute('SELECT * FROM about_me WHERE user_id = ?', (current_user_id(),)).fetchone()
    journals = conn.execute('SELECT * FROM daily_records WHERE user_id = ? ORDER BY entry_date DESC', (current_user_id(),)).fetchall()
    buckets = conn.execute("SELECT * FROM life_items WHERE user_id = ? AND category = 'bucket_list'", (current_user_id(),)).fetchall()
    conn.close()

    md = []
    md.append(f"# HER. — Sanctuary Memory Vault Backup")
    md.append(f"Exported for: **{user['display_name']}** on {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
    md.append("## 👩🏻 About Me & Living Identity")
    if about:
        md.append(f"- **Current Era**: {about['current_era']}")
        md.append(f"- **Birthday**: {about['birthday']}")
        md.append(f"- **Favorite Color**: {about['fav_color']}")
        md.append(f"- **Favorite Song**: {about['fav_song']}")
        md.append(f"- **Personality**: {about['personality']}")
        md.append(f"- **Values**: {about['values_text']}")
        md.append(f"- **Things I Love**: {about['things_i_love']}")
        md.append(f"- **Things I Dislike**: {about['things_i_dislike']}")
        md.append(f"- **What Makes Me Happy**: {about['what_makes_me_happy']}\n")

    md.append("## 🧳 Bucket List Dreams")
    for b in buckets:
        status = "[x]" if b['progress'] == 100 else "[ ]"
        md.append(f"- {status} {b['title']} ({b['subtitle']})")
    md.append("")

    md.append("## 📝 Journal Entries & Reflections")
    for j in journals:
        if j['journal_entry'] or j['mood'] or j['song_title']:
            md.append(f"### 📅 {j['entry_date']}")
            if j['mood']:
                md.append(f"- **Mood**: {j['mood']}")
            if j['song_title']:
                md.append(f"- **Soundtrack**: {j['song_title']} — {j['song_artist']}")
            if j['journal_entry']:
                md.append(f"\n{j['journal_entry']}\n")
            md.append("---")

    content = "\n".join(md)
    return Response(
        content,
        mimetype="text/markdown",
        headers={"Content-Disposition": f"attachment;filename=her_memory_backup_{datetime.now().strftime('%Y%m%d')}.md"}
    )

if __name__ == '__main__':
    app.run(debug=True)