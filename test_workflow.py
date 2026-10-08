import requests
import time
import sys

BASE_URL = 'http://localhost:5000'
session = requests.Session()

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
    stations = res.json()
    station_id = stations[0]['id']
    
    # 4. View Slots
    res = session.get(f'{BASE_URL}/api/stations/{station_id}/slots?date=2026-10-08')
    slots = res.json()
    available_slot = next(s for s in slots if s['is_available'])
    slot_id = available_slot['id']
    
    # 5. Book
    print("5. Creating booking...")
    res = session.post(f'{BASE_URL}/api/bookings', json={
        'slot_id': slot_id,
        'date': '2026-10-08'
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
    # Book a new slot to cancel
    res = session.post(f'{BASE_URL}/api/bookings', json={
        'slot_id': slot_id,
        'date': '2026-10-09'
    })
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
