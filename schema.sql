-- =========================================================
-- THE SMART SHOPPER'S GUIDE - Database Schema
-- Import this file in phpMyAdmin (XAMPP) before running app.py
-- =========================================================

CREATE DATABASE IF NOT EXISTS smart_shopper;
USE smart_shopper;

-- ---------------------------------------------------------
-- CUSTOMERS
-- ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS customers (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(50) NOT NULL,
    email VARCHAR(100) NOT NULL UNIQUE,
    mobile VARCHAR(10) NOT NULL,
    age INT NOT NULL,
    password VARCHAR(255) NOT NULL,   -- stores a hashed password, not plain text
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ---------------------------------------------------------
-- ADMINS (Mall Managers)
-- ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS admins (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(50) NOT NULL,
    email VARCHAR(100) NOT NULL UNIQUE,
    password VARCHAR(255) NOT NULL,
    mall_name VARCHAR(100) NOT NULL,
    mall_location VARCHAR(150) NOT NULL,
    map_url VARCHAR(255),
    contact_no VARCHAR(10) NOT NULL,
    registration_id VARCHAR(50) NOT NULL,
    qr_code_path VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ---------------------------------------------------------
-- IPS SENSOR PRESETS (simulated hardware)
-- Since real BLE/Wi-Fi IPS hardware is not affordable right now,
-- the admin just picks a preset sensor code (IPS1 - IPS6) when
-- adding a product. Each preset code already has a fixed
-- lat/long stored here, so the customer's "Navigate" button can
-- route from the customer's live GPS location to this point.
-- ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS ips_locations (
    id INT AUTO_INCREMENT PRIMARY KEY,
    sensor_code VARCHAR(20) NOT NULL UNIQUE,
    section_label VARCHAR(100) NOT NULL,
    latitude DECIMAL(10,7) NOT NULL,
    longitude DECIMAL(10,7) NOT NULL
);

-- Preset IPS sensor locations (example coordinates around a mall in Vapi, Gujarat)
INSERT INTO ips_locations (sensor_code, section_label, latitude, longitude) VALUES
('IPS1', 'Electronics Section', 20.3715000, 72.9112000),
('IPS2', 'Grocery Section',     20.3717000, 72.9114000),
('IPS3', 'Clothing Section',    20.3719000, 72.9111000),
('IPS4', 'Footwear Section',    20.3714000, 72.9116000),
('IPS5', 'Billing Counter',     20.3716000, 72.9113000),
('IPS6', 'Food Court',          20.3718000, 72.9115000)
ON DUPLICATE KEY UPDATE section_label = VALUES(section_label);

-- ---------------------------------------------------------
-- PRODUCTS (added by admin, linked to a preset IPS sensor)
-- ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS products (
    id INT AUTO_INCREMENT PRIMARY KEY,
    admin_id INT NOT NULL,
    product_name VARCHAR(100) NOT NULL,
    category VARCHAR(50) NOT NULL,
    price DECIMAL(10,2) NOT NULL,
    offer VARCHAR(100),
    description TEXT,
    image VARCHAR(255),
    ips_sensor_id INT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (admin_id) REFERENCES admins(id) ON DELETE CASCADE,
    FOREIGN KEY (ips_sensor_id) REFERENCES ips_locations(id)
);

-- ---------------------------------------------------------
-- SPECIAL OFFERS (added/removed by admin, shown only on that
-- admin's own mall dashboard for customers)
-- ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS offers (
    id INT AUTO_INCREMENT PRIMARY KEY,
    admin_id INT NOT NULL,
    title VARCHAR(150) NOT NULL,
    description VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (admin_id) REFERENCES admins(id) ON DELETE CASCADE
);

-- ---------------------------------------------------------
-- FEEDBACK
-- ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS feedback (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_name VARCHAR(50) NOT NULL,
    email VARCHAR(100) NOT NULL,
    rating VARCHAR(20) NOT NULL,
    comment TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
