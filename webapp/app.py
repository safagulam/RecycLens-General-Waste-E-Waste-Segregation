"""
Smart Waste Classifier - Complete Application
==============================================
Flask application with two-role system (User/NGO Authority)
"""

from flask import Flask, render_template, request, jsonify, redirect, url_for, session, make_response
import os
import sys
import logging
from datetime import datetime
from werkzeug.utils import secure_filename

# Fix Windows Unicode issues
if sys.platform == 'win32':
    try:
        if sys.stdout.encoding != 'utf-8':
            sys.stdout.reconfigure(encoding='utf-8')
        if sys.stderr.encoding != 'utf-8':
            sys.stderr.reconfigure(encoding='utf-8')
    except:
        pass

app = Flask(__name__)
app.secret_key = 'your-secret-key-change-in-production'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['RESULTS_FOLDER'] = 'static/results'

# Create folders if they don't exist
os.makedirs('static/uploads', exist_ok=True)
os.makedirs('static/results', exist_ok=True)
os.makedirs('templates', exist_ok=True)

# ============================================================================
# LOGGING CONFIGURATION (Windows-safe)
# ============================================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('waste_classifier.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# ============================================================================
# MODULE IMPORTS WITH AVAILABILITY FLAGS
# ============================================================================

# Database
DATABASE_AVAILABLE = False
try:
    from database import (
        initialize_database,
        register_user,
        login_user,
        validate_session,
        logout_user,
        get_user_profile,
        update_user_stats,
        record_waste_session,
        get_user_waste_history,
        get_user_analytics
    )
    DATABASE_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Database module not available: {e}")

# YOLO Models
MODELS_LOADED = False
ewaste_model = None
biowaste_model = None

try:
    from ultralytics import YOLO
    import cv2
    import numpy as np
    from PIL import Image
    
    if os.path.exists('bes.pt'):
        ewaste_model = YOLO('bes.pt')
        logger.info("E-Waste model loaded")
    
    if os.path.exists('yolov8n.pt'):
        biowaste_model = YOLO('yolov8n.pt')
        logger.info("Bio-Waste model loaded")
    
    if ewaste_model or biowaste_model:
        MODELS_LOADED = True
except ImportError as e:
    logger.warning(f"YOLO not available: {e}")

# Analytics Module
ANALYTICS_AVAILABLE = False
try:
    from waste_analytics import generate_analytics_report, export_analytics_csv
    ANALYTICS_AVAILABLE = True
except ImportError:
    logger.warning("Analytics module not available")






# Waste Reports Module
WASTE_REPORTS_AVAILABLE = False
try:
    # This must match the filename exactly (waste_reports.py)
    from waste_reports import (
        submit_waste_report,
        update_report_status,
        get_all_reports,
        get_report_details,
        get_dashboard_summary,
        get_hotspots_analysis,
        generate_collection_route,
        export_reports_csv
    )
    WASTE_REPORTS_AVAILABLE = True
    logger.info("✅ Waste reports module loaded successfully")
except ImportError as e:
    logger.warning(f"❌ Waste reports module not available: {e}")
# ============================================================================
# WASTE CLASSIFICATION DATA
# ============================================================================
# Grouping items by their nature
# ============================================================================
# WASTE DATABASE & LOGIC (FIXED)
# ============================================================================

ELECTRICAL_ITEMS = ['battery', 'smart phone', 'laptop', 'tablet', 'monitor', 'keyboard', 'mouse', 'hdd', 'cable', 'headset', 'printer', 'webcam']

# Ensure every item has a score
RECYCLABILITY_SCORES = {
    'bottle': 90, 'cup': 45, 'vase': 75, 'plate': 65, 'can': 85,
    'battery': 10, 'smart phone': 65, 'laptop': 75, 'cable': 95,
    'leaves': 100, 'fruit': 100, 'vegetables': 100, 'food waste': 95
}

