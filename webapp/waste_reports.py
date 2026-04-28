import json
import os
from datetime import datetime

REPORTS_DATA_FILE = 'waste_reports_data.json'

def load_reports_data():
    if os.path.exists(REPORTS_DATA_FILE):
        try:
            with open(REPORTS_DATA_FILE, 'r') as f:
                return json.load(f)
        except:
            return initialize_reports_data()
    return initialize_reports_data()

def save_reports_data(data):
    try:
        with open(REPORTS_DATA_FILE, 'w') as f:
            json.dump(data, f, indent=2)
        return True
    except Exception as e:
        print(f"Error saving JSON: {e}")
        return False

def initialize_reports_data():
    return {
        'reports': {},
        'total_reports': 0,
        'pending_reports': 0,
        'noted_reports': 0,
        'collected_reports': 0,
        'hotspots': {},
        'total_waste_weight': 0.0
    }

def submit_waste_report(user_id, user_name, phone, email, address, 
                       latitude, longitude, waste_type, waste_weight, 
                       waste_description=None, image_path=None):
    data = load_reports_data()
    report_id = f"RPT_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    
    report = {
        'id': report_id,
        'user_id': user_id,
        'user_name': user_name,
        'phone': phone,
        'email': email,
        'address': address,
        'latitude': float(latitude),
        'longitude': float(longitude),
        'waste_type': waste_type,
        'waste_weight': float(waste_weight),
        'waste_description': waste_description,
        'status': 'pending',
        'submitted_at': datetime.now().isoformat()
    }
    
    data['reports'][report_id] = report
    data['total_reports'] += 1
    data['pending_reports'] += 1
    data['total_waste_weight'] += float(waste_weight)
    
    # Update hotspots
    loc_key = f"{float(latitude):.2f},{float(longitude):.2f}"
    if loc_key not in data['hotspots']:
        data['hotspots'][loc_key] = {'latitude': latitude, 'longitude': longitude, 'address': address, 'count': 0, 'total_weight': 0.0}
    
    data['hotspots'][loc_key]['count'] += 1
    data['hotspots'][loc_key]['total_weight'] += float(waste_weight)
    
    save_reports_data(data)
    return report_id

def get_all_reports(status=None, user_id=None):
    data = load_reports_data()
    reports = list(data['reports'].values())
    if status: reports = [r for r in reports if r['status'] == status]
    reports.sort(key=lambda x: x['submitted_at'], reverse=True)
    return reports

def get_dashboard_summary():
    data = load_reports_data()
    return {
        'total_reports': data['total_reports'],
        'pending_reports': data['pending_reports'],
        'noted_reports': data.get('noted_reports', 0),
        'collected_reports': data.get('collected_reports', 0),
        'total_waste_weight': round(data['total_waste_weight'], 2),
        'avg_response_time_hours': 0,
        'waste_types': {},
        'hotspots': list(data['hotspots'].values())
    }

def get_hotspots_analysis():
    data = load_reports_data()
    return list(data['hotspots'].values())
def update_report_status(report_id, status, ngo_notes=None, assigned_to=None):
    # 1. Load fresh data
    data = load_reports_data()
    
    # 2. Check if report exists
    if report_id not in data['reports']:
        print(f"DEBUG: Report ID {report_id} not found in {list(data['reports'].keys())}")
        return False
    
    # 3. Get the report reference
    report = data['reports'][report_id]
    old_status = report['status']
    
    # 4. Update counters (Total, Pending, Noted, Collected)
    # Ensure keys exist in data first
    for s in ['pending', 'noted', 'collected']:
        if f"{s}_reports" not in data:
            data[f"{s}_reports"] = 0

    if old_status != status:
        # Decrease old counter
        old_key = f"{old_status}_reports"
        data[old_key] = max(0, data[old_key] - 1)
            
        # Increase new counter
        new_key = f"{status}_reports"
        data[new_key] = data.get(new_key, 0) + 1
        
        # Update status and timestamps
        report['status'] = status
        now = datetime.now().isoformat()
        if status == 'noted': report['noted_at'] = now
        elif status == 'collected': report['collected_at'] = now
    
    # 5. Update optional fields
    if ngo_notes: report['ngo_notes'] = ngo_notes
    if assigned_to: report['assigned_to'] = assigned_to
    
    # 6. SAVE THE DATA PERMANENTLY
    return save_reports_data(data)
# Add these empty functions so app.py doesn't crash on import
def get_report_details(report_id): return {}
def generate_collection_route(ids): return {}
def export_reports_csv(): return ""