from flask import Flask, render_template, request, session, redirect, url_for, jsonify
from flask_sock import Sock
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
from datetime import datetime
import threading
import json

app = Flask(__name__)
app.secret_key = 'super_cyber_secret'
sock = Sock(app)

DB = 'competition.db'
ws_clients = []
# Database setup
def init_db():
    conn = sqlite3.connect('competition.db')
    c = conn.cursor()

    # Таблица участников
    c.execute('''CREATE TABLE IF NOT EXISTS participants
                 (id INTEGER PRIMARY KEY, code TEXT, name TEXT)''')

    # Таблица жюри
    c.execute('''CREATE TABLE IF NOT EXISTS jury
                 (id INTEGER PRIMARY KEY, name TEXT UNIQUE)''')

    # Таблица пользователей жюри (логин/пароль + активное имя)
    c.execute('''CREATE TABLE IF NOT EXISTS jury_users
                 (id INTEGER PRIMARY KEY,
                  jury_id INTEGER,
                  login TEXT UNIQUE,
                  password_hash TEXT,
                  active_name TEXT UNIQUE)''')

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
        # Колонка уже существует
        pass

    # Таблица чата
    c.execute('''CREATE TABLE IF NOT EXISTS chat_messages
                 (id INTEGER PRIMARY KEY, jury_id INTEGER, message TEXT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')

    # Пример участников
    participants = [
        ('K1', 'Каламбет 1'),
        ('K2', 'Каламбет 2'),
        ('K3', 'Каламбет 3'),
        ('K4', 'Каламбет 4'),
        ('K5', 'Каламбет 5')
    ]
    for code, name in participants:
        c.execute("INSERT OR IGNORE INTO participants (code, name) VALUES (?, ?)", (code, name))

    # Пользователь жюри с логином/паролем
    login = 'RKSI'
    password_hash = generate_password_hash('SIGMABOY')
    if not c.execute("SELECT * FROM jury_users WHERE login=?", (login,)).fetchone():
        c.execute("INSERT INTO jury_users (login, password_hash) VALUES (?, ?)", (login, password_hash))

    conn.commit()
    conn.close()

def get_db_connection():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

# --- HELPERS ---
def validate_login(login,password):
    conn = get_db_connection()
    user = conn.execute("SELECT * FROM jury_users WHERE login=?",(login,)).fetchone()
    conn.close()
    if user and check_password_hash(user['password_hash'],password):
        return user['id']
    return None

def set_active_name(jury_user_id, name):
    """Установить уникальное имя жюри для текущего пользователя и создать запись в таблице jury"""
    conn = sqlite3.connect('competition.db')
    c = conn.cursor()
    
    # Проверяем, что имя ещё не занято в таблице jury
    if c.execute("SELECT * FROM jury WHERE name=?", (name,)).fetchone():
        conn.close()
        return False
    
    # Создаем запись в таблице jury
    c.execute("INSERT INTO jury (name) VALUES (?)", (name,))
    jury_id = c.lastrowid
    
    # Обновляем jury_users с активным именем и привязываем к jury_id
    c.execute("UPDATE jury_users SET active_name=?, jury_id=? WHERE id=?", (name, jury_id, jury_user_id))
    
    conn.commit()
    conn.close()
    return True

def get_jury_id_by_user_id(jury_user_id):
    """Получить jury_id по jury_user_id"""
    conn = sqlite3.connect('competition.db')
    c = conn.cursor()
    result = c.execute("SELECT jury_id FROM jury_users WHERE id=?", (jury_user_id,)).fetchone()
    conn.close()
    return result[0] if result else None

def get_jury_info_by_user_id(jury_user_id):
    """Получить информацию о жюри по jury_user_id"""
    conn = sqlite3.connect('competition.db')
    c = conn.cursor()
    result = c.execute("""
        SELECT j.id, j.name 
        FROM jury j
        JOIN jury_users ju ON j.id = ju.jury_id
        WHERE ju.id = ?
    """, (jury_user_id,)).fetchone()
    conn.close()
    return result if result else None

def get_scores():
    conn = get_db_connection()
    participants = conn.execute("SELECT * FROM participants ORDER BY id LIMIT 5").fetchall()
    jury_members = conn.execute("SELECT * FROM jury ORDER BY id").fetchall()
    scores = {}
    totals = {}
    for p in participants:
        scores[p['id']]={}
        total_sum=0
        for j in jury_members:
            s = conn.execute("SELECT contest1,contest2,contest3,finalized FROM scores WHERE participant_id=? AND jury_id=?",(p['id'],j['id'])).fetchone()
            if s:
                scores[p['id']][j['id']] = {'contest1': s['contest1'], 'contest2': s['contest2'], 'contest3': s['contest3'], 'finalized': s['finalized']}
                total_sum += s['contest1']+s['contest2']+s['contest3']
            else:
                # No score record exists yet, initialize with zeros
                scores[p['id']][j['id']] = {'contest1': 0, 'contest2': 0, 'contest3': 0, 'finalized': False}
                total_sum += 0
        totals[p['id']] = total_sum
    conn.close()
    return participants,jury_members,scores,totals

def get_leaderboard(totals,participants):
    leaderboard = []
    for p in participants:
        leaderboard.append({'name':p['name'],'total':totals[p['id']]})
    leaderboard.sort(key=lambda x: x['total'],reverse=True)
    return leaderboard


# --- ROUTES ---
@app.route('/')
def home():
    return render_template('home.html')

@app.route('/viewer')
def viewer():
    participants,jury,scores,totals = get_scores()
    leaderboard = get_leaderboard(totals,participants)
    return render_template('viewer.html',participants=participants,jury_list=jury,scores=scores,totals=totals,leaderboard=leaderboard)

@app.route('/leaderboard')
def leaderboard():
    participants,jury,scores,totals = get_scores()
    leaderboard = get_leaderboard(totals,participants)
    return render_template('leaderboard.html', leaderboard=leaderboard)

@app.route('/jury_login', methods=['GET','POST'])
def jury_login():
    if request.method=='POST':
        login = request.form.get('login','')
        password = request.form.get('password','')
        jury_user_id = validate_login(login,password)
        if jury_user_id:
            session['jury_user_id']=jury_user_id
            return redirect(url_for('jury_name'))
        else:
            return "Неверный логин/пароль",401
    return render_template('jury_login.html')

@app.route('/jury_name', methods=['GET', 'POST'])
def jury_name():
    if 'jury_user_id' not in session:
        return redirect(url_for('jury_login'))

    jury_user_id = session['jury_user_id']

    if request.method == 'POST':
        name = request.form['name'].strip()
        if set_active_name(jury_user_id, name):
            session['jury_name'] = name
            return redirect(url_for('jury_index'))
        else:
            return render_template('jury_name.html', error="Имя уже занято, выберите другое.")

    return render_template('jury_name.html')

@app.route('/jury_index')
def jury_index():
    if 'jury_user_id' not in session:
        return redirect(url_for('jury_login'))
    
    # Получаем информацию о текущем жюри
    jury_info = get_jury_info_by_user_id(session['jury_user_id'])
    if not jury_info:
        return redirect(url_for('jury_name'))
    
    participants,jury_list,scores,totals = get_scores()
    leaderboard = get_leaderboard(totals,participants)
    return render_template('jury_panel.html',participants=participants,jury_list=jury_list,scores=scores,totals=totals,leaderboard=leaderboard,jury={'id':jury_info[0],'name':jury_info[1]})

@app.route('/update_score',methods=['POST'])
def update_score():
    data = request.json
    part_id = data['participant_id']
    jury_id = data['jury_id']
    contest = data['contest']
    value = float(data['score'])
    
    # Валидация: балл должен быть от 0 до 5
    if value < 0 or value > 5:
        return jsonify(success=False, error="Балл должен быть от 0 до 5")
    
    conn = get_db_connection()
    # Check if score record exists, if not create one
    existing = conn.execute("SELECT id, finalized FROM scores WHERE participant_id=? AND jury_id=?",(part_id,jury_id)).fetchone()
    if existing:
        # Проверяем, не финализированы ли уже оценки
        if existing['finalized']:
            conn.close()
            return jsonify(success=False, error="Оценки уже финализированы")
        conn.execute(f"UPDATE scores SET {contest}=? WHERE participant_id=? AND jury_id=?",(value,part_id,jury_id))
    else:
        conn.execute(f"INSERT INTO scores (participant_id, jury_id, {contest}) VALUES (?, ?, ?)",(part_id,jury_id,value))
    conn.commit()
    conn.close()
    broadcast_scores()
    return jsonify(success=True)

@app.route('/finalize_scores',methods=['POST'])
def finalize_scores():
    data = request.json
    part_id = data['participant_id']
    jury_id = data['jury_id']
    conn = get_db_connection()
    # Финализируем оценки для этого участника от этого жюри
    conn.execute("UPDATE scores SET finalized=1 WHERE participant_id=? AND jury_id=?",(part_id,jury_id))
    conn.commit()
    conn.close()
    broadcast_scores()
    return jsonify(success=True)

# --- WEBSOCKET ---
@sock.route('/ws')
def ws(ws):
    ws_clients.append(ws)
    try:
        while True:
            try:
                message = ws.receive(timeout=0.1)
                # WebSocket теперь только для получения обновлений, без чата
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
    participants,jury_list,scores,totals = get_scores()
    leaderboard = get_leaderboard(totals,participants)
    # Преобразуем jury_list в формат, который можно сериализовать в JSON
    jury_data = [{'id': j['id'], 'name': j['name']} for j in jury_list]
    data = {'type':'score_update','scores':scores,'totals':totals,'leaderboard':leaderboard,'jury_list':jury_data}
    for client in ws_clients:
        try: client.send(json.dumps(data))
        except: pass


if __name__=='__main__':
    init_db()  # Initialize database tables
    app.run(debug=True,threaded=True)