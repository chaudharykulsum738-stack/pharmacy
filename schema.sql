-- ============================================
-- Smart Pharmacy Inventory & Cabinet Recommendation
-- Database Schema (multi-user version)
-- ============================================

CREATE DATABASE IF NOT EXISTS smart_pharmacy;
USE smart_pharmacy;

-- ---------- USERS ----------
-- Every pharmacy owner/participant gets their own account.
-- All other tables are scoped to a user_id so no one sees anyone else's data.
CREATE TABLE users (
    user_id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(150) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ---------- CABINETS ----------
CREATE TABLE cabinets (
    cabinet_id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    cabinet_name VARCHAR(50) NOT NULL,       -- e.g. "Cabinet A - Front Counter"
    priority_level VARCHAR(20) NOT NULL,     -- 'High', 'Medium', 'Low'
    capacity INT DEFAULT 100,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);

-- ---------- MEDICINES ----------
CREATE TABLE medicines (
    medicine_id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    medicine_name VARCHAR(100) NOT NULL,
    category VARCHAR(50),
    usage_description VARCHAR(255),          -- short note on what it's used for
    active_ingredient VARCHAR(100),          -- e.g. "Paracetamol"
    dosage_strength VARCHAR(50),             -- e.g. "500mg"
    storage_condition VARCHAR(100) DEFAULT 'Room temperature',
    prescription_required VARCHAR(3) DEFAULT 'No',  -- 'Yes' or 'No'
    stock_quantity INT NOT NULL DEFAULT 0,
    min_stock_level INT NOT NULL DEFAULT 10,  -- threshold for low stock
    expiry_date DATE NOT NULL,
    cabinet_id INT,
    usage_frequency INT DEFAULT 0,            -- times sold, updated over time
    stock_status VARCHAR(20) DEFAULT 'OK',    -- 'OK' or 'Low Stock'
    FOREIGN KEY (user_id) REFERENCES users(user_id),
    FOREIGN KEY (cabinet_id) REFERENCES cabinets(cabinet_id)
);

-- ---------- CUSTOMERS ----------
CREATE TABLE customers (
    customer_id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    name VARCHAR(100) NOT NULL,
    contact_number VARCHAR(15) NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);

-- ---------- SALES ----------
CREATE TABLE sales (
    sale_id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    customer_id INT NOT NULL,
    medicine_id INT NOT NULL,
    quantity_sold INT NOT NULL,
    sale_date DATE NOT NULL DEFAULT (CURRENT_DATE),
    FOREIGN KEY (user_id) REFERENCES users(user_id),
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id),
    FOREIGN KEY (medicine_id) REFERENCES medicines(medicine_id)
);

-- ---------- SUBSTITUTES ----------
-- Links medicines that share the same salt/generic composition
CREATE TABLE substitutes (
    substitute_id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    medicine_id INT NOT NULL,
    substitute_medicine_id INT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(user_id),
    FOREIGN KEY (medicine_id) REFERENCES medicines(medicine_id),
    FOREIGN KEY (substitute_medicine_id) REFERENCES medicines(medicine_id)
);

-- ============================================
-- TRIGGER: Low Stock Alert
-- Fires after every sale insert -> updates
-- medicine stock and flags "Low Stock" if needed.
-- Scoped naturally: it only ever touches the medicine_id on
-- the sale row, and each medicine already belongs to one user.
-- ============================================
DELIMITER //

CREATE TRIGGER trg_low_stock_check
AFTER INSERT ON sales
FOR EACH ROW
BEGIN
    -- reduce stock quantity
    UPDATE medicines
    SET stock_quantity = stock_quantity - NEW.quantity_sold,
        usage_frequency = usage_frequency + NEW.quantity_sold
    WHERE medicine_id = NEW.medicine_id;

    -- check threshold and flag status
    UPDATE medicines
    SET stock_status = CASE
        WHEN stock_quantity <= min_stock_level THEN 'Low Stock'
        ELSE 'OK'
    END
    WHERE medicine_id = NEW.medicine_id;
END//

DELIMITER ;

-- ============================================
-- Sample seed data (optional, for testing)
-- Creates one demo user + demo data owned only by that user.
-- IMPORTANT: run app/create_demo_user.py after this script to set a
-- real password hash for the demo account (see README).
-- ============================================
INSERT INTO users (name, email, password_hash) VALUES
('Demo Owner', 'demo@pharmacy.com', 'PLACEHOLDER_RUN_create_demo_user.py');

INSERT INTO cabinets (user_id, cabinet_name, priority_level, capacity) VALUES
(1, 'Cabinet A - Front Counter', 'High', 50),
(1, 'Cabinet B - Mid Shelf', 'Medium', 100),
(1, 'Cabinet C - Back Storage', 'Low', 200);

-- Medicines, substitutes, customers, and sales history are NOT seeded here.
-- Run app/create_demo_user.py (sets the password) then app/seed_data.py
-- (loads ~63 medicines with usage descriptions, substitute pairs, and
-- 30 days of sales history) - see README for the exact commands.
