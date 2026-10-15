import datetime
import requests
import time
import sys

BASE_URL = 'http://localhost:5000'
session = requests.Session()


def find_available_slot(sess, start_date, max_days=14):
    """Scan stations and dates for a free slot so repeated test runs
    never exhaust a single day (completed bookings are permanent)."""
    stations = sess.get(f'{BASE_URL}/api/stations').json()
    for offset in range(max_days):
        date_str = (start_date + datetime.timedelta(days=offset)).isoformat()
        for station in stations:
            slots = sess.get(f"{BASE_URL}/api/stations/{station['id']}/slots",
                             params={'date': date_str}).json()
            available = next((s for s in slots if s['is_available']), None)
            if available:
                return available['id'], date_str
    return None, None

def test_workflow():
    print("Testing Workflow...")
    
    # 1. Register
    print("1. Registering user...")
    res = session.post(f'{BASE_URL}/api/register', json={
        'name': 'Test User Notifications',
        'email': 'notif_test@example.com',
        'phone': '5559876543',
        'password': 'testpassword'
    })
    
    # 2. Login
    print("2. Logging in...")
    res = session.post(f'{BASE_URL}/api/login', json={
        'email': 'notif_test@example.com',
        'password': 'testpassword'
    })
    assert res.status_code == 200, f"Login failed: {res.text}"
    user_id = res.json()['user']['id']
    
    # 3. Search Stations
    res = session.get(f'{BASE_URL}/api/stations')
    assert res.status_code == 200, f"Station search failed: {res.text}"
    stations = res.json()
    assert stations, 'No stations found'

    # 4. View Slots — find a station/date combination with a free slot
    slot_id, book_date = find_available_slot(session, datetime.date(2026, 10, 8))
    assert slot_id is not None, 'No available slot found on any station within 14 days'

    # 5. Book
    print(f"5. Creating booking for {book_date}...")
    res = session.post(f'{BASE_URL}/api/bookings', json={
        'slot_id': slot_id,
        'date': book_date
    })
    assert res.status_code == 201
    booking_id = res.json()['booking_id']
    
    # Check booking notification
    res = session.get(f'{BASE_URL}/api/notifications')
    notifs = res.json()
    assert any('created successfully' in n['message'] for n in notifs)
    
    # 6. Payment Failure
    print("6. Simulating payment failure...")
    res = session.post(f'{BASE_URL}/api/payments', json={
        'booking_id': booking_id,
        'method': 'FAIL'
    })
    assert res.status_code == 400
    
    res = session.get(f'{BASE_URL}/api/notifications')
    notifs = res.json()
    assert any('failed' in n['message'] for n in notifs)
    
    # 7. Payment Success
    print("7. Simulating payment success...")
    res = session.post(f'{BASE_URL}/api/payments', json={
        'booking_id': booking_id,
        'method': 'CREDIT_CARD'
    })
    assert res.status_code == 201
    
    res = session.get(f'{BASE_URL}/api/notifications')
    notifs = res.json()
    assert any('successful' in n['message'] for n in notifs)
    
    # 8. Start Charging
    print("8. Starting charging...")
    res = session.post(f'{BASE_URL}/api/charging/start', json={'booking_id': booking_id})
    assert res.status_code == 200
    
    res = session.get(f'{BASE_URL}/api/notifications')
    notifs = res.json()
    assert any('started' in n['message'] for n in notifs)
    
    # 9. Complete Charging
    print("9. Completing charging...")
    res = session.post(f'{BASE_URL}/api/charging/complete', json={'booking_id': booking_id})
    assert res.status_code == 200
    
    res = session.get(f'{BASE_URL}/api/notifications')
    notifs = res.json()
    assert any('completed' in n['message'] for n in notifs)
    
    # 10. Test Cancellation
    print("10. Testing cancellation notification...")
    # Book a new slot to cancel (fresh slot/date so this stays repeatable)
    cancel_slot_id, cancel_date = find_available_slot(session, datetime.date(2026, 10, 8))
    assert cancel_slot_id is not None, 'No available slot found for cancellation test'
    res = session.post(f'{BASE_URL}/api/bookings', json={
        'slot_id': cancel_slot_id,
        'date': cancel_date
    })
    assert res.status_code == 201, f"Cancel-test booking failed: {res.text}"
    cancel_booking_id = res.json()['booking_id']
    
    res = session.put(f'{BASE_URL}/api/bookings/{cancel_booking_id}/cancel')
    assert res.status_code == 200
    
    res = session.get(f'{BASE_URL}/api/notifications')
    notifs = res.json()
    assert any('cancelled' in n['message'] for n in notifs)
    
    print("Workflow test completed successfully, all notifications verified!")

if __name__ == '__main__':
    time.sleep(2)
    try:
        test_workflow()
    except Exception as e:
        print(f"Test failed: {e}")
        sys.exit(1)
