from flask import Flask, render_template, request, jsonify, redirect, url_for, send_file, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_bcrypt import Bcrypt
from datetime import datetime, timedelta
import time
import random
import json
import csv
import io
import secrets
import os

app = Flask(__name__)

# --- CONFIGURATION ---
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'ai_cms.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = secrets.token_hex(16)

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# --- DATABASE MODELS ---

# --- DATABASE MODELS ---

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(120), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_admin = db.Column(db.Boolean, default=False)
    
    def set_password(self, password):
        self.password_hash = bcrypt.generate_password_hash(password).decode('utf-8')
    
    def check_password(self, password):
        return bcrypt.check_password_hash(self.password_hash, password)

class APIKey(db.Model):
    __tablename__ = 'api_keys'
    
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(64), unique=True, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    name = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_used = db.Column(db.DateTime)
    is_active = db.Column(db.Boolean, default=True)
    usage_count = db.Column(db.Integer, default=0)
    
    user = db.relationship('User', backref='api_keys')
    
    @staticmethod
    def generate_key():
        return secrets.token_hex(32)
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'key': self.key,
            'created_at': self.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            'last_used': self.last_used.strftime("%Y-%m-%d %H:%M:%S") if self.last_used else 'Never',
            'usage_count': self.usage_count,
            'is_active': self.is_active
        }

class APIEndpoint(db.Model):
    __tablename__ = 'api_endpoints'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    route = db.Column(db.String(100), nullable=False)
    model = db.Column(db.String(50), nullable=False)
    prompt = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    
    total_calls = db.Column(db.Integer, default=0)
    total_tokens = db.Column(db.Integer, default=0)
    total_cost = db.Column(db.Float, default=0.0)
    
    user = db.relationship('User', backref='endpoints')
    # Add cascade delete for logs
    logs = db.relationship('APILog', backref='endpoint', lazy=True, cascade='all, delete-orphan')
    
    def to_dict(self):
        return {
            'id': self.id,
            'route': self.route,
            'model': self.model,
            'prompt': self.prompt,
            'created_at': self.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            'is_active': self.is_active,
            'total_calls': self.total_calls,
            'total_tokens': self.total_tokens,
            'total_cost': round(self.total_cost, 4)
        }

