import sqlite3
from functools import wraps
from datetime import datetime, date
from flask import Flask, render_template, request, redirect, url_for, flash, session, g
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config['DATABASE'] = 'tasks.db'
app.config['SECRET_KEY'] = 'super-secret-key-change-me'


def get_db_connection():
    conn = sqlite3.connect(app.config['DATABASE'])
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db_connection()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            points INTEGER DEFAULT 0
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            subject TEXT NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            deadline TEXT NOT NULL,
            priority TEXT CHECK(priority IN ('Low','Medium','High')) NOT NULL,
            status TEXT CHECK(status IN ('pending','completed')) NOT NULL DEFAULT 'pending',
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS subjects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            UNIQUE(user_id, name),
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    ''')
    conn.commit()
    conn.close()


@app.before_first_request
def initialize_db():
    init_db()


@app.before_request
def load_logged_in_user():
    user_id = session.get('user_id')
    if user_id is None:
        g.user = None
    else:
        conn = get_db_connection()
        g.user = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
        conn.close()


def login_required(view):
    @wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None:
            flash('Please login first', 'danger')
            return redirect(url_for('login'))
        return view(**kwargs)
    return wrapped_view


@app.route('/')
def welcome():
    if g.user:
        return redirect(url_for('dashboard'))
    return render_template('welcome.html')


@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username'].strip()
        email = request.form['email'].strip()
        password = request.form['password'].strip()

        if not username or not email or not password:
            flash('All fields are required', 'danger')
            return redirect(url_for('signup'))

        conn = get_db_connection()
        existing = conn.execute('SELECT id FROM users WHERE username = ? OR email = ?', (username, email)).fetchone()
        if existing:
            flash('Username or email already exists', 'danger')
            conn.close()
            return redirect(url_for('signup'))

        hashed_password = generate_password_hash(password)
        conn.execute('INSERT INTO users (username, email, password) VALUES (?, ?, ?)', (username, email, hashed_password))
        conn.commit()
        conn.close()

        flash('Sign up successful, please log in', 'success')
        return redirect(url_for('login'))

    return render_template('signup.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password'].strip()

        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE username = ? OR email = ?', (username, username)).fetchone()
        conn.close()

        if user is None or not check_password_hash(user['password'], password):
            flash('Invalid credentials', 'danger')
            return redirect(url_for('login'))

        session.clear()
        session['user_id'] = user['id']
        flash(f'Welcome back, {user["username"]}!', 'success')
        return redirect(url_for('dashboard'))

    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully', 'info')
    return redirect(url_for('welcome'))


@app.route('/dashboard')
@login_required
def dashboard():
    conn = get_db_connection()
    tasks = conn.execute('SELECT * FROM tasks WHERE user_id = ? ORDER BY deadline', (g.user['id'],)).fetchall()
    conn.close()

    total_tasks = len(tasks)
    completed_tasks = sum(1 for t in tasks if t['status'] == 'completed')
    pending_tasks = sum(1 for t in tasks if t['status'] == 'pending')
    progress = int((completed_tasks / total_tasks) * 100) if total_tasks > 0 else 0

    now = datetime.now()
    today_date = now.date()

    todays_tasks = []
    upcoming = []
    overdue = []

    for t in tasks:
        if t['status'] != 'pending':
            continue

        try:
            deadline_dt = datetime.fromisoformat(t['deadline'])
        except ValueError:
            # fallback in case no seconds
            deadline_dt = datetime.strptime(t['deadline'], '%Y-%m-%d %H:%M')

        if deadline_dt.date() == today_date:
            todays_tasks.append(t)
        elif deadline_dt > now:
            upcoming.append(t)
        else:
            overdue.append(t)

    for t in tasks:
        if t['status'] == 'pending':
            try:
                deadline_dt = datetime.fromisoformat(t['deadline'])
            except ValueError:
                deadline_dt = datetime.strptime(t['deadline'], '%Y-%m-%d %H:%M')
            t['overdue'] = (t['status'] == 'pending' and deadline_dt < now)


    return render_template('dashboard.html', total_tasks=total_tasks, completed_tasks=completed_tasks,
                           pending_tasks=pending_tasks, progress=progress, todays_tasks=todays_tasks,
                           upcoming=upcoming, overdue=overdue)


@app.route('/add-task', methods=['GET', 'POST'])
@login_required
def add_task():
    conn = get_db_connection()
    subjects = [r['name'] for r in conn.execute('SELECT name FROM subjects WHERE user_id = ? ORDER BY name', (g.user['id'],)).fetchall()]
    conn.close()

    if request.method == 'POST':
        subject = request.form['subject'].strip()
        title = request.form['title'].strip()
        description = request.form['description'].strip()
        deadline = request.form['deadline'].strip()
        priority = request.form['priority']

        if not subject or not title or not deadline or not priority:
            flash('All required fields must be filled', 'danger')
            return redirect(url_for('add_task'))

        try:
            deadline_dt = datetime.fromisoformat(deadline)
        except ValueError:
            flash('Invalid date/time format', 'danger')
            return redirect(url_for('add_task'))

        conn = get_db_connection()
        conn.execute('INSERT OR IGNORE INTO subjects (user_id, name) VALUES (?, ?)', (g.user['id'], subject))
        conn.execute('INSERT INTO tasks (user_id, subject, title, description, deadline, priority, status) VALUES (?, ?, ?, ?, ?, ?, ?)',
                     (g.user['id'], subject, title, description, deadline_dt.isoformat(' '), priority, 'pending'))
        conn.commit()
        conn.close()

        flash('Task added successfully', 'success')
        return redirect(url_for('tasks'))

    return render_template('add_task.html', subjects=subjects)


@app.route('/tasks')
@login_required
def tasks():
    priority_filter = request.args.get('priority', 'all')
    conn = get_db_connection()
    if priority_filter in ('Low', 'Medium', 'High'):
        task_rows = conn.execute('SELECT * FROM tasks WHERE user_id = ? AND priority = ? ORDER BY deadline', (g.user['id'], priority_filter)).fetchall()
    else:
        task_rows = conn.execute('SELECT * FROM tasks WHERE user_id = ? ORDER BY deadline', (g.user['id'],)).fetchall()
    conn.close()

    now = datetime.now()
    for row in task_rows:
        row['overdue'] = row['status'] == 'pending' and datetime.fromisoformat(row['deadline']) < now

    return render_template('tasks.html', tasks=task_rows, priority_filter=priority_filter)


@app.route('/schedule')
@login_required
def schedule():
    conn = get_db_connection()
    tasks = conn.execute('SELECT * FROM tasks WHERE user_id = ? ORDER BY deadline', (g.user['id'],)).fetchall()
    conn.close()

    now = datetime.now()
    today = []
    upcoming = []
    overdue = []

    for t in tasks:
        t_deadline = datetime.fromisoformat(t['deadline'])
        if t['status'] == 'completed':
            continue
        if t_deadline.date() == now.date():
            today.append(t)
        elif t_deadline > now:
            upcoming.append(t)
        else:
            overdue.append(t)

    return render_template('schedule.html', today=today, upcoming=upcoming, overdue=overdue)


@app.route('/subjects', methods=['GET', 'POST'])
@login_required
def subjects():
    if request.method == 'POST':
        subject_name = request.form['subject_name'].strip()
        if subject_name:
            conn = get_db_connection()
            conn.execute('INSERT OR IGNORE INTO subjects (user_id, name) VALUES (?, ?)', (g.user['id'], subject_name))
            conn.commit()
            conn.close()
            flash('Subject added', 'success')
            return redirect(url_for('subjects'))

    conn = get_db_connection()
    subjects = conn.execute('SELECT * FROM subjects WHERE user_id = ? ORDER BY name', (g.user['id'],)).fetchall()
    tasks_by_subject = {}
    for s in subjects:
        rows = conn.execute('SELECT * FROM tasks WHERE user_id = ? AND subject = ? ORDER BY deadline', (g.user['id'], s['name'])).fetchall()
        tasks_by_subject[s['name']] = rows
    conn.close()

    return render_template('subjects.html', subjects=subjects, tasks_by_subject=tasks_by_subject)


@app.route('/complete/<int:task_id>')
@login_required
def complete(task_id):
    conn = get_db_connection()
    task = conn.execute('SELECT * FROM tasks WHERE id = ? AND user_id = ?', (task_id, g.user['id'])).fetchone()
    if task and task['status'] == 'pending':
        conn.execute('UPDATE tasks SET status = ? WHERE id = ?', ('completed', task_id))
        conn.execute('UPDATE users SET points = points + 10 WHERE id = ?', (g.user['id'],))
        conn.commit()
        flash('Task marked complete +10 points', 'success')
    else:
        flash('Task not found or already completed', 'danger')
    conn.close()
    return redirect(url_for('tasks'))


@app.route('/delete/<int:task_id>')
@login_required
def delete(task_id):
    conn = get_db_connection()
    task = conn.execute('SELECT * FROM tasks WHERE id = ? AND user_id = ?', (task_id, g.user['id'])).fetchone()
    if task:
        if task['status'] == 'completed':
            conn.execute('UPDATE users SET points = MAX(points - 10, 0) WHERE id = ?', (g.user['id'],))
        conn.execute('DELETE FROM tasks WHERE id = ?', (task_id,))
        conn.commit()
        flash('Task deleted', 'info')
    else:
        flash('Task not found', 'danger')
    conn.close()
    return redirect(url_for('tasks'))


@app.route('/edit/<int:task_id>', methods=['GET', 'POST'])
@login_required
def edit(task_id):
    conn = get_db_connection()
    task = conn.execute('SELECT * FROM tasks WHERE id = ? AND user_id = ?', (task_id, g.user['id'])).fetchone()
    if not task:
        conn.close()
        flash('Task not found', 'danger')
        return redirect(url_for('tasks'))

    if request.method == 'POST':
        subject = request.form['subject'].strip()
        title = request.form['title'].strip()
        description = request.form['description'].strip()
        deadline = request.form['deadline'].strip()
        priority = request.form['priority']

        if not subject or not title or not deadline or not priority:
            flash('All fields are required', 'danger')
            return redirect(url_for('edit', task_id=task_id))

        try:
            datetime.fromisoformat(deadline)
        except ValueError:
            flash('Invalid date/time', 'danger')
            return redirect(url_for('edit', task_id=task_id))

        conn.execute('UPDATE tasks SET subject=?, title=?, description=?, deadline=?, priority=? WHERE id = ?',
                     (subject, title, description, deadline, priority, task_id))
        conn.commit()
        conn.close()

        flash('Task updated successfully', 'success')
        return redirect(url_for('tasks'))

    conn.close()
    return render_template('edit_task.html', task=task)


if __name__ == '__main__':
    app.run(debug=True)


import os

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)