MATERIAL_INFO = {
    # --- E-WASTE (Focus: Toxicity & Hazards) ---
    'battery': {
        'type': 'electrical',
        'materials': ['Lithium', 'Cobalt', 'Lead'],
        'toxicity': 'HIGH',
        'hazards': '🔥 FIRE HAZARD, 🧪 Chemical Leakage',
        'disposal_msg': 'STOP! Place in fire-proof SECURE E-Waste container.'
    },
    'smart phone': {
        'type': 'electrical',
        'materials': ['Gold', 'Silver', 'Palladium', 'Lithium'],
        'toxicity': 'MEDIUM',
        'hazards': '🔋 Battery Swelling Risk',
        'disposal_msg': 'Separate for parts recovery in e-waste bin.'
    },
    # --- NON E-WASTE (Focus: Contamination & Reuse) ---
    'bottle': {
        'type': 'general',
        'materials': ['PET Plastic', 'Glass'],
        'contamination_risk': 'Low (if rinsed)',
        'reuse_potential': 'High (Refillable/DIY)',
        'recycling_feasibility': 'Very High'
    },
    'cup': {
        'type': 'general',
        'materials': ['Ceramic', 'Paper', 'Plastic'],
        'contamination_risk': 'High (Liquid residue)',
        'reuse_potential': 'Medium',
        'recycling_feasibility': 'Low'
    }
}

def get_recyclability_info(item_name):
    """Categorizes waste and returns type-specific metrics."""
    name = str(item_name).lower().strip()
    
    # 1. Get basic recyclability score (Fixes the 'score' error)
    score = RECYCLABILITY_SCORES.get(name, 50)
    
    # 2. Identify if it is E-Waste
    is_ewaste = name in ELECTRICAL_ITEMS
    
    # 3. Fetch Info from Database
    info = MATERIAL_INFO.get(name, {
        'type': 'electrical' if is_ewaste else 'general',
        'materials': ['Mixed Components'],
        'toxicity': 'LOW',
        'hazards': 'Standard Handling',
        'disposal_msg': 'Place in secure e-waste bin.',
        'contamination_risk': 'Moderate',
        'reuse_potential': 'Limited',
        'recycling_feasibility': 'Moderate'
    })

    # 4. Construct result with the 'score' key included
    result = {
        'score': score, # <--- THIS FIXES YOUR ERROR
        'is_ewaste': is_ewaste,
        'class': name,
        'materials': info.get('materials', ['Mixed']),
        'nature_color': "#e67e22" if is_ewaste else "#3498db"
    }

    if is_ewaste:
        result.update({
            'toxicity': info.get('toxicity', 'LOW'),
            'hazards': info.get('hazards', 'General Hazard'),
            'disposal_msg': info.get('disposal_msg', 'Secure e-waste container.')
        })
    else:
        result.update({
            'contamination': info.get('contamination_risk', 'Moderate'),
            'reuse': info.get('reuse_potential', 'Limited'),
            'feasibility': info.get('recycling_feasibility', 'Moderate')
        })
        
    return result
  
def allowed_file(filename):
    """Check if file extension is allowed"""
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'bmp', 'webp'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

    """Get detailed sustainability info and categorize by biodegradability"""
    name = item_name.lower()
    
    # 1. Determine the Material Nature (Biodegradable / Electrical / Non-Bio)
    if name in BIO_DEGRADABLE_ITEMS:
        material_nature = "Biodegradable"
        nature_color = "#27ae60" # Green
    elif name in ELECTRICAL_ITEMS:
        material_nature = "Electrical (E-Waste)"
        nature_color = "#e67e22" # Orange
    else:
        material_nature = "Non-Biodegradable"
        nature_color = "#3498db" # Blue

    # 2. Get existing info from your dictionaries
    score = RECYCLABILITY_SCORES.get(name, 50)
    info = MATERIAL_INFO.get(name, {
        'materials': ['Mixed Materials'],
        'category': 'General Waste',
        'contamination': 'Moderate',
        'reuse': 'Limited',
        'feasibility': 'Moderate'
    })
    
    return {
        'score': score,
        'materials': info['materials'],
        'category': info['category'],
        'contamination': info['contamination'],
        'reuse': info['reuse'],
        'feasibility': info['feasibility'],
        # NEW FIELDS
        'material_nature': material_nature,
        'nature_color': nature_color
    }
