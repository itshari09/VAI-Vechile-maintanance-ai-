from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, validators
from wtforms.validators import DataRequired, Email, Regexp
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import os
from rdflib import Graph
import random

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Load ontology
g = Graph()
g.parse("vehicle_maintenance.owl")

# Real-life vehicle data (customizable)
VEHICLES = {
    "Bike_01": [
        {"task": "Oil Change", "interval": 5000},
        {"task": "Chain Lubrication", "interval": 1000}
    ],
    "Bike_02": [
        {"task": "Brake Check", "interval": 2000}
    ],
    "Car_01": [
        {"task": "Oil Change", "interval": 10000},
        {"task": "Tyre Rotation", "interval": 15000},
        {"task": "Battery Check", "interval": 20000}
    ],
    "Car_02": [
        {"task": "AC Service", "interval": 12000}
    ],
    "Bicycle_01": [
        {"task": "Chain Oil", "interval": 500},
        {"task": "Brake Adjustment", "interval": 1000}
    ]
}

class ServiceRecord(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    vehicle_name = db.Column(db.String(50), nullable=False)
    task = db.Column(db.String(100), nullable=False)
    last_odo = db.Column(db.Integer, default=0)

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=True)
    mobile = db.Column(db.String(15), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    vehicles = db.relationship('UserVehicle', backref='user', lazy=True)

class UserVehicle(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    vehicle_name = db.Column(db.String(50), nullable=False)
    odometer = db.Column(db.Integer, default=0)

    def set_password(self, password):
        self.password = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password, password)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

class LoginForm(FlaskForm):
    identifier = StringField('Email or Mobile Number', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')

class SignupForm(FlaskForm):
    name = StringField('Full Name', validators=[DataRequired()])
    mobile = StringField('Mobile Number', validators=[DataRequired(), Regexp(r'^\d{10}$', message="Mobile number must be 10 digits")])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Signup')

class ResetForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    answer = StringField('Answer', validators=[DataRequired()])
    new_password = PasswordField('New Password', validators=[DataRequired()])
    submit = SubmitField('Reset Password')

class ProfileForm(FlaskForm):
    name = StringField('Full Name', validators=[DataRequired()])
    mobile = StringField('Mobile Number', validators=[DataRequired(), Regexp(r'^\d{10}$', message="Mobile number must be 10 digits")])
    email = StringField('Email', validators=[DataRequired(), Email()])
    submit = SubmitField('Update Profile')

@app.route("/login", methods=["GET", "POST"])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        identifier = form.identifier.data
        # Check if identifier is email or mobile
        user = User.query.filter((User.email == identifier) | (User.mobile == identifier)).first()
        if user:
            if user.check_password(form.password.data):
                login_user(user)
                return redirect(url_for('index'))
            else:
                flash('Wrong password')
        else:
            flash('User not found')
    return render_template('login.html', form=form)

@app.route("/signup", methods=["GET", "POST"])
def signup():
    form = SignupForm()
    if form.validate_on_submit():
        if User.query.filter_by(mobile=form.mobile.data).first():
            flash('Mobile number already registered')
        elif User.query.filter_by(email=form.email.data).first():
            flash('Email already registered')
        else:
            user = User(name=form.name.data, mobile=form.mobile.data, email=form.email.data)
            user.set_password(form.password.data)
            db.session.add(user)
            db.session.commit()
            flash('Account created successfully')
            return redirect(url_for('login'))
    return render_template('signup.html', form=form)

@app.route("/reset", methods=["GET", "POST"])
def reset():
    form = ResetForm()
    question = session.get('math_question', '')
    if request.method == 'GET':
        # Generate question on GET
        a = random.randint(1, 9)
        b = random.randint(1, 9)
        question = f"What is {a} + {b}?"
        session['math_question'] = question
        session['math_answer'] = a + b
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and session.get('math_answer') and int(request.form.get('answer', 0)) == session['math_answer']:
            user.set_password(form.new_password.data)
            db.session.commit()
            session.pop('math_question', None)
            session.pop('math_answer', None)
            flash('Password reset successfully')
            return redirect(url_for('login'))
        flash('Invalid email or incorrect answer')
    return render_template('reset.html', form=form, question=question)

@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    form = ProfileForm()
    if form.validate_on_submit():
        # Check if mobile or email is already taken by another user
        existing_mobile = User.query.filter(User.mobile == form.mobile.data, User.id != current_user.id).first()
        existing_email = User.query.filter(User.email == form.email.data, User.id != current_user.id).first()
        if existing_mobile:
            flash('Mobile number already in use')
        elif existing_email:
            flash('Email already in use')
        else:
            current_user.name = form.name.data
            current_user.mobile = form.mobile.data
            current_user.email = form.email.data
            db.session.commit()
            flash('Profile updated successfully')
            return redirect(url_for('profile'))
    elif request.method == 'GET':
        form.name.data = current_user.name
        form.mobile.data = current_user.mobile
        form.email.data = current_user.email
    return render_template('profile.html', form=form)

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route("/", methods=["GET", "POST"])
@login_required
def index():
    tasks = []
    selected_vehicle = None
    user_vehicles = {uv.vehicle_name: uv for uv in current_user.vehicles}
    due_services = []
    serviced_status = {}

    # Get service records
    service_records = {f"{sr.vehicle_name}_{sr.task}": sr for sr in ServiceRecord.query.filter_by(user_id=current_user.id).all()}

    if request.method == "POST":
        if 'update_odo' in request.form:
            # Update odometer readings
            for vehicle in VEHICLES.keys():
                if request.form.get(f'check_{vehicle}'):
                    odo = request.form.get(f'odo_{vehicle}', 0)
                    try:
                        odo = int(odo)
                    except:
                        odo = 0
                    if vehicle in user_vehicles:
                        old_odo = user_vehicles[vehicle].odometer
                        user_vehicles[vehicle].odometer = odo
                        # Check for due services if odo increased
                        if odo > old_odo:
                            for task_info in VEHICLES[vehicle]:
                                task = task_info['task']
                                interval = task_info['interval']
                                key = f"{vehicle}_{task}"
                                last_odo = service_records.get(key, ServiceRecord(last_odo=0)).last_odo
                                if odo - last_odo >= interval:
                                    due_services.append(f"{vehicle}: {task} (Due at {last_odo + interval} km)")
                    else:
                        uv = UserVehicle(user_id=current_user.id, vehicle_name=vehicle, odometer=odo)
                        db.session.add(uv)
                elif vehicle in user_vehicles:
                    db.session.delete(user_vehicles[vehicle])
            db.session.commit()
            flash('Vehicle odometer readings updated')
            return redirect(url_for('index'))
        elif 'mark_serviced' in request.form:
            vehicle = request.form.get('service_vehicle')
            task = request.form.get('service_task')
            if vehicle and task and vehicle in user_vehicles:
                key = f"{vehicle}_{task}"
                if key in service_records:
                    service_records[key].last_odo = user_vehicles[vehicle].odometer
                else:
                    sr = ServiceRecord(user_id=current_user.id, vehicle_name=vehicle, task=task, last_odo=user_vehicles[vehicle].odometer)
                    db.session.add(sr)
                db.session.commit()
                flash(f'{task} for {vehicle} marked as serviced')
                return redirect(url_for('index'))
        else:
            # Check maintenance
            selected_vehicle = request.form.get("vehicle")
            if selected_vehicle and selected_vehicle in user_vehicles:
                tasks = [t['task'] for t in VEHICLES.get(selected_vehicle, [])]
                # Check status
                current_odo = user_vehicles[selected_vehicle].odometer
                for task_info in VEHICLES[selected_vehicle]:
                    task = task_info['task']
                    interval = task_info['interval']
                    key = f"{selected_vehicle}_{task}"
                    last_odo = service_records.get(key, ServiceRecord(last_odo=0)).last_odo
                    if current_odo - last_odo < interval:
                        serviced_status[task] = "Up to date"
                    else:
                        serviced_status[task] = f"Due (last serviced at {last_odo} km)"

    return render_template(
        "index.html",
        vehicles=VEHICLES.keys(),
        tasks=tasks,
        selected_vehicle=selected_vehicle,
        user_vehicles=user_vehicles,
        due_services=due_services,
        serviced_status=serviced_status,
        service_records=service_records
    )

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        # Add name column if not exists (migration for existing db)
        try:
            db.engine.execute("ALTER TABLE user ADD COLUMN name VARCHAR(150)")
        except:
            pass  # Column already exists
    app.run(debug=True)