import requests
import time
import sys

BASE_URL = 'http://localhost:5000'

def test_admin_workflow():
    print("Testing Admin Workflow...")
    
    # 1. Normal User Access Test
    print("1. Testing unauthorized access...")
    normal_session = requests.Session()
    # Register/Login normal user
    normal_session.post(f'{BASE_URL}/api/register', json={
        'name': 'Normal User',
        'email': 'normal@example.com',
        'phone': '1112223333',
        'password': 'password'
    })
    normal_session.post(f'{BASE_URL}/api/login', json={
        'email': 'normal@example.com',
        'password': 'password'
    })
    
    # Try accessing admin API
    res = normal_session.get(f'{BASE_URL}/api/admin/stations')
    assert res.status_code == 403, f"Expected 403 Forbidden, got {res.status_code}"
    print("Unauthorized access correctly blocked with 403.")
    
    # 2. Admin Login
    print("2. Admin login...")
    admin_session = requests.Session()
    res = admin_session.post(f'{BASE_URL}/api/login', json={
        'email': 'admin@example.com',
        'password': 'admin123'
    })
    assert res.status_code == 200
    assert res.json()['user']['is_admin'] is True
    
    # 3. View Stations
    print("3. Viewing stations...")
    res = admin_session.get(f'{BASE_URL}/api/admin/stations')
    assert res.status_code == 200
    
    # 4. Add Station
    print("4. Adding a new station...")
    res = admin_session.post(f'{BASE_URL}/api/admin/stations', json={
        'name': 'Admin Test Station',
        'location': 'Admin Area',
        'operating_hours': '24/7',
        'connector_types': 'CCS',
        'price_per_kwh': 0.75
    })
    assert res.status_code == 201
    
    # 5. Add Charging Point
    print("5. Adding a charging point...")
    res = admin_session.get(f'{BASE_URL}/api/admin/stations')
    stations = res.json()
    new_station = next(s for s in stations if s['name'] == 'Admin Test Station')
    
    res = admin_session.post(f'{BASE_URL}/api/admin/points', json={
        'station_id': new_station['id'],
        'point_name': 'Test Point A'
    })
    assert res.status_code == 201
    
    # 6. Add Slot
    print("6. Adding a slot...")
    res = admin_session.get(f'{BASE_URL}/api/admin/points')
    points = res.json()
    new_point = next(p for p in points if p['point_name'] == 'Test Point A')
    
    res = admin_session.post(f'{BASE_URL}/api/admin/slots', json={
        'point_id': new_point['id'],
        'slot_time': '12:00-13:00'
    })
    assert res.status_code == 201
    
    # 7. Edit Station (Pricing Update)
    print("7. Updating station pricing...")
    res = admin_session.put(f'{BASE_URL}/api/admin/stations/{new_station["id"]}', json={
        'name': 'Admin Test Station Updated',
        'location': 'Admin Area',
        'operating_hours': '24/7',
        'connector_types': 'CCS',
        'price_per_kwh': 0.85,
        'status': 'ACTIVE'
    })
    assert res.status_code == 200
    
    # 8. View Bookings
    print("8. Viewing all bookings...")
    res = admin_session.get(f'{BASE_URL}/api/admin/bookings')
    assert res.status_code == 200
    # There may or may not be bookings depending on test_workflow.py execution, but it should return 200.
    
    # 9. Delete Slot, Point, Station
    print("9. Cleaning up...")
    res = admin_session.get(f'{BASE_URL}/api/admin/slots')
    slots = res.json()
    new_slot = next(s for s in slots if s['point_id'] == new_point['id'])
    admin_session.delete(f'{BASE_URL}/api/admin/slots/{new_slot["id"]}')
    admin_session.delete(f'{BASE_URL}/api/admin/points/{new_point["id"]}')
    admin_session.delete(f'{BASE_URL}/api/admin/stations/{new_station["id"]}')
    
    print("Admin workflow test completed successfully!")

if __name__ == '__main__':
    time.sleep(2)
    try:
        test_admin_workflow()
    except Exception as e:
        print(f"Test failed: {e}")
        sys.exit(1)
