from flask import Flask, render_template, request, redirect, url_for, session, send_file, jsonify
import sqlite3
import pandas as pd
from io import BytesIO
from datetime import datetime
from flask_cors import CORS

app = Flask(__name__)
CORS(app)
app.secret_key = "securekey"

# ---------------- Database Setup ----------------
def init_db():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS voters (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT,
                    gender TEXT,
                    fingerprint_id INTEGER,
                    voted INTEGER DEFAULT 0,
                    timestamp TEXT
                )''')
    conn.commit()
    conn.close()

init_db()

# ---------------- Admin Login ----------------
@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if username == 'admin' and password == 'admin123':
            session['admin'] = True
            return redirect(url_for('admin'))
        else:
            return render_template('login.html', error="Invalid credentials")
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('admin', None)
    return redirect(url_for('login'))

# ---------------- Admin Panel ----------------
@app.route('/admin')
def admin():
    if 'admin' not in session:
        return redirect(url_for('login'))

    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("SELECT * FROM voters")
    voters = c.fetchall()
    conn.close()
    return render_template('admin.html', voters=voters)

@app.route('/add_voter', methods=['POST'])
def add_voter():
    name = request.form['name']
    gender = request.form['gender']
    fingerprint_id = request.form['fingerprint_id']

    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("INSERT INTO voters (name, gender, fingerprint_id, voted) VALUES (?, ?, ?, 0)",
              (name, gender, fingerprint_id))
    conn.commit()
    conn.close()
    return redirect(url_for('admin'))

@app.route('/delete_voter/<int:id>')
def delete_voter(id):
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("DELETE FROM voters WHERE id=?", (id,))
    conn.commit()
    conn.close()
    return redirect(url_for('admin'))

@app.route('/reset_votes')
def reset_votes():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("UPDATE voters SET voted=0, timestamp=NULL")
    conn.commit()
    conn.close()
    return redirect(url_for('admin'))

@app.route('/download_csv')
def download_csv():
    conn = sqlite3.connect('database.db')
    df = pd.read_sql_query("SELECT * FROM voters", conn)
    conn.close()
    csv_data = df.to_csv(index=False)
    return send_file(BytesIO(csv_data.encode()), mimetype='text/csv',
                     as_attachment=True, download_name='voters.csv')

@app.route('/download_excel')
def download_excel():
    conn = sqlite3.connect('database.db')
    df = pd.read_sql_query("SELECT * FROM voters", conn)
    conn.close()
    output = BytesIO()
    writer = pd.ExcelWriter(output, engine='xlsxwriter')
    df.to_excel(writer, index=False, sheet_name='Voters')
    writer.close()
    output.seek(0)
    return send_file(output, download_name='voters.xlsx', as_attachment=True)

# ---------------- Dashboard ----------------
@app.route('/dashboard')
def dashboard():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM voters")
    total = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM voters WHERE gender='Male'")
    male = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM voters WHERE gender='Female'")
    female = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM voters WHERE voted=1")
    voted = c.fetchone()[0]

    percent = round((voted / total * 100), 2) if total > 0 else 0
    conn.close()

    return render_template('dashboard.html', total=total, male=male, female=female, voted=voted, percent=percent)

# ---------------- ESP32 APIs ----------------
@app.route('/verify', methods=['POST'])
def verify_voter():
    data = request.get_json()
    finger_id = data.get('finger_id')
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("SELECT name, voted FROM voters WHERE fingerprint_id=?", (finger_id,))
    voter = c.fetchone()
    conn.close()

    if voter:
        name, voted = voter
        if voted == 0:
            return jsonify({'status': 'allowed', 'name': name})
        else:
            return jsonify({'status': 'voted'})
    else:
        return jsonify({'status': 'not_found'})

@app.route('/vote', methods=['POST'])
def cast_vote():
    data = request.get_json()
    finger_id = data.get('finger_id')
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("UPDATE voters SET voted=1, timestamp=? WHERE fingerprint_id=?", (datetime.now().isoformat(), finger_id))
    conn.commit()
    conn.close()
    return jsonify({'status': 'success', 'message': 'Vote recorded successfully'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
