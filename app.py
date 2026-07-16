from flask import Flask, render_template, request, redirect, url_for, send_file, session
from functools import wraps
from PIL import Image
from datetime import datetime
import textwrap
from docxtpl import DocxTemplate, InlineImage
from docx.shared import Mm
from werkzeug.utils import secure_filename
import sqlite3
import os
import io

app = Flask(__name__)
# The secret key is required to encrypt the session cookies
app.secret_key = 'jmc_hr_super_secret_key_2026' 
DB_NAME = "employees.db"

# Setup Upload Folder
UPLOAD_FOLDER = "static/uploads"
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Database Setup
def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS employees (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT, address TEXT, birthdate TEXT, 
            sss TEXT, philhealth TEXT, hdmf TEXT, tin TEXT, 
            position TEXT, id_no TEXT, date_hired TEXT, 
            department TEXT, em_name TEXT, em_contact TEXT,
            photo TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# --- SECURITY LOCK DECORATOR ---
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# --- AUTHENTICATION ROUTES ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        # Hardcoded Credentials
        if username == 'HR' and password == '@JMC_HR_2026':
            session['logged_in'] = True
            return redirect(url_for('index'))
        else:
            error = "Invalid username or password."
            
    return render_template('login.html', error=error)

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('login'))

# --- PROTECTED APP ROUTES ---
@app.route('/')
@login_required
def index():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    employees = conn.execute('SELECT * FROM employees ORDER BY id DESC').fetchall()
    conn.close()
    return render_template('index.html', employees=employees)

@app.route('/add', methods=['POST'])
@login_required
def add_employee():
    photo_file = request.files.get('photo')
    photo_filename = ""
    if photo_file and photo_file.filename != '':
        photo_filename = secure_filename(photo_file.filename)
        save_path = os.path.join(app.config['UPLOAD_FOLDER'], photo_filename)
        
        img = Image.open(photo_file)
        width, height = img.size
        
        if width != height:
            min_dim = min(width, height)
            left = (width - min_dim) / 2
            top = (height - min_dim) / 2
            right = (width + min_dim) / 2
            bottom = (height + min_dim) / 2
            img = img.crop((left, top, right, bottom))
            
        img.save(save_path)

    data = (
        request.form.get('name', ''), request.form.get('address', ''), request.form.get('birthdate', ''),
        request.form.get('sss', ''), request.form.get('philhealth', ''), request.form.get('hdmf', ''),
        request.form.get('tin', ''), request.form.get('position', ''), request.form.get('id_no', ''),
        request.form.get('date_hired', ''), request.form.get('department', ''), 
        request.form.get('em_name', ''), request.form.get('em_contact', ''),
        photo_filename
    )
    
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''
        INSERT INTO employees (name, address, birthdate, sss, philhealth, hdmf, tin, position, id_no, date_hired, department, em_name, em_contact, photo)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', data)
    conn.commit()
    conn.close()
    return redirect(url_for('index'))

