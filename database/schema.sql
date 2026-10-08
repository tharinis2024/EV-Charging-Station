CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    phone TEXT NOT NULL,
    password TEXT NOT NULL,
    is_admin BOOLEAN DEFAULT 0
);

CREATE TABLE IF NOT EXISTS stations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    location TEXT NOT NULL,
    operating_hours TEXT NOT NULL,
    connector_types TEXT NOT NULL,
    price_per_kwh REAL NOT NULL,
    status TEXT DEFAULT 'ACTIVE'
);

CREATE TABLE IF NOT EXISTS charging_points (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    station_id INTEGER,
    point_name TEXT,
    status TEXT DEFAULT 'ACTIVE', -- ACTIVE, INACTIVE
    FOREIGN KEY(station_id) REFERENCES stations(id)
);

CREATE TABLE IF NOT EXISTS slots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    point_id INTEGER,
    slot_time TEXT NOT NULL,
    FOREIGN KEY(point_id) REFERENCES charging_points(id)
);

CREATE TABLE IF NOT EXISTS bookings (
    id TEXT PRIMARY KEY,
    user_id INTEGER,
    slot_id INTEGER,
    date TEXT NOT NULL,
    amount REAL NOT NULL,
    status TEXT DEFAULT 'PENDING', -- PENDING, CONFIRMED, CANCELLED
    FOREIGN KEY(user_id) REFERENCES users(id),
    FOREIGN KEY(slot_id) REFERENCES slots(id)
);

CREATE TABLE IF NOT EXISTS payments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    booking_id TEXT,
    amount REAL,
    method TEXT,
    status TEXT, -- SUCCESS, FAILED
    transaction_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(booking_id) REFERENCES bookings(id)
);

CREATE TABLE IF NOT EXISTS charging_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    booking_id TEXT,
    status TEXT DEFAULT 'BOOKED', -- BOOKED, CHARGING, COMPLETED, CANCELLED
    start_time TIMESTAMP,
    end_time TIMESTAMP,
    duration INTEGER,
    energy_consumed REAL,
    FOREIGN KEY(booking_id) REFERENCES bookings(id)
);

CREATE TABLE IF NOT EXISTS notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    message TEXT NOT NULL,
    is_read BOOLEAN DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(user_id) REFERENCES users(id)
);

-- Insert sample admin
INSERT OR IGNORE INTO users (id, name, email, phone, password, is_admin) VALUES
(1, 'Admin User', 'admin@example.com', '1234567890', 'admin123', 1);

-- Insert sample user
INSERT OR IGNORE INTO users (id, name, email, phone, password, is_admin) VALUES
(2, 'Sample User', 'user@example.com', '0987654321', 'user123', 0);

-- Insert sample stations
INSERT OR IGNORE INTO stations (id, name, location, operating_hours, connector_types, price_per_kwh, status) VALUES
(1, 'Central City Station', 'Downtown', '24/7', 'Type 2, CCS', 0.50, 'ACTIVE'),
(2, 'Northside Mall Plug', 'Northside', '08:00 - 22:00', 'CCS, CHAdeMO', 0.45, 'ACTIVE'),
(3, 'Highway Fast Charge', 'Highway 50', '24/7', 'Tesla, CCS', 0.60, 'ACTIVE');

-- Insert sample charging points
INSERT OR IGNORE INTO charging_points (id, station_id, point_name) VALUES
(1, 1, 'Point A1'), (2, 1, 'Point A2'),
(3, 2, 'Point B1'),
(4, 3, 'Point C1'), (5, 3, 'Point C2');

-- Insert sample slots
INSERT OR IGNORE INTO slots (id, point_id, slot_time) VALUES
(1, 1, '09:00-10:00'), (2, 1, '10:00-11:00'), (3, 1, '11:00-12:00'),
(4, 2, '09:00-10:00'), (5, 2, '10:00-11:00'),
(6, 3, '14:00-15:00'), (7, 3, '15:00-16:00'),
(8, 4, '18:00-19:00'), (9, 4, '19:00-20:00');
