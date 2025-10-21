from flask import Flask, render_template, request, session, redirect, url_for, jsonify
from flask_sock import Sock
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
from datetime import datetime
import json
import random
import string
import os
import threading

app = Flask(__name__)
app.secret_key = 'super_cyber_secret'
sock = Sock(app)

DB = 'competition.db'
ws_clients = []
db_lock = threading.Lock()

# Database setup
def init_db():
    if os.path.exists(DB):
        os.remove(DB)
    
    conn = sqlite3.connect('competition.db', timeout=30)
    c = conn.cursor()
    c.execute("PRAGMA journal_mode=WAL")

    # Таблица участников
    c.execute('''CREATE TABLE IF NOT EXISTS participants
                 (id INTEGER PRIMARY KEY, code TEXT, name TEXT)''')

    # Таблица жюри
    c.execute('''CREATE TABLE IF NOT EXISTS jury
                 (id INTEGER PRIMARY KEY, name TEXT UNIQUE, code TEXT UNIQUE)''')

    # Таблица пользователей жюри (логин/пароль + активное имя + is_admin)
    c.execute('''CREATE TABLE IF NOT EXISTS jury_users
                 (id INTEGER PRIMARY KEY,
                  jury_id INTEGER,
                  login TEXT,
                  password_hash TEXT,
                  password_plain TEXT,
                  active_name TEXT,
                  is_admin BOOLEAN DEFAULT 0)''')

    # Добавляем колонку is_admin если её нет
    try:
        c.execute("ALTER TABLE jury_users ADD COLUMN is_admin BOOLEAN DEFAULT 0")
    except sqlite3.OperationalError:
        pass

    # Добавляем колонку password_plain если её нет
    try:
        c.execute("ALTER TABLE jury_users ADD COLUMN password_plain TEXT")
    except sqlite3.OperationalError:
        pass

    # Таблица оценок
    c.execute('''CREATE TABLE IF NOT EXISTS scores
                 (id INTEGER PRIMARY KEY,
                  participant_id INTEGER,
                  jury_id INTEGER,
                  contest1 REAL DEFAULT 0,
                  contest2 REAL DEFAULT 0,
                  contest3 REAL DEFAULT 0,
                  finalized BOOLEAN DEFAULT 0,
                  UNIQUE(participant_id, jury_id))''')

    # Добавляем колонку finalized если её нет
    try:
        c.execute("ALTER TABLE scores ADD COLUMN finalized BOOLEAN DEFAULT 0")
    except sqlite3.OperationalError:
        pass

    # Таблица чата
    c.execute('''CREATE TABLE IF NOT EXISTS chat_messages
                 (id INTEGER PRIMARY KEY, jury_id INTEGER, message TEXT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')

    # Пример участников
    for i in range(1, 6):
        code = f'K{i}'
        name = f'Каламбет {i}'
        c.execute("INSERT INTO participants (id, code, name) VALUES (?, ?, ?)", (i, code, name))

    # Один мастер-логин для всех жюри
    login = 'rksi'
    password_hash = generate_password_hash('zzz')
    if not c.execute("SELECT * FROM jury_users WHERE login=?", (login,)).fetchone():
        c.execute("INSERT INTO jury_users (login, password_hash) VALUES (?, ?)", (login, password_hash))

    # Админ отдельно
    admin_login = 'admin'
    admin_password_hash = generate_password_hash('admin123')
    if not c.execute("SELECT * FROM jury_users WHERE login=?", (admin_login,)).fetchone():
        c.execute("INSERT INTO jury_users (login, password_hash, is_admin) VALUES (?, ?, 1)", (admin_login, admin_password_hash))

    conn.commit()
    conn.close()

def get_db_connection():
    conn = sqlite3.connect(DB, timeout=30)
    conn.row_factory = sqlite3.Row
    return conn

# --- HELPERS ---
def validate_login(login, password):
    conn = get_db_connection()
    user = conn.execute("SELECT * FROM jury_users WHERE login=?", (login,)).fetchone()
    if user and check_password_hash(user['password_hash'], password):
        conn.close()
        return user
    conn.close()
    return None

def get_jury_list():
    """Возвращает список всех членов жюри"""
    conn = get_db_connection()
    jury_list = conn.execute("SELECT id, name, code FROM jury ORDER BY name").fetchall()
    conn.close()
    return jury_list

def select_jury_profile(jury_id):
    """Привязывает выбранный профиль жюри к сессии"""
    session['selected_jury_id'] = jury_id
    return True

def create_new_jury_profile(name):
    """Создает новый профиль жюри с уникальным кодом"""
    with db_lock:
        conn = get_db_connection()
        c = conn.cursor()
        if c.execute("SELECT * FROM jury WHERE name=?", (name,)).fetchone():
            conn.close()
            return False
        
        # Генерируем уникальный код
        while True:
            code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
            if not c.execute("SELECT * FROM jury WHERE code=?", (code,)).fetchone():
                break
        
        c.execute("INSERT INTO jury (name, code) VALUES (?, ?)", (name, code))
        jury_id = c.lastrowid
        conn.commit()
        conn.close()
    return jury_id

def get_selected_jury_info():
    """Получает информацию о выбранном жюри"""
    if 'selected_jury_id' not in session:
        return None
    conn = get_db_connection()
    result = conn.execute("SELECT id, name, code FROM jury WHERE id=?", (session['selected_jury_id'],)).fetchone()
    conn.close()
    return result

def get_scores():
    conn = get_db_connection()
    participants = conn.execute("SELECT * FROM participants ORDER BY id").fetchall()
    jury_members = conn.execute("SELECT * FROM jury ORDER BY id").fetchall()
    scores = {}
    totals = {}
    for p in participants:
        scores[p['id']] = {}
        total_sum = 0
        for j in jury_members:
            s = conn.execute("SELECT contest1,contest2,contest3,finalized FROM scores WHERE participant_id=? AND jury_id=?", (p['id'], j['id'])).fetchone()
            if s:
                scores[p['id']][j['id']] = {'contest1': s['contest1'], 'contest2': s['contest2'], 'contest3': s['contest3'], 'finalized': s['finalized']}
                total_sum += s['contest1'] + s['contest2'] + s['contest3']
            else:
                scores[p['id']][j['id']] = {'contest1': 0, 'contest2': 0, 'contest3': 0, 'finalized': False}
        totals[p['id']] = total_sum
    conn.close()
    return participants, jury_members, scores, totals

def get_leaderboard(totals, participants):
    leaderboard = []
    for p in participants:
        leaderboard.append({'name': p['name'], 'total': totals[p['id']]})
    leaderboard.sort(key=lambda x: x['total'], reverse=True)
    return leaderboard

def is_admin(user_id):
    conn = get_db_connection()
    user = conn.execute("SELECT is_admin FROM jury_users WHERE id=?", (user_id,)).fetchone()
    conn.close()
    return user and user['is_admin'] == 1

def generate_random_string(length=5):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/viewer')
def viewer():
    participants, jury_list, scores, totals = get_scores()
    return render_template('viewer.html', participants=participants, jury_list=jury_list, scores=scores)

@app.route('/leaderboard')
def leaderboard():
    _, _, _, totals = get_scores()
    participants = get_db_connection().execute("SELECT * FROM participants ORDER BY id").fetchall()
    leaderboard = get_leaderboard(totals, participants)
    return render_template('leaderboard.html', leaderboard=leaderboard)

@app.route('/jury_login', methods=['GET', 'POST'])
def jury_login():
    if request.method == 'POST':
        login = request.form['login']
        password = request.form['password']
        user = validate_login(login, password)
        if user and not user['is_admin']:
            session['user_id'] = user['id']
            return redirect(url_for('jury_select'))
        return render_template('jury_login.html', error="Неверный логин или пароль")
    return render_template('jury_login.html')

@app.route('/jury_select', methods=['GET', 'POST'])
def jury_select():
    if 'user_id' not in session:
        return redirect(url_for('jury_login'))
    
    jury_list = get_jury_list()
    
    if request.method == 'POST':
        jury_id = request.form['jury_id']
        if jury_id == 'new':
            return redirect(url_for('jury_name'))
        else:
            jury_id = int(jury_id)
            if select_jury_profile(jury_id):
                return redirect(url_for('jury_panel'))
        return render_template('jury_select.html', jury_list=jury_list, error="Ошибка выбора")
    
    return render_template('jury_select.html', jury_list=jury_list)

@app.route('/jury_name', methods=['GET', 'POST'])
def jury_name():
    if 'user_id' not in session:
        return redirect(url_for('jury_login'))
    
    if request.method == 'POST':
        name = request.form['name'].strip()
        if not name:
            return render_template('jury_name.html', error="Имя не может быть пустым")
        jury_id = create_new_jury_profile(name)
        if jury_id:
            if select_jury_profile(jury_id):
                return redirect(url_for('jury_panel'))
        return render_template('jury_name.html', error="Имя уже занято")
    
    return render_template('jury_name.html')

@app.route('/jury_panel')
def jury_panel():
    if 'user_id' not in session:
        return redirect(url_for('jury_login'))
    if 'selected_jury_id' not in session:
        return redirect(url_for('jury_select'))
        
    jury_info = get_selected_jury_info()
    if not jury_info:
        return redirect(url_for('jury_select'))
        
    participants, jury_list, scores, totals = get_scores()
    leaderboard = get_leaderboard(totals, participants)
    return render_template('jury_panel.html', participants=participants, jury_list=jury_list, scores=scores, totals=totals, leaderboard=leaderboard, jury={'id': jury_info[0], 'name': jury_info[1], 'code': jury_info[2]})

@app.route('/update_score', methods=['POST'])
def update_score():
    data = request.json
    part_id = data['participant_id']
    jury_id = data['jury_id']
    contest = data['contest']
    value = float(data['score'])
    
    if value < 0 or value > 5:
        return jsonify(success=False, error="Балл должен быть от 0 до 5")
    
    with db_lock:
        conn = get_db_connection()
        c = conn.cursor()
        existing = c.execute("SELECT id, finalized FROM scores WHERE participant_id=? AND jury_id=?", (part_id, jury_id)).fetchone()
        if existing:
            if existing['finalized']:
                conn.close()
                return jsonify(success=False, error="Оценки уже финализированы")
            c.execute(f"UPDATE scores SET {contest}=? WHERE participant_id=? AND jury_id=?", (value, part_id, jury_id))
        else:
            c.execute(f"INSERT INTO scores (participant_id, jury_id, {contest}) VALUES (?, ?, ?)", (part_id, jury_id, value))
        conn.commit()
        conn.close()
    broadcast_scores()
    return jsonify(success=True)

@app.route('/finalize_scores', methods=['POST'])
def finalize_scores():
    data = request.json
    part_id = data['participant_id']
    jury_id = data['jury_id']
    with db_lock:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("UPDATE scores SET finalized=1 WHERE participant_id=? AND jury_id=?", (part_id, jury_id))
        conn.commit()
        conn.close()
    broadcast_scores()
    return jsonify(success=True)

# --- ADMIN ROUTES ---
@app.route('/admin_login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        login = request.form['login']
        password = request.form['password']
        user = validate_login(login, password)
        if user and user['is_admin']:
            session['user_id'] = user['id']
            return redirect(url_for('admin_panel'))
        return render_template('admin_login.html', error="Неверный логин или пароль")
    return render_template('admin_login.html')

@app.route('/admin_panel')
def admin_panel():
    # Если не авторизован - редирект на admin_login
    if 'user_id' not in session or not is_admin(session['user_id']):
        return redirect(url_for('admin_login'))
    
    conn = get_db_connection()
    # УЧАСТНИКИ - правильный запрос
    participants = conn.execute("SELECT id, code, name FROM participants ORDER BY id").fetchall()
    
    # ЖЮРИ - УПРОЩЕННЫЙ запрос БЕЗ logins/passwords
    jury_list = conn.execute("""
        SELECT id, code, name 
        FROM jury 
        ORDER BY id
    """).fetchall()
    
    conn.close()
    return render_template('admin_panel.html', participants=participants, jury_list=jury_list)

@app.route('/add_participant', methods=['POST'])
def add_participant():
    if 'user_id' not in session or not is_admin(session['user_id']):
        return jsonify(success=False), 403
    
    code = request.form['code']
    name = request.form['name']
    with db_lock:
        conn = get_db_connection()
        c = conn.cursor()
        max_id = c.execute("SELECT MAX(id) FROM participants").fetchone()[0] or 0
        new_id = max_id + 1
        c.execute("INSERT INTO participants (id, code, name) VALUES (?, ?, ?)", (new_id, code, name))
        conn.commit()
        conn.close()
    broadcast_scores()
    return redirect(url_for('admin_panel'))

@app.route('/delete_participant/<int:id>')
def delete_participant(id):
    if 'user_id' not in session or not is_admin(session['user_id']):
        return jsonify(success=False), 403
    
    with db_lock:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("DELETE FROM scores WHERE participant_id=?", (id,))
        c.execute("DELETE FROM participants WHERE id=?", (id,))
        conn.commit()
        conn.close()
    broadcast_scores()
    return redirect(url_for('admin_panel'))

@app.route('/reset_scores/<int:id>')
def reset_scores(id):
    if 'user_id' not in session or not is_admin(session['user_id']):
        return jsonify(success=False), 403
    
    with db_lock:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("UPDATE scores SET contest1=0, contest2=0, contest3=0, finalized=0 WHERE participant_id=?", (id,))
        conn.commit()
        conn.close()
    broadcast_scores()
    return redirect(url_for('admin_panel'))

@app.route('/add_jury', methods=['POST'])
def add_jury():
    if 'user_id' not in session or not is_admin(session['user_id']):
        return jsonify(success=False), 403
    
    name = request.form['name']
    with db_lock:
        conn = get_db_connection()
        c = conn.cursor()
        if c.execute("SELECT * FROM jury WHERE name=?", (name,)).fetchone():
            conn.close()
            return redirect(url_for('admin_panel'))  # Имя занято
        
        # Генерируем уникальный код
        while True:
            code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
            if not c.execute("SELECT * FROM jury WHERE code=?", (code,)).fetchone():
                break
        
        c.execute("INSERT INTO jury (name, code) VALUES (?, ?)", (name, code))
        conn.commit()
        conn.close()
    broadcast_scores()
    return redirect(url_for('admin_panel'))

@app.route('/delete_jury/<int:id>')
def delete_jury(id):
    if 'user_id' not in session or not is_admin(session['user_id']):
        return jsonify(success=False), 403
    
    with db_lock:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("DELETE FROM scores WHERE jury_id=?", (id,))
        c.execute("DELETE FROM jury WHERE id=?", (id,))
        conn.commit()
        conn.close()
    broadcast_scores()
    return redirect(url_for('admin_panel'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))

# --- WEBSOCKET ---
@sock.route('/ws')
def ws(ws):
    ws_clients.append(ws)
    try:
        while True:
            try:
                message = ws.receive(timeout=0.1)
            except Exception as e:
                if "timeout" not in str(e).lower():
                    break
            except:
                pass
    finally:
        if ws in ws_clients:
            ws_clients.remove(ws)

# --- BROADCAST FUNCTIONS ---
def broadcast_scores():
    participants, jury_list, scores, totals = get_scores()
    leaderboard = get_leaderboard(totals, participants)
    jury_data = [{'id': j['id'], 'name': j['name']} for j in jury_list]
    data = {'type': 'score_update', 'scores': scores, 'totals': totals, 'leaderboard': leaderboard, 'jury_list': jury_data}
    for client in ws_clients:
        try:
            client.send(json.dumps(data))
        except:
            pass

if __name__ == '__main__':
    init_db()
    app.run(debug=True, threaded=True)