from flask import Flask, render_template, request, redirect, url_for, jsonify, session, flash
from flask_mysqldb import MySQL
from werkzeug.security import generate_password_hash, check_password_hash
import qrcode, os, re
import random, smtplib, ssl, datetime
from email.mime.text import MIMEText

app = Flask(__name__)

import os

# Secret Key
app.secret_key = os.environ.get("SECRET_KEY", "smart-shopper-secret-key")

# ---------------- MySQL Configuration ----------------
app.config['MYSQL_HOST'] = os.environ.get('MYSQL_HOST')
app.config['MYSQL_USER'] = os.environ.get('MYSQL_USER')
app.config['MYSQL_PASSWORD'] = os.environ.get('MYSQL_PASSWORD')
app.config['MYSQL_DB'] = os.environ.get('MYSQL_DB')
app.config['MYSQL_PORT'] = int(os.environ.get('MYSQL_PORT', 3306))
app.config['MYSQL_CURSORCLASS'] = 'DictCursor'

mysql = MySQL(app)

# QR Code Folder
QR_FOLDER = os.path.join('static', 'qr')
os.makedirs(QR_FOLDER, exist_ok=True)

# ---------------- SMTP Configuration ----------------  
app.config['SMTP_SERVER'] = 'smtp-relay.brevo.com'
app.config['SMTP_PORT'] = 587
app.config['SMTP_EMAIL'] = os.environ.get('SMTP_EMAIL')
app.config['SMTP_PASSWORD'] = os.environ.get('SMTP_PASSWORD')

OTP_VALID_MINUTES = 10       


# =========================================================
# VALIDATION HELPERS
# =========================================================
NAME_RE = re.compile(r'^[A-Za-z][A-Za-z ]{1,49}$')                 # letters/spaces, 2-50 chars
EMAIL_RE = re.compile(r'^[\w\.\+\-]+@[\w\-]+\.[a-zA-Z]{2,}$')       # standard email format
MOBILE_RE = re.compile(r'^[6-9]\d{9}$')                            # 10-digit Indian mobile number
# Password: min 8 chars, at least 1 upper, 1 lower, 1 digit, 1 special char
PASSWORD_RE = re.compile(r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[^\w\s]).{8,}$')


def validate_name(name):
    return bool(name) and bool(NAME_RE.match(name.strip()))


def validate_email(email):
    return bool(email) and bool(EMAIL_RE.match(email.strip()))


def validate_mobile(mobile):
    return bool(mobile) and bool(MOBILE_RE.match(mobile.strip()))


def validate_password(password):
    return bool(password) and bool(PASSWORD_RE.match(password))


def validate_age(age):
    try:
        age = int(age)
        return 5 <= age <= 100
    except (TypeError, ValueError):
        return False


def email_already_used(cur, email):
    """Email must be unique across BOTH customers and admins."""
    cur.execute("SELECT id FROM customers WHERE email=%s", (email,))
    if cur.fetchone():
        return True
    cur.execute("SELECT id FROM admins WHERE email=%s", (email,))
    if cur.fetchone():
        return True
    return False


def login_required_role(role):
    return session.get('role') == role


def find_account_role_by_email(cur, email):
    """Checks BOTH customers and admins tables for this email.
    Returns 'customer', 'admin', or None."""
    cur.execute("SELECT id FROM customers WHERE email=%s", (email,))
    if cur.fetchone():
        return 'customer'
    cur.execute("SELECT id FROM admins WHERE email=%s", (email,))
    if cur.fetchone():
        return 'admin'
    return None


def generate_otp():
    return f"{random.randint(0, 999999):06d}"


