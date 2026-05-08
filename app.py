from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import psycopg2
import psycopg2.extras
from datetime import datetime
from functools import wraps

app = Flask(__name__)
app.secret_key = 'school-secret-key-change-me'

ADMIN_PASSWORD = 'school2025'

DATABASE_URL = "postgresql://school:tIfprhxTB3xOuAuLcnHNGlKRsX1kpe41@dpg-d7v3e2btqb8s73fn38s0-a/school_db_1ytf"

SLOTS = {
    "14 мая": ["14:00-14:15", "14:15-14:30", "14:30-14:45", "14:45-15:00", "15:00-15:15", "15:15-15:30", "15:30-15:45"],
    "15 мая": ["16:00-16:15", "16:15-16:30", "16:30-16:45", "16:45-17:00", "17:00-17:15", "17:15-17:30", "17:30-17:45", "17:45-18:00", "18:00-18:15", "18:15-18:30"],
    "19 мая": ["18:30-18:45", "18:45-19:00", "19:00-19:15", "19:15-19:30", "19:30-19:45", "19:45-20:00", "20:00-20:15", "20:15-20:30"],
    "20 мая": ["18:30-18:45", "18:45-19:00", "19:00-19:15", "19:15-19:30"],
    "22 мая": ["17:00-17:15", "17:15-17:30", "17:30-17:45", "17:45-18:00", "18:00-18:15", "18:15-18:30", "18:30-18:45", "18:45-19:00"]
}

def get_db():
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    return conn

def init_db():
    conn = get_db()
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS appointments (
            id SERIAL PRIMARY KEY,
            date TEXT NOT NULL,
            time TEXT NOT NULL,
            fio TEXT NOT NULL,
            school TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(date, time)
        )
    ''')
    cur.close()
    conn.close()

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('admin_logged_in'):
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
def index():
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute('SELECT date, time, fio, school FROM appointments')
    appointments = cur.fetchall()
    cur.close()
    conn.close()

    occupied = {}
    for a in appointments:
        if a['date'] not in occupied:
            occupied[a['date']] = {}
        parts = a['fio'].split()
        if parts:
            short_fio = parts[0][0] + '***'
        else:
            short_fio = '***'
        occupied[a['date']][a['time']] = {'fio': short_fio, 'school': a['school']}

    return render_template('index.html', slots=SLOTS, occupied=occupied)

@app.route('/book', methods=['POST'])
def book():
    date = request.form.get('date')
    time = request.form.get('time')
    fio = request.form.get('fio', '').strip()
    school = request.form.get('school', '').strip()

    if not date or not time or not fio or not school:
        return jsonify({'success': False, 'message': 'Все поля обязательны'})

    if date not in SLOTS or time not in SLOTS[date]:
        return jsonify({'success': False, 'message': 'Неверный слот'})

    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute(
            'INSERT INTO appointments (date, time, fio, school) VALUES (%s, %s, %s, %s)',
            (date, time, fio, school)
        )
        cur.close()
        conn.close()
        return jsonify({'success': True, 'message': 'Вы записаны!'})
    except psycopg2.errors.UniqueViolation:
        conn.rollback()
        cur.close()
        conn.close()
        return jsonify({'success': False, 'message': 'Это время уже занято'})

@app.route('/cancel', methods=['POST'])
def cancel():
    fio = request.form.get('fio', '').strip()

    if not fio:
        return jsonify({'success': False, 'message': 'Введите ФИО'})

    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute('SELECT * FROM appointments WHERE fio = %s', (fio,))
    appointment = cur.fetchone()

    if not appointment:
        cur.close()
        conn.close()
        return jsonify({'success': False, 'message': 'Запись не найдена'})

    cur.execute('DELETE FROM appointments WHERE id = %s', (appointment['id'],))
    cur.close()
    conn.close()

    return jsonify({
        'success': True,
        'message': f"Запись на {appointment['date']} ({appointment['time']}) отменена"
    })

@app.route('/my-booking', methods=['POST'])
def my_booking():
    fio = request.form.get('fio', '').strip()
    if not fio:
        return jsonify({'success': False, 'message': 'Введите ФИО'})

    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute('SELECT date, time, school FROM appointments WHERE fio = %s', (fio,))
    appointment = cur.fetchone()
    cur.close()
    conn.close()

    if appointment:
        return jsonify({
            'success': True,
            'date': appointment['date'],
            'time': appointment['time'],
            'school': appointment['school']
        })
    return jsonify({'success': False, 'message': 'Запись не найдена'})

@app.route('/admin', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        if request.form.get('password') == ADMIN_PASSWORD:
            session['admin_logged_in'] = True
            return redirect(url_for('admin_panel'))
        return render_template('admin_login.html', error='Неверный пароль')
    return render_template('admin_login.html')

@app.route('/admin/panel')
@login_required
def admin_panel():
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute('SELECT * FROM appointments ORDER BY date, time')
    appointments = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('admin_panel.html', appointments=appointments)

@app.route('/admin/delete/<int:id>', methods=['POST'])
@login_required
def admin_delete(id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute('DELETE FROM appointments WHERE id = %s', (id,))
    cur.close()
    conn.close()
    return redirect(url_for('admin_panel'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

init_db()

if __name__ == '__main__':
    app.run(debug=True)
