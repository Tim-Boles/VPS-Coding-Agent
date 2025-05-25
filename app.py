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
import redis # ADDED: Redis import
import pickle # ADDED: Pickle import

# Configure basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

app = Flask(__name__)

# --- Redis Client Initialization ---
redis_host = os.getenv('REDIS_HOST', 'localhost')
redis_port = int(os.getenv('REDIS_PORT', 6379))
redis_db = int(os.getenv('REDIS_DB', 0))
redis_client = redis.Redis(host=redis_host, port=redis_port, db=redis_db)

try:
    if redis_client.ping():
        logging.info(f"Successfully connected to Redis at {redis_host}:{redis_port}, DB: {redis_db}")
    else:
        logging.error(f"Failed to connect to Redis at {redis_host}:{redis_port}, DB: {redis_db} - ping returned false")
except redis.exceptions.ConnectionError as e:
    logging.error(f"Redis connection error for {redis_host}:{redis_port}, DB: {redis_db}: {e}")
except Exception as e:
    logging.error(f"An unexpected error occurred during Redis connection test for {redis_host}:{redis_port}, DB: {redis_db}: {e}")

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


# user_runners = {} # REMOVED: Global dictionary replaced by Redis

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
    user_id = current_user.id # Get user_id before logging out
    logout_user()
    # Remove the user's agent_runner from Redis
    try:
        redis_key = f'runner:{user_id}'
        deleted_count = redis_client.delete(redis_key)
        if deleted_count > 0:
            logging.info(f"🧹 Cleaned up agent runner from Redis for user_id: {user_id} (key: {redis_key}).")
        else:
            logging.info(f"No agent runner found in Redis to clean up for user_id: {user_id} (key: {redis_key}).")
    except redis.exceptions.RedisError as e:
        logging.error(f"Redis error while deleting agent runner for user_id: {user_id} (key: {redis_key}): {e}")
    except Exception as e:
        logging.error(f"Unexpected error while deleting agent runner from Redis for user_id: {user_id} (key: {redis_key}): {e}")
    flash('You have been logged out. See you soon! 👋', 'info')
    return redirect(url_for('login'))

@app.route('/chat') # Renamed your main interaction page to /chat
@login_required   # Now requires login
async def chat_page():
    """Serves the main chat page, requires login."""
    logging.info(f"--- Entered /chat route for user_id: {current_user.id} ---") # REVERTED
    # global agent_runner # REMOVED global agent_runner
    
    logging.info(f"Attempting to initialize agent runner for user_id: {current_user.id}...") # REVERTED
    runner = await initialize_gemini_model(current_user.id)
    logging.info(f"Initialization result for user_id: {current_user.id}: Runner is {'NOT None' if runner else 'None'}. Runner object: {str(runner)}") # REVERTED

    redis_key = f'runner:{current_user.id}'
    if runner:
        try:
            serialized_runner = pickle.dumps(runner)
            redis_client.set(redis_key, serialized_runner, ex=14400) # 4 hours expiration
            logging.info(f"✅ Agent runner for user_id: {current_user.id} serialized and stored in Redis (key: {redis_key}). Runner object: {str(runner)}") # REVERTED, "TEST:" prefix removed
        except pickle.PicklingError as e:
            logging.error(f"🔴 Failed to serialize agent runner for user_id: {current_user.id} (key: {redis_key}): {e}", exc_info=True) # "TEST:" prefix removed
        except redis.exceptions.RedisError as e:
            logging.error(f"🔴 Redis error storing agent runner for user_id: {current_user.id} (key: {redis_key}): {e}", exc_info=True) # "TEST:" prefix removed
        except Exception as e:
            logging.error(f"🔴 Unexpected error storing agent runner for user_id: {current_user.id} (key: {redis_key}): {e}", exc_info=True) # "TEST:" prefix removed
    else:
        logging.error(f"🔴 ADK runner FAILED to initialize for user_id: {current_user.id}. No runner stored. initialize_gemini_model returned: {str(runner)}") # REVERTED to ERROR, "TEST:" prefix removed
        try:
            deleted_count = redis_client.delete(redis_key)
            if deleted_count > 0:
                logging.info(f"Removed existing runner from Redis for user_id: {current_user.id} (key: {redis_key}) due to failed initialization.") # REVERTED, "TEST:" prefix removed
            else:
                logging.info(f"No existing runner in Redis to remove for user_id: {current_user.id} (key: {redis_key}) after failed initialization.") # "TEST:" prefix removed
        except redis.exceptions.RedisError as e:
            logging.error(f"🔴 Redis error while deleting stale runner for user_id: {current_user.id} (key: {redis_key}): {e}", exc_info=True) # "TEST:" prefix removed
        except Exception as e:
            logging.error(f"🔴 Unexpected error deleting stale runner for user_id: {current_user.id} (key: {redis_key}): {e}", exc_info=True) # "TEST:" prefix removed
            
    logging.info(f"--- Exiting /chat route for user_id: {current_user.id} ---") # REVERTED
    return render_template('chat_interface.html', username=current_user.username) # Assuming chat interface is separate

@app.route('/ask', methods=['POST'])
@login_required # Secure this endpoint
async def ask():
    """Handles chat messages from the user and returns the AI's response."""
    agent_runner = None # Initialize to None
    redis_key = f'runner:{current_user.id}'
    logging.info(f"Attempting to retrieve agent runner for user_id: {current_user.id} from Redis (key: {redis_key}).")

    try:
        serialized_runner = redis_client.get(redis_key)
        if serialized_runner:
            try:
                agent_runner = pickle.loads(serialized_runner)
                logging.info(f"✅ Agent runner successfully retrieved and deserialized from Redis for user_id: {current_user.id} (key: {redis_key}). Runner type: {type(agent_runner)}")
            except pickle.UnpicklingError as e:
                logging.error(f"🔴 Failed to deserialize agent runner for user_id: {current_user.id} (key: {redis_key}): {e}. Removing invalid key.", exc_info=True)
                try:
                    redis_client.delete(redis_key)
                except redis.exceptions.RedisError as del_e:
                    logging.error(f"🔴 Redis error while deleting invalid runner key {redis_key} for user_id {current_user.id}: {del_e}", exc_info=True)
            except Exception as e:
                logging.error(f"🔴 Unexpected error during deserialization for user_id: {current_user.id} (key: {redis_key}): {e}", exc_info=True)
        else:
            logging.warning(f"⚠️ No agent runner found in Redis for user_id: {current_user.id} (key: {redis_key}).")
    except redis.exceptions.RedisError as e:
        logging.error(f"🔴 Redis error retrieving agent runner for user_id: {current_user.id} (key: {redis_key}): {e}", exc_info=True)
    except Exception as e:
        logging.error(f"🔴 Unexpected error retrieving agent runner from Redis for user_id: {current_user.id} (key: {redis_key}): {e}", exc_info=True)

    if not agent_runner:
        logging.warning(f"⚠️ Agent runner not available for user_id: {current_user.id} in /ask (key: {redis_key}). They might need to visit /chat first or an error occurred.")
        return jsonify({'error': 'Agent not initialized for this session. Please visit the chat page first.'}), 400

    try:
        user_message = request.json.get('message')
        if not user_message:
            return jsonify({'error': 'No message provided.'}), 400

        ai_response = await get_gemini_response(agent_runner, user_message, current_user.id)

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