@app.route('/generate', methods=['POST'])
@login_required
def generate_ids():
    selected_ids = request.form.getlist('employee_ids')
    template_type = request.form.get('template_type')
    
    if not selected_ids or len(selected_ids) > 4:
        return "Please select between 1 and 4 employees.", 400

    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    placeholders = ','.join('?' for _ in selected_ids)
    employees = conn.execute(f'SELECT * FROM employees WHERE id IN ({placeholders})', selected_ids).fetchall()
    conn.close()

    template_path = f"static/{template_type}_template.docx"
    doc = DocxTemplate(template_path)

    context = {}
    for i, emp in enumerate(employees):
        idx = i + 1 
        for key in emp.keys():
            if key in ['birthdate', 'date_hired'] and emp[key]:
                try:
                    parsed_date = datetime.strptime(emp[key], '%Y-%m-%d')
                    month_map = {
                        "JANUARY": "JAN", "FEBRUARY": "FEB", "MARCH": "MAR", "APRIL": "APR",
                        "MAY": "MAY", "JUNE": "JUNE", "JULY": "JULY", "AUGUST": "AUG",
                        "SEPTEMBER": "SEPT", "OCTOBER": "OCT", "NOVEMBER": "NOV", "DECEMBER": "DEC"
                    }
                    full_month = parsed_date.strftime('%B').upper()
                    short_month = month_map.get(full_month, full_month[:3])
                    day_year = parsed_date.strftime(' %d, %Y')
                    context[f"{key}_{idx}"] = f"{short_month}{day_year}"
                except ValueError:
                    context[f"{key}_{idx}"] = emp[key].upper()
            else:
                context[f"{key}_{idx}"] = emp[key]
            
        full_addr = emp['address']
        if full_addr:
            wrapped = textwrap.wrap(full_addr, width=20)
            context[f"address_{idx}"] = wrapped[0] if len(wrapped) > 0 else ""
            context[f"address2_{idx}"] = " ".join(wrapped[1:]) if len(wrapped) > 1 else ""
        else:
            context[f"address_{idx}"] = ""
            context[f"address2_{idx}"] = ""
        
        if emp['photo'] and os.path.exists(os.path.join(app.config['UPLOAD_FOLDER'], emp['photo'])):
            img_path = os.path.join(app.config['UPLOAD_FOLDER'], emp['photo'])
            context[f"photo_{idx}"] = InlineImage(doc, image_descriptor=img_path, width=Mm(22), height=Mm(22))
        else:
            context[f"photo_{idx}"] = ""

    for i in range(len(employees), 4):
        idx = i + 1
        for key in employees[0].keys():
            context[f"{key}_{idx}"] = ""
        context[f"photo_{idx}"] = ""
        context[f"address2_{idx}"] = ""

    doc.render(context)
    file_stream = io.BytesIO()
    doc.save(file_stream)
    file_stream.seek(0)

    return send_file(
        file_stream, 
        as_attachment=True, 
        download_name=f"Generated_{template_type.capitalize()}_IDs.docx"
    )

@app.route('/delete/<int:id>', methods=['GET', 'POST'])
@login_required
def delete_employee(id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('DELETE FROM employees WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    return redirect(url_for('index'))

@app.route('/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_employee(id):
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    
    if request.method == 'POST':
        photo_file = request.files.get('photo')
        photo_filename = request.form.get('existing_photo', '')
        
        if photo_file and photo_file.filename != '':
            photo_filename = secure_filename(photo_file.filename)
            save_path = os.path.join(app.config['UPLOAD_FOLDER'], photo_filename)

            img = Image.open(photo_file)
            width, height = img.size

            if width != height:
                min_dim = min(width, height)
                left = (width - min_dim) / 2
                top = (height - min_dim) / 2
                right = (width + min_dim) / 2
                bottom = (height + min_dim) / 2
                img = img.crop((left, top, right, bottom))
                
            img.save(save_path)

        data = (
            request.form.get('name', ''), request.form.get('address', ''), request.form.get('birthdate', ''),
            request.form.get('sss', ''), request.form.get('philhealth', ''), request.form.get('hdmf', ''),
            request.form.get('tin', ''), request.form.get('position', ''), request.form.get('id_no', ''),
            request.form.get('date_hired', ''), request.form.get('department', ''), 
            request.form.get('em_name', ''), request.form.get('em_contact', ''),
            photo_filename,
            id
        )
        c = conn.cursor()
        c.execute('''
            UPDATE employees SET 
            name=?, address=?, birthdate=?, sss=?, philhealth=?, hdmf=?, tin=?, position=?, id_no=?, date_hired=?, department=?, em_name=?, em_contact=?, photo=?
            WHERE id=?
        ''', data)
        conn.commit()
        conn.close()
        return redirect(url_for('index'))
    
    employee = conn.execute('SELECT * FROM employees WHERE id = ?', (id,)).fetchone()
    conn.close()
    return render_template('edit.html', emp=employee)

if __name__ == '__main__':
    app.run(debug=True)