class APILog(db.Model):
    __tablename__ = 'api_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    endpoint_id = db.Column(db.Integer, db.ForeignKey('api_endpoints.id', ondelete='CASCADE'), nullable=False)
    api_key_id = db.Column(db.Integer, db.ForeignKey('api_keys.id', ondelete='SET NULL'), nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    input_data = db.Column(db.Text)
    output_data = db.Column(db.Text)
    tokens_used = db.Column(db.Integer)
    latency = db.Column(db.Float)
    cost = db.Column(db.Float)
    status_code = db.Column(db.Integer, default=200)
    
    api_key = db.relationship('APIKey', backref='logs')
    
    def to_dict(self):
        return {
            'id': self.id,
            'endpoint_id': self.endpoint_id,
            'timestamp': self.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            'tokens_used': self.tokens_used,
            'latency': round(self.latency, 3),
            'cost': round(self.cost, 4),
            'status_code': self.status_code
        }

# --- LOGIN MANAGER ---
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- MOCK AI RESPONSE ---
def generate_mock_response(prompt, input_data):
    time.sleep(random.uniform(0.5, 1.5))
    return f"AI Response based on prompt: '{prompt[:30]}...' and input: {json.dumps(input_data)}"

# --- AUTH ROUTES ---

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        data = request.json if request.is_json else request.form
        username = data.get('username')
        password = data.get('password')
        
        user = User.query.filter_by(username=username).first()
        
        if user and user.check_password(password):
            login_user(user)
            if request.is_json:
                return jsonify({"status": "success", "message": "Login successful"})
            return redirect(url_for('dashboard'))
        
        if request.is_json:
            return jsonify({"status": "error", "message": "Invalid credentials"}), 401
        flash('Invalid username or password', 'error')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        data = request.json if request.is_json else request.form
        username = data.get('username')
        password = data.get('password')
        
        if User.query.filter_by(username=username).first():
            if request.is_json:
                return jsonify({"status": "error", "message": "Username exists"}), 400
            flash('Username already exists', 'error')
            return render_template('register.html')
        
        user = User(username=username)
        user.set_password(password)
        
        # First user becomes admin
        if User.query.count() == 0:
            user.is_admin = True
        
        db.session.add(user)
        db.session.commit()
        
        if request.is_json:
            return jsonify({"status": "success", "message": "Registration successful"})
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# --- FRONTEND ROUTES ---

@app.route('/')
@login_required
def dashboard():
    return render_template('index.html')

# --- CMS API ENDPOINTS ---

@app.route('/api/cms/create', methods=['POST'])
@login_required
def create_api():
    data = request.json
    
    existing = APIEndpoint.query.filter_by(route=data['route'], user_id=current_user.id).first()
    if existing:
        return jsonify({"status": "error", "message": "Route already exists"}), 400
    
    new_api = APIEndpoint(
        user_id=current_user.id,
        route=data['route'],
        model=data['model'],
        prompt=data['prompt']
    )
    
    db.session.add(new_api)
    db.session.commit()
    
    return jsonify({"status": "success", "message": "API Created Successfully", "api": new_api.to_dict()})

@app.route('/api/cms/list', methods=['GET'])
@login_required
def list_apis():
    apis = APIEndpoint.query.filter_by(user_id=current_user.id).all()
    return jsonify([api.to_dict() for api in apis])

@app.route('/api/cms/stats', methods=['GET'])
@login_required
def get_stats():
    apis = APIEndpoint.query.filter_by(user_id=current_user.id).all()
    
    total_calls = sum(api.total_calls for api in apis)
    total_tokens = sum(api.total_tokens for api in apis)
    total_cost = sum(api.total_cost for api in apis)
    
    return jsonify({
        "total_calls": total_calls,
        "total_tokens": total_tokens,
        "total_cost": round(total_cost, 4),
        "active_apis": len([api for api in apis if api.is_active])
    })

@app.route('/api/cms/logs', methods=['GET'])
@login_required
def get_logs():
    user_endpoint_ids = [api.id for api in APIEndpoint.query.filter_by(user_id=current_user.id).all()]
    logs = APILog.query.filter(APILog.endpoint_id.in_(user_endpoint_ids)).order_by(APILog.timestamp.desc()).limit(50).all()
    return jsonify([log.to_dict() for log in logs])

@app.route('/api/cms/delete/<int:api_id>', methods=['DELETE'])
@login_required
def delete_api(api_id):
    api = APIEndpoint.query.filter_by(id=api_id, user_id=current_user.id).first_or_404()
    db.session.delete(api)
    db.session.commit()
    return jsonify({"status": "success", "message": "API Deleted"})

@app.route('/api/cms/export', methods=['GET'])
@login_required
def export_logs():
    user_endpoint_ids = [api.id for api in APIEndpoint.query.filter_by(user_id=current_user.id).all()]
    logs = APILog.query.filter(APILog.endpoint_id.in_(user_endpoint_ids)).order_by(APILog.timestamp.desc()).all()
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Timestamp', 'Endpoint', 'Tokens', 'Latency', 'Cost', 'Status'])
    
    for log in logs:
        writer.writerow([
            log.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            log.endpoint.route,
            log.tokens_used,
            round(log.latency, 3),
            round(log.cost, 4),
            log.status_code
        ])
    
    output.seek(0)
    return send_file(
        io.BytesIO(output.getvalue().encode('utf-8')),
        mimetype='text/csv',
        as_attachment=True,
        download_name=f'api_logs_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
    )

# --- API KEY MANAGEMENT ---

@app.route('/api/cms/keys', methods=['GET'])
@login_required
def list_keys():
    keys = APIKey.query.filter_by(user_id=current_user.id).all()
    return jsonify([k.to_dict() for k in keys])

@app.route('/api/cms/keys', methods=['POST'])
@login_required
def create_key():
    data = request.json
    new_key = APIKey(
        user_id=current_user.id,
        key=APIKey.generate_key(),
        name=data.get('name', 'Unnamed Key')
    )
    db.session.add(new_key)
    db.session.commit()
    return jsonify({"status": "success", "key": new_key.key})

@app.route('/api/cms/keys/<int:key_id>', methods=['DELETE'])
@login_required
def delete_key(key_id):
    key = APIKey.query.filter_by(id=key_id, user_id=current_user.id).first_or_404()
    db.session.delete(key)
    db.session.commit()
    return jsonify({"status": "success", "message": "Key Deleted"})

@app.route('/api/cms/keys/<int:key_id>/toggle', methods=['POST'])
@login_required
def toggle_key(key_id):
    key = APIKey.query.filter_by(id=key_id, user_id=current_user.id).first_or_404()
    key.is_active = not key.is_active
    db.session.commit()
    return jsonify({"status": "success", "is_active": key.is_active})

# --- DYNAMIC USER API ENDPOINTS ---

@app.route('/user-api/<path:route>', methods=['GET', 'POST'])
def dynamic_endpoint(route):
    api_key = request.headers.get('X-API-Key') or request.args.get('api_key')
    
    target_api = APIEndpoint.query.filter_by(route=route, is_active=True).first()
    
    if not target_api:
        return jsonify({"error": "Endpoint not found"}), 404
    
    api_key_obj = None
    if api_key:
        api_key_obj = APIKey.query.filter_by(key=api_key, is_active=True).first()
        if not api_key_obj:
            return jsonify({"error": "Invalid API Key"}), 401
        
        api_key_obj.last_used = datetime.utcnow()
        api_key_obj.usage_count += 1
    
    start_time = time.time()
    input_data = request.json if request.is_json else request.args.to_dict()
    
    response_text = generate_mock_response(target_api.prompt, input_data)
    
    latency = time.time() - start_time
    tokens_used = len(response_text) // 4
    cost = (tokens_used / 1000) * 0.002
    
    target_api.total_calls += 1
    target_api.total_tokens += tokens_used
    target_api.total_cost += cost
    
    log = APILog(
        endpoint_id=target_api.id,
        api_key_id=api_key_obj.id if api_key_obj else None,
        input_data=json.dumps(input_data),
        output_data=response_text,
        tokens_used=tokens_used,
        latency=latency,
        cost=cost,
        status_code=200
    )
    
    db.session.add(log)
    db.session.commit()
    
    return jsonify({
        "response": response_text,
        "meta": {
            "model": target_api.model,
            "latency": round(latency, 3),
            "tokens": tokens_used,
            "cost": round(cost, 4)
        }
    })

# --- INITIALIZE DATABASE ---
def init_db():
    with app.app_context():
        db.create_all()
        
        if User.query.count() == 0:
            admin = User(username='admin', is_admin=True)
            admin.set_password('admin123')
            db.session.add(admin)
            db.session.commit()
            print("✅ Default admin created (username: admin, password: admin123)")
        
        print("✅ Database initialized!")

if __name__ == '__main__':
    init_db()
    app.run(debug=True, port=5000)