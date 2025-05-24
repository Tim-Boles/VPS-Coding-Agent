from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, current_user, login_required
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField
from wtforms.validators import DataRequired, Email, EqualTo, Length
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from agent import initialize_gemini_model, get_gemini_response, AGENT_FILES_WORKSPACE
import os
import logging
from pathlib import Path

# Configure basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

app = Flask(__name__)

# --- Constants for File Upload ---
ALLOWED_EXTENSIONS = {'.txt', '.pdf'}
MAX_FILE_SIZE = 1 * 1024 * 1024 * 1024  # 1GB

# --- Configuration ---
app.config['SECRET_KEY'] = os.getenv("SECRET_KEY")
db_file_path = Path(app.instance_path) / 'users.db'
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_file_path.resolve()}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# --- Database & Login Manager Initialization ---
db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login' 
login_manager.login_message_category = 'info'

# --- User Model ---
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256)) # Increased length for future-proofing

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<User {self.username}>'

# --- Forms (using Flask-WTF) ---
class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    remember_me = BooleanField('Remember Me')
    submit = SubmitField('Login 🔑')

class RegistrationForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=3, max=80)])
    email = StringField('Email', validators=[DataRequired(), Email(), Length(max=120)])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField('Confirm Password',
                                     validators=[DataRequired(), EqualTo('password', message='Passwords must match.')])
    submit = SubmitField('Register 📝')

# --- Flask-Login User Loader ---
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# Initialize Gemini model when the app starts
agent_runner = None

# --- Routes ---
@app.route('/')
def index():
    """Serves the main page. It could be a welcome page or redirect to chat/dashboard."""
    if current_user.is_authenticated:
        # If logged in, maybe go to a dashboard or the chat directly
        return render_template('index.html', username=current_user.username) # Pass username to template
    return render_template('index.html') # Or a more generic landing page

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = RegistrationForm()
    if form.validate_on_submit():
        existing_user_email = User.query.filter_by(email=form.email.data).first()
        if existing_user_email:
            flash('That email address is already registered. Please log in.', 'warning')
            return redirect(url_for('login'))
        existing_user_username = User.query.filter_by(username=form.username.data).first()
        if existing_user_username:
            flash('That username is already taken. Please choose a different one.', 'warning')
            return redirect(url_for('register'))

        user = User(username=form.username.data, email=form.email.data)
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        flash('Congratulations, you are now a registered user! Please log in. 🎉', 'success')
        return redirect(url_for('login'))
    return render_template('register.html', title='Register', form=form)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index')) # Or a user-specific dashboard
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and user.check_password(form.password.data):
            login_user(user, remember=form.remember_me.data)
            next_page = request.args.get('next')
            flash(f'Welcome back, {user.username}! 👋', 'success')
            return redirect(next_page) if next_page else redirect(url_for('index'))
        else:
            flash('Login Unsuccessful. Please check email and password. 🧐', 'danger')
    return render_template('login.html', title='Login', form=form)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out. See you soon! 👋', 'info')
    return redirect(url_for('login'))

@app.route('/chat') # Renamed your main interaction page to /chat
@login_required   # Now requires login
async def chat_page():
    """Serves the main chat page, requires login."""
    global agent_runner = await initialize_gemini_model(current_user.id)

    if not global agent_runner:
        logging.error("🔴 ADK runner failed to initialize. The /ask endpoint will not work.")
    return render_template('chat_interface.html', username=current_user.username) # Assuming chat interface is separate

@app.route('/ask', methods=['POST'])
@login_required # Secure this endpoint
async def ask():
    """Handles chat messages from the user and returns the AI's response."""
    if not global agent_runner:
        return jsonify({'error': 'Gemini model not initialized. Check server logs.'}), 500

    try:
        user_message = request.json.get('message')
        if not user_message:
            return jsonify({'error': 'No message provided.'}), 400

        ai_response = await get_gemini_response(global agent_runner, user_message, current_user.id)

        if ai_response is None:
            return jsonify({'error': 'Failed to get response from AI. Please check server logs.'}), 500

        return jsonify({'reply': ai_response})

    except Exception as e:
        logging.error(f"💥 Error in /ask endpoint for user {current_user.id}: {e}")
        return jsonify({'error': 'An internal error occurred.'}), 500

@app.route('/list_files', methods=['GET'])
@login_required # Secure this endpoint
def list_agent_files():
    """Lists files in the agent's workspace. Now requires login."""
    return jsonify({'error': 'Could not list files due to an internal server error.'}), 500

@app.route('/view_file/<path:filename>', methods=['GET'])
@login_required 
def view_agent_file(filename):
    """Serves the content of a specific file from the agent's workspace. Now requires login."""
    return jsonify({'error': f'An unexpected error occurred while trying to read the file {filename}.'}), 500

# --- File Upload Route ---
@app.route('/upload_file', methods=['POST'])
@login_required
def upload_file():
    """Handles file uploads from the user."""
    if 'file' not in request.files:
        logging.warning(f"File upload attempt by {current_user.username} failed: No file part in request.")
        return jsonify({'error': 'No file part in the request.'}), 400

    file = request.files['file']

    if file.filename == '':
        logging.warning(f"File upload attempt by {current_user.username} failed: No selected file.")
        return jsonify({'error': 'No selected file.'}), 400

    _, ext = os.path.splitext(file.filename)
    if ext.lower() not in ALLOWED_EXTENSIONS:
        logging.warning(f"File upload attempt by {current_user.username} for '{file.filename}' failed: File type not allowed.")
        return jsonify({'error': 'File type not allowed. Only .txt and .pdf files are accepted.'}), 400

    # Check file size
    file.seek(0, os.SEEK_END)
    file_size = file.tell()
    file.seek(0)  # Reset pointer to the beginning of the file

    if file_size > MAX_FILE_SIZE:
        logging.warning(f"File upload attempt by {current_user.username} for '{file.filename}' failed: File too large ({file_size} bytes).")
        return jsonify({'error': f'File exceeds maximum size of 1GB.'}), 400

    try:
        filename = secure_filename(file.filename)
        # Ensure the AGENT_FILES_WORKSPACE directory exists (it should be created by agent.py, but good to be safe)
        Path(AGENT_FILES_WORKSPACE).mkdir(parents=True, exist_ok=True)
        save_path = Path(AGENT_FILES_WORKSPACE) / filename
        
        file.save(save_path)
        logging.info(f"File '{filename}' uploaded successfully by user {current_user.username} to {save_path}.")
        return jsonify({'message': f'File {filename} uploaded successfully.'}), 200
    except Exception as e:
        logging.error(f"💥 Error saving file '{filename}' for user {current_user.username}: {e}")
        return jsonify({'error': 'An error occurred while saving the file.'}), 500

# --- Database Initialization Command ---
@app.cli.command('create_db')
def create_db_command():
    """Creates the database tables."""
    # Ensure the instance folder exists.
    # app.instance_path will resolve to /app/instance if your app.py is in /app
    instance_folder = Path(app.instance_path)
    instance_folder.mkdir(parents=True, exist_ok=True)
    app.logger.info(f"Ensured instance folder exists at: {instance_folder.resolve()}")

    with app.app_context():
        db.create_all()
    print(f'Database tables created (or an attempt was made) for {app.config["SQLALCHEMY_DATABASE_URI"]}')