def send_otp_email(to_email, otp):
    """Sends the OTP to the user's email via SMTP.
    Requires app.config['SMTP_EMAIL'] / ['SMTP_PASSWORD'] above to be set to a
    real sending account. Returns True on success, False on failure."""
    try:
        msg = MIMEText(
            f"Your Smart Shopper's Guide password reset OTP is: {otp}\n\n"
            f"This OTP is valid for {OTP_VALID_MINUTES} minutes. "
            f"If you did not request this, you can safely ignore this email."
        )
        msg['Subject'] = "Smart Shopper's Guide - Password Reset OTP"
        msg['From'] = app.config['SMTP_EMAIL']
        msg['To'] = to_email

        context = ssl.create_default_context()
        with smtplib.SMTP(app.config['SMTP_SERVER'], app.config['SMTP_PORT']) as server:
            server.starttls(context=context)
            server.login(app.config['SMTP_EMAIL'], app.config['SMTP_PASSWORD'])
            server.sendmail(app.config['SMTP_EMAIL'], to_email, msg.as_string())
        return True
    except Exception as e:
        print(f"[OTP EMAIL ERROR] {e}")
        return False


# =========================================================
# BASIC PAGES
# =========================================================
@app.route('/')
def index():
    return render_template('index.html')


@app.route('/login', methods=['GET', 'POST'])
def login_page():
    if request.method == 'GET':
        return render_template('login.html')

    email = request.form.get('email', '').strip()
    password = request.form.get('password', '')

    if not email or not password:
        flash("Please enter both email and password.", "error")
        return render_template('login.html')

    cur = mysql.connection.cursor()

    # 1) Check customers table first
    cur.execute("SELECT * FROM customers WHERE email=%s", (email,))
    user = cur.fetchone()
    if user and check_password_hash(user['password'], password):
        cur.close()
        session['user_id'] = user['id']
        session['role'] = 'customer'
        session['name'] = user['name']
        return redirect(url_for('dashboard_customer'))

    # 2) Check admins table
    cur.execute("SELECT * FROM admins WHERE email=%s", (email,))
    admin = cur.fetchone()
    cur.close()
    if admin and check_password_hash(admin['password'], password):
        session['user_id'] = admin['id']
        session['role'] = 'admin'
        session['name'] = admin['name']
        return redirect(url_for('dashboard_admin'))

    flash("Invalid email or password.", "error")
    return render_template('login.html')


@app.route('/register')
def register_page():
    return render_template('register.html')


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login_page'))


# =========================================================
# FORGOT PASSWORD (OTP-based reset, works for customers + admins)
# =========================================================
@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'GET':
        return render_template('forgot_password.html')

    email = request.form.get('email', '').strip()

    if not validate_email(email):
        flash("Please enter a valid email address.", "error")
        return render_template('forgot_password.html')

    cur = mysql.connection.cursor()
    role = find_account_role_by_email(cur, email)
    cur.close()

    if not role:
        flash("No account found with that email address.", "error")
        return render_template('forgot_password.html')

    otp = generate_otp()
    session['reset_email'] = email
    session['reset_role'] = role
    session['reset_otp'] = otp
    session['reset_otp_expires'] = (
        datetime.datetime.utcnow() + datetime.timedelta(minutes=OTP_VALID_MINUTES)
    ).isoformat()

    if not send_otp_email(email, otp):
        flash("Could not send the OTP email. Please check the SMTP settings in app.py.", "error")
        return render_template('forgot_password.html')

    flash(f"An OTP has been sent to {email}. It is valid for {OTP_VALID_MINUTES} minutes.", "success")
    return redirect(url_for('verify_otp'))


