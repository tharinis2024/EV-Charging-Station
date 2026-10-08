# EV Charging Station Booking System

A simple full-stack academic web application for booking EV charging stations. 
Built for a Software Testing project (Selenium, Bruno, JMeter).

## Features

- **User Authentication:** Register and login system.
- **Station Search:** Find available charging stations.
- **Booking Management:** Select slots and book a charging point.
- **Payment Simulation:** Simulate successful and failed payments.
- **Charging Session:** States to simulate BOOKED -> CHARGING -> COMPLETED.
- **Booking History:** View upcoming, completed, and cancelled bookings.
- **Admin Dashboard:** Basic UI for administrative tasks.

## Technologies

- Python Flask (Backend)
- SQLite (Database)
- HTML, CSS, JavaScript (Frontend)
- Jinja Templates (Server-side rendering)

## Installation & How to Run

1. Clone or download this repository.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Run the application (the SQLite database will be initialized automatically on first run):
   ```bash
   python app.py
   ```
4. Open your browser and go to `http://localhost:5000`

## Sample Credentials

**User:**
- Email: `user@example.com`
- Password: `user123`

**Admin:**
- Email: `admin@example.com`
- Password: `admin123`

## API Endpoints

- `POST /api/register`
- `POST /api/login`
- `POST /api/logout`
- `GET /api/stations`
- `GET /api/stations/<id>`
- `GET /api/stations/<id>/slots`
- `POST /api/bookings`
- `GET /api/bookings/<id>`
- `PUT /api/bookings/<id>/cancel`
- `POST /api/payments`
- `POST /api/charging/start`
- `POST /api/charging/complete`
- `GET /api/users/<id>/bookings`
