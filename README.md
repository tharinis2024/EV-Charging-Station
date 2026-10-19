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

## Vercel deployment with PostgreSQL

Vercel functions cannot use the ignored, deployment-excluded SQLite file as a
persistent application database. In the Vercel project settings, configure
`DATABASE_URL` with the connection URL of a real, reachable PostgreSQL database
(`postgres://` or `postgresql://`) and configure a strong `SECRET_KEY`. Keep
these values in Vercel environment variables; do not commit them. Configure
them for each environment you deploy, then redeploy. The project pins Python
3.12, for which `requirements.txt` installs `psycopg2-binary`.

The app does not initialize the PostgreSQL schema automatically in Vercel.
To copy the existing local SQLite data, first make and verify a separate
backup of `database/ev_booking.db`, and use a new, empty PostgreSQL database.
From a local terminal where the database URL is securely available as
`DATABASE_URL`, preview and then run:

```bash
python migrate.py --dry-run --copy-from-sqlite
python migrate.py --copy-from-sqlite
```

The migration reads SQLite in read-only mode, initializes PostgreSQL without
demo seed rows, copies the existing records without overwriting conflicts,
hashes legacy plaintext passwords, and synchronizes PostgreSQL identity
sequences. Review the per-table inserted/skipped counts: any skipped rows
indicate existing conflicting PostgreSQL records and should be reconciled
before switching traffic. Do not use the copy command if the local database
or a verified backup is unavailable. A dry run validates and prints the plan;
it does not prove that the database URL works. Only a successful real
migration proves the PostgreSQL connection and schema setup worked.

## Sample Credentials

**User:**
- Email: `user@example.com`
- Password: `user123`

**Admin:**
- Email: `admin@example.com`
- Password: `admin123`

> Passwords are stored as salted hashes (werkzeug). The sample rows in
> `database/schema.sql` are converted to hashes automatically the first time
> the app starts.

### Creating or promoting an admin account (local development)

Use the bundled helper instead of editing the database by hand:

```bash
# Create a brand-new admin (or update + promote an existing email)
python create_admin.py --email me@example.com --password mysecret --name "My Admin"

# Promote an existing registered user, keeping their current password
python create_admin.py --promote user@example.com
```

Admins log in at the dedicated **Admin Login** page:
**http://localhost:5000/admin/login** — linked from the navbar ("⚑ Admin",
visible to logged-out visitors) and from the user login page. Successful admin
login redirects to the Admin Panel at **http://localhost:5000/admin**; the
navbar shows an "Admin Panel" link for administrators only. A normal user
account can never sign in through the admin page.

## Admin Module

- **Dashboard:** live SQLite statistics — users, stations, charging points,
  bookings, active charging sessions, completed/cancelled bookings,
  successful/failed payments, revenue (₹).
- **Stations:** add / edit / view / delete with validation; deletes cascade
  only when no bookings reference the station.
- **Charging points:** CRUD + ACTIVE/INACTIVE toggle (blocked while a charging
  session is in progress).
- **Slots:** CRUD with duplicate-time prevention and an availability grid per
  date; slots with bookings cannot be deleted.
- **Bookings:** list, status/payment filters, search, detail view, and safe
  admin cancellation (lifecycle-guarded, notifies the user).
- **Pricing:** update ₹/kWh per station; negative values rejected; persisted
  in SQLite.
- **Users:** search, booking counts, protected delete (admins cannot delete
  their own account; active bookings block deletion). Passwords are never
  returned by the API.
- **Notifications:** read-only, system-wide view reusing the existing
  `notifications` table.

Security: `/admin` requires a logged-in admin (others are redirected / 403),
and every `/api/admin/*` endpoint returns 401 for anonymous requests and 403
for non-admin users.


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