@app.route('/verify_otp', methods=['GET', 'POST'])
def verify_otp():
    if 'reset_email' not in session:
        flash("Please request a password reset OTP first.", "error")
        return redirect(url_for('forgot_password'))

    if request.method == 'GET':
        return render_template('verify_otp.html', email=session.get('reset_email'))

    entered_otp = request.form.get('otp', '').strip()
    new_password = request.form.get('new_password', '')
    confirm_password = request.form.get('confirm_password', '')

    expires_at = datetime.datetime.fromisoformat(session['reset_otp_expires'])
    if datetime.datetime.utcnow() > expires_at:
        session.pop('reset_email', None)
        session.pop('reset_role', None)
        session.pop('reset_otp', None)
        session.pop('reset_otp_expires', None)
        flash("This OTP has expired. Please request a new one.", "error")
        return redirect(url_for('forgot_password'))

    if not entered_otp or entered_otp != session.get('reset_otp'):
        flash("Incorrect OTP. Please try again.", "error")
        return render_template('verify_otp.html', email=session.get('reset_email'))

    if not validate_password(new_password):
        flash("Password must be 8+ characters with an uppercase letter, lowercase letter, number, and special character.", "error")
        return render_template('verify_otp.html', email=session.get('reset_email'))

    if new_password != confirm_password:
        flash("Passwords do not match.", "error")
        return render_template('verify_otp.html', email=session.get('reset_email'))

    email = session['reset_email']
    role = session['reset_role']
    hashed_pw = generate_password_hash(new_password)

    cur = mysql.connection.cursor()
    if role == 'customer':
        cur.execute("UPDATE customers SET password=%s WHERE email=%s", (hashed_pw, email))
    else:
        cur.execute("UPDATE admins SET password=%s WHERE email=%s", (hashed_pw, email))
    mysql.connection.commit()
    cur.close()

    session.pop('reset_email', None)
    session.pop('reset_role', None)
    session.pop('reset_otp', None)
    session.pop('reset_otp_expires', None)

    flash("Your password has been reset successfully. Please login.", "success")
    return redirect(url_for('login_page'))


@app.route('/resend_otp')
def resend_otp():
    if 'reset_email' not in session:
        flash("Please request a password reset OTP first.", "error")
        return redirect(url_for('forgot_password'))

    email = session['reset_email']
    otp = generate_otp()
    session['reset_otp'] = otp
    session['reset_otp_expires'] = (
        datetime.datetime.utcnow() + datetime.timedelta(minutes=OTP_VALID_MINUTES)
    ).isoformat()

    if send_otp_email(email, otp):
        flash(f"A new OTP has been sent to {email}.", "success")
    else:
        flash("Could not send the OTP email. Please check the SMTP settings in app.py.", "error")

    return redirect(url_for('verify_otp'))


# =========================================================
# REGISTER CUSTOMER
# =========================================================
@app.route('/register_customer', methods=['POST'])
def register_customer():
    name = request.form.get('name', '').strip()
    email = request.form.get('email', '').strip()
    mobile = request.form.get('mobile', '').strip()
    age = request.form.get('age', '').strip()
    password = request.form.get('password', '')

    errors = []
    if not validate_name(name):
        errors.append("Name must contain only letters/spaces (2-50 characters).")
    if not validate_email(email):
        errors.append("Please enter a valid email address.")
    if not validate_mobile(mobile):
        errors.append("Mobile number must be a valid 10-digit Indian number (starts with 6-9).")
    if not validate_age(age):
        errors.append("Age must be a number between 5 and 100.")
    if not validate_password(password):
        errors.append("Password must be 8+ characters with an uppercase letter, lowercase letter, number, and special character.")

    if errors:
        for e in errors:
            flash(e, "error")
        return redirect(url_for('register_page') + '?role=customer')

    cur = mysql.connection.cursor()
    if email_already_used(cur, email):
        cur.close()
        flash("This email is already registered. Please login instead.", "error")
        return redirect(url_for('register_page') + '?role=customer')

    hashed_pw = generate_password_hash(password)
    cur.execute("""INSERT INTO customers (name, email, mobile, age, password)
                   VALUES (%s, %s, %s, %s, %s)""",
                (name, email, mobile, age, hashed_pw))
    mysql.connection.commit()
    cur.close()

    flash("Registration successful! Please login.", "success")
    return redirect(url_for('login_page'))