def check_battery_hazards(detections):
    """Check for battery hazards in detections"""
    direct_batteries = ['Battery']
    battery_containing = ['Smart Phone', 'Laptop', 'Tablet', 'Webcam', 'Headset']
    
    hazards = []
    hazard_level = 'LOW'
    
    for det in detections:
        item = det.get('class', '')
        
        if item in direct_batteries:
            hazards.append({
                'item': item,
                'type': 'Direct Battery',
                'warning': 'Contains lithium-ion battery - FIRE HAZARD',
                'disposal': 'Take to designated battery recycling center'
            })
            hazard_level = 'HIGH'
        
        elif item in battery_containing:
            hazards.append({
                'item': item,
                'type': 'Battery-Powered Device',
                'warning': 'Contains internal battery',
                'disposal': 'Remove battery before disposal if possible'
            })
            if hazard_level == 'LOW':
                hazard_level = 'MEDIUM'
    
    safety_class = 'danger' if hazard_level == 'HIGH' else 'warning' if hazard_level == 'MEDIUM' else 'safe'
    
    return {
        'has_hazards': len(hazards) > 0,
        'hazard_level': hazard_level,
        'hazards': hazards,
        'safety_class': safety_class,
        'count': len(hazards)
    }

def get_current_user():
    """Get current user from session or authorization header"""
    # Check Authorization header first (for API calls)
    auth_header = request.headers.get('Authorization')
    if auth_header and auth_header.startswith('Bearer '):
        session_token = auth_header.split(' ')[1]
        if DATABASE_AVAILABLE:
            user = validate_session(session_token)
            if user:
                return user
    
    # Check cookies (for web pages)
    session_token = request.cookies.get('session_token')
    if session_token and DATABASE_AVAILABLE:
        user = validate_session(session_token)
        if user:
            return user
    
    return None

def login_required(f):
    """Decorator to require login"""
    from functools import wraps
    
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user = get_current_user()
        if not user:
            if request.is_json:
                return jsonify({'error': 'Authentication required'}), 401
            return redirect('/login')
        return f(*args, **kwargs)
    
    return decorated_function

# ============================================================================
# PUBLIC PAGE ROUTES
# ============================================================================

@app.route('/')
@app.route('/home')
def home():
    """Landing page"""
    return render_template('home.html')

@app.route('/register')
def register_page():
    """Registration page"""
    return render_template('register.html')

@app.route('/login')
def login_page():
    """Login page"""
    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    """Main waste classifier dashboard"""
    return render_template('index.html')

@app.route('/recyclability')
def recyclability_page():
    """Recyclability information page"""
    return render_template('recyclability.html')




@app.route('/analytics')
def analytics_page():
    """Analytics dashboard page"""
    return render_template('analytics_dashboard.html')


@app.route('/health')
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'database': DATABASE_AVAILABLE,
        'models': MODELS_LOADED,
        'modules': {
            'analytics': ANALYTICS_AVAILABLE,
            
            'waste_reports': WASTE_REPORTS_AVAILABLE
        }
    })

# ============================================================================
# USER ROUTES
# ============================================================================

@app.route('/user-dashboard')
def user_dashboard():
    """User dashboard page"""
    user = get_current_user()
    if not user or user.get('role') != 'user':
        return redirect('/login')
    return render_template('user_dashboard.html')

@app.route('/report-waste')
def report_waste_page():
    """Waste report submission page"""
    return render_template('user_report_waste.html')

# ============================================================================
# NGO ROUTES
# ============================================================================

@app.route('/ngo-dashboard')
def ngo_dashboard():
    """NGO authority dashboard page"""
    user = get_current_user()
    if not user or user.get('role') != 'ngo':
        return redirect('/login')
    return render_template('ngo_dashboard.html')

# ============================================================================
# AUTHENTICATION API
# ============================================================================

