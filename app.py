from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import sqlite3
from datetime import datetime
from functools import wraps
import os

app = Flask(__name__)
app.secret_key = 'school-secret-key-change-me'

ADMIN_PASSWORD = 'school2025'

SLOTS = {
    "14 мая": ["14:00-14:15", "14:15-14:30", "14:30-14:45", "14:45-15:00", "15:00-15:15", "15:15-15:30", "15:30-15:45"],
    "15 мая": ["16:00-16:15", "16:15-16:30", "16:30-16:45", "16:45-17:00", "17:00-17:15", "17:15-17:30", "17:30-17:45", "17:45-18:00", "18:00-18:15", "18:15-18:30"],
    "19 мая": ["18:30-18:45", "18:45-19:00", "19:00-19:15", "19:15-19:30", "19:30-19:45", "19:45-20:00", "20:00-20:15", "20:15-20:30"],
    "20 мая": ["18:30-18:45", "18:45-19:00", "19:00-19:15", "19:15-19:30"],
    "22 мая": ["17:00-17:15", "17:15-17:30", "17:30-17:45", "17:45-18:00", "18:00-18:15", "18:15-18:30", "18:30-18:45", "18:45-19:00"]
}

DB_PATH = '/tmp/school.db'

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS appointments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            time TEXT NOT NULL,
            fio TEXT NOT NULL,
            school TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(date, time)
        )
    ''')
    conn.commit()
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
    appointments = conn.execute('SELECT date, time, fio, school FROM appointments').fetchall()
    conn.close()

    occupied = {}
    for a in appointments:
        if a['date'] not in occupied:
            occupied[a['date']] = {}
        # Скрываем ФИО: оставляем только первую букву фамилии + ***
        parts = a['fio'].split()
        if parts:
            short_fio = parts[0][0] + '***'
        else:
            short_fio = '***'
        occupied[a['date']][a['time']] = {'fio': short_fio, 'school': a['school']}

    return render_template('index.html', slots=SLOTS, occupied=occupied)
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
    try:
        conn.execute(
            'INSERT INTO appointments (date, time, fio, school) VALUES (?, ?, ?, ?)',
            (date, time, fio, school)
        )
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'message': 'Вы записаны!'})
    except sqlite3.IntegrityError:
        conn.close()
        return jsonify({'success': False, 'message': 'Это время уже занято'})

@app.route('/cancel', methods=['POST'])
def cancel():
    fio = request.form.get('fio', '').strip()

    if not fio:
        return jsonify({'success': False, 'message': 'Введите ФИО'})

    conn = get_db()
    appointment = conn.execute(
        'SELECT * FROM appointments WHERE fio = ?', (fio,)
    ).fetchone()

    if not appointment:
        conn.close()
        return jsonify({'success': False, 'message': 'Запись не найдена'})

    conn.execute('DELETE FROM appointments WHERE id = ?', (appointment['id'],))
    conn.commit()
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
    appointment = conn.execute(
        'SELECT date, time, school FROM appointments WHERE fio = ?', (fio,)
    ).fetchone()
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
    appointments = conn.execute(
        'SELECT * FROM appointments ORDER BY date, time'
    ).fetchall()
    conn.close()
    return render_template('admin_panel.html', appointments=appointments)

@app.route('/admin/delete/<int:id>', methods=['POST'])
@login_required
def admin_delete(id):
    conn = get_db()
    conn.execute('DELETE FROM appointments WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    return redirect(url_for('admin_panel'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

# Создаём таблицу при импорте
init_db()

if __name__ == '__main__':
    app.run(debug=True)
