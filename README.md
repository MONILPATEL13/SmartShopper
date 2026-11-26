# 🛒 SmartShopper: The Smart Shopper's Guide

A Flask web app that helps customers browse a mall's products and offers, track their shopping budget and find product sections. Mall admins manage their products and offers from a dashboard.

Customers open a mall by scanning its QR code or entering its Mall ID.

## ✨ Features

### Customer
- Register and log in
- Enter a mall using its QR code or Mall ID
- View that mall's products, prices, discount prices and special offers
- Add products to a shopping list and see the total
- Set a budget limit and get an alert when the total crosses it
- Open walking directions to a product's section in Google Maps
- Submit a rating and feedback

### Mall Admin
- Register a mall and get a QR code generated for it
- Add and remove products
- Link each product to a section (sensor point)
- Add and remove special offers
- View customer feedback

### Account
- Password hashing
- Form validation for registration and other inputs
- Password reset using an email OTP (valid for 10 minutes)

## 🏗️ Architecture

```
Browser (HTML, Bootstrap, JavaScript)
        |
        v
Flask application (app.py) ----> Brevo API (OTP email)
        |                 \
        v                  ----> QR code images (static/qr/)
MySQL database

Navigate button: Browser location ----> Google Maps directions
```

### User flow
```
Admin:    Register mall -> QR generated -> Add products and offers
Customer: Scan QR / enter Mall ID -> Log in -> Browse -> Shopping list -> Navigate
```

## 🛠️ Tech Stack

| Part | Technology |
|---|---|
| Backend | Python, Flask |
| Database | MySQL (Flask-MySQLdb) |
| Frontend | HTML, CSS, Bootstrap, JavaScript |
| QR codes | qrcode, Pillow |
| Email | Brevo API |
| Production server | Gunicorn |

## 📁 Project Structure

```
SmartShopper/
├── app.py              # Routes and application logic
├── schema.sql          # Database tables and sample sensor points
├── requirements.txt
├── static/qr/          # Mall QR code images
└── templates/          # HTML pages
```

## 🗄️ Database Tables

| Table | Stores |
|---|---|
| `customers` | Customer accounts |
| `admins` | Admin accounts and mall details |
| `ips_locations` | Preset section coordinates |
| `products` | Mall products |
| `offers` | Special offers |
| `feedback` | Customer ratings and comments |

## 🚀 Run Locally (Windows)

### Requirements
- Python 3.12 (recommended for the pinned package versions)
- MySQL, for example through XAMPP
- A Brevo API key and verified sender email (for password reset)

### Steps

1. Clone the repository
   ```bash
   git clone https://github.com/MONILPATEL13/SmartShopper.git
   cd SmartShopper
   ```

2. Create a virtual environment and install packages
   ```bash
   python -m venv venv
   venv\Scripts\activate
   python -m pip install -r requirements.txt
   ```

3. Start MySQL and import `schema.sql` using phpMyAdmin. It creates the `smart_shopper` database.

4. Set environment variables in Command Prompt
   ```bat
   set SECRET_KEY=replace-with-a-long-random-value
   set MYSQL_HOST=localhost
   set MYSQL_USER=root
   set MYSQL_PASSWORD=your-mysql-password
   set MYSQL_DB=smart_shopper
   set MYSQL_PORT=3306
   set BREVO_API_KEY=your-brevo-api-key
   set SENDER_EMAIL=your-verified-sender-email
   ```
   If your local MySQL user has no password, skip the `MYSQL_PASSWORD` line.

5. Start the app
   ```bash
   python app.py
   ```

6. Open `http://127.0.0.1:5000`

A QR code generated on `127.0.0.1` will not open from a phone. Use the Mall ID for local testing.

## ⚠️ Current Limitations
- Indoor positioning is simulated: each section has preset coordinates, and no Bluetooth or Wi-Fi sensors are used
- The sample coordinates must be changed to match a real mall
- Directions rely on phone GPS and Google Maps, which may be inaccurate indoors
- The shopping list and budget are cleared when the page reloads
- Feedback is not separated by mall
- QR images are saved on the server's disk and may be lost on hosts with temporary storage
- This is a student project and needs security improvements before real-world use

## 🔮 Future Improvements
- Real indoor positioning with Bluetooth beacons
- Saved shopping lists
- Separate feedback for each mall
- Product images and search
- OTP storage on the server, attempt limits and CSRF protection

## 👤 Author

**Monil Patel**
[GitHub](https://github.com/MONILPATEL13) · [LinkedIn](https://www.linkedin.com/in/monil-patel-698ab6311)