@app.route('/api/auth/register', methods=['POST'])
def api_register():
    """Register new user"""
    if not DATABASE_AVAILABLE:
        return jsonify({'success': False, 'message': 'Database not available'}), 500
    
    try:
        data = request.json
        
        result = register_user(
            email=data.get('email'),
            password=data.get('password'),
            full_name=data.get('full_name'),
            role=data.get('role', 'user'),  # 'user' or 'ngo'
            phone=data.get('phone'),
            location=data.get('location'),
            organization=data.get('organization')
        )
        
        return jsonify(result)
    
    except Exception as e:
        logger.error(f"Registration error: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/auth/login', methods=['POST'])
def api_login():
    """User login"""
    if not DATABASE_AVAILABLE:
        return jsonify({'success': False, 'message': 'Database not available'}), 500
    
    try:
        data = request.json
        
        result = login_user(
            email=data.get('email'),
            password=data.get('password')
        )
        
        return jsonify(result)
    
    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/auth/validate')
def api_validate_session():
    """Validate session token"""
    user = get_current_user()
    
    if user:
        return jsonify({
            'valid': True,
            'user': user
        })
    else:
        return jsonify({'valid': False}), 401

@app.route('/api/auth/logout', methods=['POST'])
def api_logout():
    """User logout"""
    if not DATABASE_AVAILABLE:
        return jsonify({'success': True})
    
    try:
        data = request.json
        session_token = data.get('session_token')
        
        if session_token:
            logout_user(session_token)
        
        return jsonify({'success': True})
    
    except Exception as e:
        logger.error(f"Logout error: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500

# ============================================================================
# WASTE DETECTION API
# ============================================================================
@app.route('/predict', methods=['POST'])
def predict():
    try:
        if 'file' not in request.files:
            return jsonify({'success': False, 'error': 'No file uploaded'}), 400
        
        file = request.files['file']
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)

        detections = []
        final_results = None
        waste_type = "General Waste"

        if MODELS_LOADED:
            # 1. Run both models
            res_e = ewaste_model(filepath) if ewaste_model else []
            res_b = biowaste_model(filepath) if biowaste_model else []

            # 2. Count detections in each
            count_e = sum(len(r.boxes) for r in res_e)
            count_b = sum(len(r.boxes) for r in res_b)

            # 3. Pick the model that detected the most items
            if count_e >= count_b and count_e > 0:
                final_results = res_e
                waste_type = "E-Waste Detected"
            elif count_b > 0:
                final_results = res_b
                waste_type = "Bio/Recyclable Waste Detected"
            else:
                # Fallback if nothing is detected
                final_results = res_b if res_b else res_e
                waste_type = "No specific waste identified"

            # 4. Process the detected boxes
            if final_results:
                for r in final_results:
                    for box in r.boxes:
                        cls_id = int(box.cls[0])
                        label = r.names[cls_id]
                        conf = float(box.conf[0])
                        
                        # Get the detailed info (Materials, Nature, etc.)
                        info = get_recyclability_info(label)
                        
                        det_data = {
                            'class': label,
                            'confidence': round(conf * 100, 1)
                        }
                        det_data.update(info)
                        detections.append(det_data)

                # 5. Save the annotated image
                annotated_img = final_results[0].plot()
                res_filename = "res_" + filename
                cv2.imwrite(os.path.join(app.config['RESULTS_FOLDER'], res_filename), annotated_img)
                result_url = f"/static/results/{res_filename}"
            else:
                result_url = f"/static/uploads/{filename}"

        # 6. Final Calculation
        total_items = len(detections)
        avg_score = sum(d['score'] for d in detections) / total_items if total_items > 0 else 0

        return jsonify({
            'success': True,
            'waste_type': waste_type,
            'detections': detections,
            'total_items': total_items,
            'avg_recyclability': round(avg_score, 1),
            'result_image': result_url
        })

    except Exception as e:
        print(f"Error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500
    try:
        if 'file' not in request.files:
            return jsonify({'success': False, 'error': 'No file uploaded'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'success': False, 'error': 'No file selected'}), 400

        # Save the file
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)

        detections = []
        waste_type = "General"
        
        if MODELS_LOADED:
            # 1. Run Detection (assuming ewaste_model is the one for batteries)
            # We check both models to be sure
            results = []
            if ewaste_model:
                results = ewaste_model(filepath)
                waste_type = "E-Waste"
            elif biowaste_model:
                results = biowaste_model(filepath)
                waste_type = "Bio-Waste"

            # 2. Process Boxes into the detections list
            for r in results:
                boxes = r.boxes
                for box in boxes:
                    cls = int(box.cls[0])
                    conf = float(box.conf[0])
                    label = r.names[cls] # This will be "Battery"
                    
                    # 3. GET THE DETAILED MATERIAL INFO
                    # This calls the function we fixed earlier
                    info = get_recyclability_info(label)
                    
                    # 4. Create the detection object
                    det_entry = {
                        'class': label,
                        'confidence': round(conf * 100, 1)
                    }
                    det_entry.update(info) # Adds materials, contamination, nature, etc.
                    detections.append(det_entry)

            # 5. Save the annotated image (the one with boxes)
            annotated_img = results[0].plot()
            result_filename = "res_" + filename
            result_path = os.path.join(app.config['RESULTS_FOLDER'], result_filename)
            cv2.imwrite(result_path, annotated_img)
            result_url = f"/static/results/{result_filename}"

            # 6. Calculate Overall Stats
            total_items = len(detections)
            avg_score = sum(d['score'] for d in detections) / total_items if total_items > 0 else 0

            return jsonify({
                'success': True,
                'waste_type': waste_type,
                'detections': detections, # THIS IS THE LIST FOR THE CARDS
                'total_items': total_items, # THIS WILL NOW SHOW 2 OR MORE
                'avg_recyclability': round(avg_score, 1),
                'result_image': result_url
            })

    except Exception as e:
        logger.error(f"Prediction Error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500
# ============================================================================
# WASTE REPORTS API (USER)
# ============================================================================
@app.route('/api/waste-reports/submit', methods=['POST'])
def api_submit_waste_report():
    """Submit waste report with proper error keys for the UI"""
    if not WASTE_REPORTS_AVAILABLE:
        return jsonify({'success': False, 'message': 'Waste reports module not available'}), 500
    
    # Verify the user is logged in
    user = get_current_user()
    if not user:
        return jsonify({'success': False, 'message': 'Authentication required. Please login again.'}), 401
    
    try:
        data = request.json
        
        # Ensure coordinates are provided
        if not data.get('latitude') or not data.get('longitude'):
            return jsonify({'success': False, 'message': 'Please select a location on the map.'}), 400

        report_id = submit_waste_report(
            user_id=user['user_id'],
            user_name=data['user_name'],
            phone=data['phone'],
            email=data['email'],
            address=data['address'],
            latitude=data['latitude'],
            longitude=data['longitude'],
            waste_type=data['waste_type'],
            waste_weight=data['waste_weight'],
            waste_description=data.get('waste_description')
        )
        
        return jsonify({
            'success': True,
            'report_id': report_id,
            'message': 'Report submitted successfully'
        })
    
    except Exception as e:
        logger.error(f"Submit report error: {str(e)}")
        return jsonify({'success': False, 'message': f"Server error: {str(e)}"}), 500

@app.route('/api/waste-reports/my-reports')
def api_my_reports():
    """Get user's reports"""
    if not WASTE_REPORTS_AVAILABLE:
        return jsonify([])
    
    user = get_current_user()
    if not user:
        return jsonify({'error': 'Authentication required'}), 401
    
    try:
        reports = get_all_reports(user_id=user['user_id'])
        return jsonify(reports)
    
    except Exception as e:
        logger.error(f"Get reports error: {str(e)}")
        return jsonify({'error': str(e)}), 500
@app.route('/api/ngo/reports/<report_id>/status', methods=['PUT'])
def api_update_report_status(report_id):
    try:
        data = request.get_json()
        new_status = data.get('status')
        
        import waste_reports
        # Call the updated function
        success = waste_reports.update_report_status(report_id, new_status)
        
        if success:
            print(f"✅ Status for {report_id} updated to {new_status}")
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'message': 'Failed to save to database'}), 500
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500

  
def update_report_status(report_id, status, ngo_notes=None, assigned_to=None):
    # 1. Load the latest data from the file
    data = load_reports_data()
    
    if report_id not in data['reports']:
        print(f"Error: Report {report_id} not found")
        return False
    
    report = data['reports'][report_id]
    old_status = report['status']
    
    # 2. Only update if the status is actually different
    if old_status != status:
        # Decrease old counter
        old_key = f"{old_status}_reports"
        if old_key in data:
            data[old_key] = max(0, data[old_key] - 1)
        else:
            # Create key if missing
            data[old_key] = 0

        # Increase new counter
        new_key = f"{status}_reports"
        data[new_key] = data.get(new_key, 0) + 1
        
        # Update the report record
        report['status'] = status
        
        # Add timestamps
        now = datetime.now().isoformat()
        if status == 'noted':
            report['noted_at'] = now
        elif status == 'collected':
            report['collected_at'] = now
    
    # 3. Update optional fields
    if ngo_notes: report['ngo_notes'] = ngo_notes
    if assigned_to: report['assigned_to'] = assigned_to
    
    # 4. CRITICAL: Save back to JSON file
    success = save_reports_data(data)
    return success