# =========================================================
# REGISTER ADMIN + GENERATE QR
# =========================================================
@app.route('/register_admin', methods=['POST'])
def register_admin():
    name = request.form.get('name', '').strip()
    email = request.form.get('email', '').strip()
    password = request.form.get('password', '')
    mall_name = request.form.get('mall_name', '').strip()
    mall_location = request.form.get('mall_location', '').strip()
    map_url = request.form.get('map_url', '').strip()
    contact_no = request.form.get('contact_no', '').strip()
    registration_id = request.form.get('registration_id', '').strip()

    errors = []
    if not validate_name(name):
        errors.append("Name must contain only letters/spaces (2-50 characters).")
    if not validate_email(email):
        errors.append("Please enter a valid email address.")
    if not validate_password(password):
        errors.append("Password must be 8+ characters with an uppercase letter, lowercase letter, number, and special character.")
    if not mall_name:
        errors.append("Mall name is required.")
    if not mall_location:
        errors.append("Mall location is required.")
    if not validate_mobile(contact_no):
        errors.append("Mall contact number must be a valid 10-digit Indian number (starts with 6-9).")
    if not registration_id:
        errors.append("Mall registration ID is required.")

    if errors:
        for e in errors:
            flash(e, "error")
        return redirect(url_for('register_page') + '?role=admin')

    cur = mysql.connection.cursor()
    if email_already_used(cur, email):
        cur.close()
        flash("This email is already registered. Please login instead.", "error")
        return redirect(url_for('register_page') + '?role=admin')

    hashed_pw = generate_password_hash(password)
    cur.execute("""INSERT INTO admins
                   (name, email, password, mall_name, mall_location, map_url, contact_no, registration_id)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
                (name, email, hashed_pw, mall_name, mall_location, map_url, contact_no, registration_id))
    mysql.connection.commit()
    mall_id = cur.lastrowid

    # Generate QR Code for this mall (customer scans -> lands on login/mall page)
    mall_url = f"{request.host_url}mall/{mall_id}"
    qr_img = qrcode.make(mall_url)
    qr_path = os.path.join(QR_FOLDER, f"mall_qr_{mall_id}.png")
    qr_img.save(qr_path)

    cur.execute("UPDATE admins SET qr_code_path=%s WHERE id=%s", (qr_path, mall_id))
    mysql.connection.commit()
    cur.close()

    flash("Registration successful! Please login to access your Admin Dashboard.", "success")
    return redirect(url_for('login_page'))


# =========================================================
# MALL PAGE (reached via QR code scan)
# =========================================================
@app.route('/mall/<int:mall_id>')
def mall_page(mall_id):
    cur = mysql.connection.cursor()
    cur.execute("SELECT mall_name, mall_location, map_url FROM admins WHERE id=%s", (mall_id,))
    mall = cur.fetchone()
    cur.close()

    if not mall:
        return "Mall not found!", 404

    # Remember which mall this customer scanned/entered
    session['scanned_mall_id'] = mall_id

    # If already logged in as a customer, jump straight into that mall's dashboard
    if login_required_role('customer'):
        flash(f"Welcome to {mall['mall_name']}!", "success")
        return redirect(url_for('dashboard_customer'))

    flash(f"Welcome to {mall['mall_name']}! Please login or register to continue.", "success")
    return redirect(url_for('login_page'))


# =========================================================
# ADMIN DASHBOARD
# =========================================================
@app.route('/dashboard_admin')
def dashboard_admin():
    if not login_required_role('admin'):
        flash("Please login as an admin to continue.", "error")
        return redirect(url_for('login_page'))

    cur = mysql.connection.cursor()

    cur.execute("SELECT * FROM admins WHERE id=%s", (session['user_id'],))
    admin = cur.fetchone()

    cur.execute("SELECT * FROM ips_locations ORDER BY sensor_code")
    ips_sensors = cur.fetchall()

    cur.execute("""SELECT p.*, i.sensor_code, i.section_label
                   FROM products p
                   LEFT JOIN ips_locations i ON p.ips_sensor_id = i.id
                   WHERE p.admin_id=%s
                   ORDER BY p.created_at DESC""", (session['user_id'],))
    products = cur.fetchall()

    cur.execute("SELECT * FROM offers WHERE admin_id=%s ORDER BY created_at DESC", (session['user_id'],))
    offers = cur.fetchall()

    cur.close()

    return render_template('dashboard_admin.html',
                            name=session.get('name'),
                            admin=admin,
                            ips_sensors=ips_sensors,
                            products=products,
                            offers=offers)


# ---------- ADD PRODUCT (admin) ----------
@app.route('/add_product', methods=['POST'])
def add_product():
    if not login_required_role('admin'):
        flash("Please login as an admin to continue.", "error")
        return redirect(url_for('login_page'))

    admin_id = session['user_id']
    product_name = request.form.get('product_name', '').strip()
    category = request.form.get('category', '').strip()
    price = request.form.get('price', '').strip()
    discount_price = request.form.get('discount_price', '').strip()
    description = request.form.get('description', '').strip()
    ips_sensor_id = request.form.get('ips_sensor_id', '').strip()

    errors = []
    if not product_name:
        errors.append("Product name is required.")
    if not category:
        errors.append("Category is required.")

    price_val = None
    try:
        price_val = float(price)
        if price_val <= 0:
            errors.append("Price must be a positive number.")
    except ValueError:
        errors.append("Price must be a valid number.")

    discount_val = None
    if discount_price:
        try:
            discount_val = float(discount_price)
            if discount_val < 0:
                errors.append("Discount price cannot be negative.")
            elif price_val and discount_val >= price_val:
                errors.append("Discount price must be lower than the regular price.")
        except ValueError:
            errors.append("Discount price must be a valid number.")

    if not description:
        errors.append("Description is required.")
    if not ips_sensor_id:
        errors.append("Please select an IPS sensor location for this product.")

    if errors:
        for e in errors:
            flash(e, "error")
        return redirect(url_for('dashboard_admin'))

    cur = mysql.connection.cursor()
    cur.execute("""INSERT INTO products
                   (admin_id, product_name, category, price, offer, description, ips_sensor_id)
                   VALUES (%s,%s,%s,%s,%s,%s,%s)""",
                (admin_id, product_name, category, price_val, discount_val, description, ips_sensor_id))
    mysql.connection.commit()
    cur.close()

    flash("Product added successfully.", "success")
    return redirect(url_for('dashboard_admin'))


# ---------- REMOVE PRODUCT (admin) ----------
@app.route('/remove_product/<int:product_id>', methods=['POST'])
def remove_product(product_id):
    if not login_required_role('admin'):
        flash("Please login as an admin to continue.", "error")
        return redirect(url_for('login_page'))

    cur = mysql.connection.cursor()
    cur.execute("DELETE FROM products WHERE id=%s AND admin_id=%s", (product_id, session['user_id']))
    mysql.connection.commit()
    cur.close()

    flash("Product removed.", "success")
    return redirect(url_for('dashboard_admin'))


# ---------- ADD SPECIAL OFFER (admin) ----------
@app.route('/add_offer', methods=['POST'])
def add_offer():
    if not login_required_role('admin'):
        flash("Please login as an admin to continue.", "error")
        return redirect(url_for('login_page'))

    admin_id = session['user_id']
    title = request.form.get('title', '').strip()
    description = request.form.get('description', '').strip()

    if not title:
        flash("Offer title is required.", "error")
        return redirect(url_for('dashboard_admin'))

    cur = mysql.connection.cursor()
    cur.execute("INSERT INTO offers (admin_id, title, description) VALUES (%s, %s, %s)",
                (admin_id, title, description))
    mysql.connection.commit()
    cur.close()

    flash("Special offer added.", "success")
    return redirect(url_for('dashboard_admin'))


# ---------- REMOVE SPECIAL OFFER (admin) ----------
@app.route('/remove_offer/<int:offer_id>', methods=['POST'])
def remove_offer(offer_id):
    if not login_required_role('admin'):
        flash("Please login as an admin to continue.", "error")
        return redirect(url_for('login_page'))

    cur = mysql.connection.cursor()
    cur.execute("DELETE FROM offers WHERE id=%s AND admin_id=%s", (offer_id, session['user_id']))
    mysql.connection.commit()
    cur.close()

    flash("Offer removed.", "success")
    return redirect(url_for('dashboard_admin'))


# =========================================================
# CUSTOMER DASHBOARD
# =========================================================
@app.route('/dashboard_customer')
def dashboard_customer():
    if not login_required_role('customer'):
        flash("Please login as a customer to continue.", "error")
        return redirect(url_for('login_page'))

    cur = mysql.connection.cursor()

    # Customers can ONLY reach a mall's dashboard by scanning that mall's QR
    # code (route /mall/<id>) or by typing in the Mall ID printed on the
    # QR stamp below. There is no listing/browsing of every registered mall.
    mall_id = request.args.get('mall_id', type=int)

    if mall_id:
        cur.execute("SELECT id FROM admins WHERE id=%s", (mall_id,))
        if cur.fetchone():
            session['scanned_mall_id'] = mall_id
        else:
            flash(f"No mall found with ID {mall_id}. Please check the ID and try again.", "error")
            session.pop('scanned_mall_id', None)
            mall_id = None

    if not mall_id:
        mall_id = session.get('scanned_mall_id')

    products = []
    offers = []
    selected_mall = None
    if mall_id:
        cur.execute("SELECT * FROM admins WHERE id=%s", (mall_id,))
        selected_mall = cur.fetchone()

        if not selected_mall:
            # Mall was removed/invalid; drop it from the session
            session.pop('scanned_mall_id', None)
            mall_id = None
        else:
            cur.execute("""SELECT p.*, i.sensor_code, i.section_label, i.latitude, i.longitude
                           FROM products p
                           LEFT JOIN ips_locations i ON p.ips_sensor_id = i.id
                           WHERE p.admin_id=%s
                           ORDER BY p.category, p.product_name""", (mall_id,))
            products = cur.fetchall()

            cur.execute("SELECT * FROM offers WHERE admin_id=%s ORDER BY created_at DESC", (mall_id,))
            offers = cur.fetchall()

    cur.close()

    return render_template('dashboard_customer.html',
                            name=session.get('name'),
                            selected_mall=selected_mall,
                            selected_mall_id=mall_id,
                            products=products,
                            offers=offers)


@app.route('/leave_mall')
def leave_mall():
    """Lets a customer step out of the current mall's dashboard and
    scan/enter a different Mall ID."""
    if not login_required_role('customer'):
        flash("Please login as a customer to continue.", "error")
        return redirect(url_for('login_page'))

    session.pop('scanned_mall_id', None)
    flash("You've left the mall. Scan a mall's QR code or enter its Mall ID to continue.", "success")
    return redirect(url_for('dashboard_customer'))


# =========================================================
# FEEDBACK
# =========================================================
@app.route('/submit_feedback', methods=['POST'])
def submit_feedback():
    if not login_required_role('customer'):
        flash("Please login as a customer to submit feedback.", "error")
        return redirect(url_for('login_page'))

    user_name = request.form.get('user_name', '').strip()
    email = request.form.get('email', '').strip()
    rating = request.form.get('rating', '').strip()
    comment = request.form.get('comment', '').strip()

    errors = []
    if not validate_name(user_name):
        errors.append("Name must contain only letters/spaces (2-50 characters).")
    if not validate_email(email):
        errors.append("Please enter a valid email address.")
    if not rating:
        errors.append("Please select a rating.")
    if not comment:
        errors.append("Please enter your comment.")

    if errors:
        for e in errors:
            flash(e, "error")
        return redirect(url_for('dashboard_customer'))

    cur = mysql.connection.cursor()
    cur.execute("INSERT INTO feedback (user_name, email, rating, comment) VALUES (%s,%s,%s,%s)",
                (user_name, email, rating, comment))
    mysql.connection.commit()
    cur.close()

    flash("Thank you for your feedback!", "success")
    return redirect(url_for('dashboard_customer'))


@app.route('/get_feedback')
def get_feedback():
    if not login_required_role('admin'):
        flash("Please login as an admin to continue.", "error")
        return redirect(url_for('login_page'))

    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM feedback ORDER BY created_at DESC")
    feedback_list = cur.fetchall()
    cur.close()

    return render_template('feedback_list.html', feedback_list=feedback_list)


if __name__ == '__main__':
    app.run(debug=True)