@app.route('/api/ngo/reports')
def api_ngo_reports():
    # Force reload of data from JSON
    import waste_reports
    reports = waste_reports.get_all_reports()
    return jsonify(reports)

@app.route('/api/ngo/dashboard-summary')
def api_ngo_dashboard_summary():
    import waste_reports
    summary = waste_reports.get_dashboard_summary()
    return jsonify(summary)
def get_dashboard_summary():
    data = load_reports_data()
    return {
        'total_reports': data.get('total_reports', 0),
        'pending_reports': data.get('pending_reports', 0),
        'noted_reports': data.get('noted_reports', 0),
        'collected_reports': data.get('collected_reports', 0),
        'total_waste_weight': round(data.get('total_waste_weight', 0), 2),
        'avg_response_time_hours': 0
    }

def api_hotspots():
    """Get hotspots analysis"""
    if not WASTE_REPORTS_AVAILABLE:
        return jsonify([])
    
    user = get_current_user()
    if not user or user.get('role') != 'ngo':
        return jsonify({'error': 'Unauthorized'}), 403
    
    try:
        hotspots = get_hotspots_analysis()
        return jsonify(hotspots)
    
    except Exception as e:
        logger.error(f"Hotspots error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/ngo/route-optimization', methods=['POST'])
def api_route_optimization():
    """Generate optimized collection route"""
    if not WASTE_REPORTS_AVAILABLE:
        return jsonify({'error': 'Waste reports module not available'}), 500
    
    user = get_current_user()
    if not user or user.get('role') != 'ngo':
        return jsonify({'error': 'Unauthorized'}), 403
    
    try:
        data = request.json
        route = generate_collection_route(data['report_ids'])
        return jsonify(route)
    
    except Exception as e:
        logger.error(f"Route optimization error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/ngo/reports/export')
def api_export_reports():
    """Export reports as CSV"""
    if not WASTE_REPORTS_AVAILABLE:
        return jsonify({'error': 'Waste reports module not available'}), 500
    
    user = get_current_user()
    if not user or user.get('role') != 'ngo':
        return jsonify({'error': 'Unauthorized'}), 403
    
    try:
        csv_data = export_reports_csv()
        
        response = make_response(csv_data)
        response.headers['Content-Type'] = 'text/csv'
        response.headers['Content-Disposition'] = 'attachment; filename=waste_reports.csv'
        
        return response
    
    except Exception as e:
        logger.error(f"Export error: {str(e)}")
        return jsonify({'error': str(e)}), 500

# ============================================================================
# ANALYTICS API
# ============================================================================

@app.route('/api/analytics')
def get_analytics():
    """Get analytics report"""
    if not ANALYTICS_AVAILABLE:
        # Return sample data if module not available
        return jsonify({
            'total_sessions': 0,
            'total_items': 0,
            'avg_recyclability': 0,
            'waste_distribution': {}
        })
    
    try:
        report = generate_analytics_report()
        return jsonify(report)
    except Exception as e:
        logger.error(f"Analytics error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/analytics/export')
def export_analytics():
    """Export analytics as CSV"""
    if not ANALYTICS_AVAILABLE:
        return jsonify({'error': 'Analytics not available'}), 500
    
    try:
        csv_data = export_analytics_csv()
        
        response = make_response(csv_data)
        response.headers['Content-Type'] = 'text/csv'
        response.headers['Content-Disposition'] = 'attachment; filename=analytics.csv'
        
        return response
    except Exception as e:
        logger.error(f"Export error: {str(e)}")
        return jsonify({'error': str(e)}), 500



@app.errorhandler(404)
def not_found(e):
    """404 error handler"""
    if request.path.startswith('/api/'):
        return jsonify({'error': 'Not found'}), 404
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(e):
    """500 error handler"""
    logger.error(f"Internal error: {str(e)}")
    if request.path.startswith('/api/'):
        return jsonify({'error': 'Internal server error'}), 500
    return render_template('500.html'), 500

@app.errorhandler(413)
def file_too_large(e):
    """413 error handler for file size"""
    return jsonify({'error': 'File too large. Maximum size is 16MB'}), 413
# app.py

@app.route('/api/collection-drives', methods=['GET'])
def api_get_all_campaigns():
    """Returns all campaigns for both Users and NGOs"""
    try:
        import collection_drive_analytics
        campaigns = collection_drive_analytics.get_all_campaigns_overview()
        return jsonify(campaigns)
    except Exception as e:
        return jsonify([])

@app.route('/api/collection-drives/create', methods=['POST'])
def api_create_campaign():
    """NGO creates a campaign"""
    try:
        data = request.json
        import collection_drive_analytics
        result = collection_drive_analytics.create_campaign(
            name=data['name'],
            institution=data['institution'],
            start_date=data['start_date'],
            end_date=data['end_date'],
            target_items=data['target_items'],
            location=data['location'],
            organizer=data['organizer'],
            campaign_type=data['campaign_type']
        )
        return jsonify({'success': True, 'campaign': result})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
# ============================================================================
# INITIALIZATION
# ============================================================================
@app.route('/api/collection-drives/record', methods=['POST'])
def api_record_drive_collection():
    try:
        data = request.json
        import collection_drive_analytics
        
        # This function must return True if it worked
        success = collection_drive_analytics.record_collection(
            campaign_id=data['campaign_id'],
            items_collected=data['items_collected']
        )
        
        if success:
            return jsonify({'success': True, 'message': 'Weight recorded'})
        else:
            return jsonify({'success': False, 'message': 'Campaign not found'}), 404
            
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
@app.route('/api/collection-drives', methods=['GET'])
def get_all_campaigns():
    import collection_drive_analytics
    # This must return the list of campaigns from your JSON file
    data = collection_drive_analytics.get_all_campaigns_overview()
    return jsonify(data)
@app.route('/api/collection-drives', methods=['GET'])
def api_get_campaigns():
    try:
        import collection_drive_analytics
        # This function must exist in collection_drive_analytics.py
        data = collection_drive_analytics.get_all_campaigns_overview()
        return jsonify(data)
    except Exception as e:
        print(f"API Error: {e}")
        return jsonify([])
def initialize_app():
    """Initialize application on startup"""
    logger.info("=" * 70)
    logger.info("Initializing Smart Waste Classifier...")
    logger.info("=" * 70)
    
    # Create required directories
    os.makedirs('static/uploads', exist_ok=True)
    os.makedirs('static/results', exist_ok=True)
    
    # Initialize database
    if DATABASE_AVAILABLE:
        try:
            initialize_database()
            logger.info("[OK] Database initialized")
        except Exception as e:
            logger.error(f"Database init error: {e}")
    
    # Load models
    if not MODELS_LOADED:
        logger.warning("[!] YOLO models not loaded")
    
    # Log module availability
    logger.info(f"Analytics: {'[OK]' if ANALYTICS_AVAILABLE else '[X]'}")
    
   
    logger.info(f"Waste Reports: {'[OK]' if WASTE_REPORTS_AVAILABLE else '[X]'}")
    logger.info("=" * 70)
    
    # Print server info
    print()
    print("=" * 70)
    print("SMART WASTE CLASSIFIER - PRODUCTION READY")
    print("=" * 70)
    print()
    print("Server Configuration:")
    print(f"   URL: http://0.0.0.0:5000")
    print(f"   Debug: {app.debug}")
    print()
    print("Available Pages:")
    print("   Landing: http://localhost:5000/")
    print("   Register: http://localhost:5000/register")
    print("   Login: http://localhost:5000/login")
    print("   User Dashboard: http://localhost:5000/user-dashboard")
    print("   NGO Dashboard: http://localhost:5000/ngo-dashboard")
    print("   Report Waste: http://localhost:5000/report-waste")
    print("   Main App: http://localhost:5000/dashboard")
    print("   Analytics: http://localhost:5000/analytics")
    print()
    print("System Status:")
    print(f"   Database: {'[OK] Ready' if DATABASE_AVAILABLE else '[X] Not Available'}")
    print(f"   Models: {'[OK] Loaded' if MODELS_LOADED else '[X] Not Found'}")
    print(f"   Analytics: {'[OK] Enabled' if ANALYTICS_AVAILABLE else '[X] Disabled'}")
    print(f"   Waste Reports: {'[OK] Enabled' if WASTE_REPORTS_AVAILABLE else '[X] Disabled'}")
    print("=" * 70)
    print()

# ============================================================================
# RUN APPLICATION
# ============================================================================

if __name__ == '__main__':
    initialize_app()
    app.run(host='0.0.0.0', port=5000, debug=True)