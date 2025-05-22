Gemini AI Agent with User Authentication & File InteractionThis project is a web-based AI agent powered by Google's Gemini model. It provides a secure chat interface for registered users to interact with the AI. The application features user registration, login, and session management, and includes tools that allow the authenticated agent to read and write text files within its containerized environment. The application is built with Python, Flask (using Flask-Login for authentication, Flask-SQLAlchemy for database, and Flask-WTF for forms), and the Google Generative AI SDK. It's designed for Dockerized deployment.FeaturesUser Authentication System:User registration and login.Secure password hashing.Session management using Flask-Login.Protected routes: Only authenticated users can access the chat interface and file operation tools.Web-based Chat Interface: Clean and simple UI for interacting with the Gemini AI, now personalized for logged-in users.Gemini Model Integration: Leverages the power of Google's Gemini models for generating responses.File System Tools (for authenticated users):Read Text Files: The agent can read the content of specified text files from a designated workspace.Write Text Files: The agent can write or overwrite text content to specified files in its workspace.Database Integration: Uses SQLite via Flask-SQLAlchemy to store user credentials.Dockerized Deployment: Easy to build and deploy using Docker, ensuring a consistent environment.Configurable: API keys, secret keys, and model names are configured via environment variables.Basic Path Safety: File operations are restricted to a specific subdirectory (/app/agent_files) within the container.How It WorksThe application consists of several key components:app.py (Flask Application):Manages user authentication (registration, login, logout) using Flask-Login.Defines the User model using Flask-SQLAlchemy for storing credentials in a SQLite database.Handles forms using Flask-WTF (e.g., for login and registration).Serves HTML templates for different pages (welcome, chat, login, registration).Provides API endpoints (e.g., /ask, /list_files, /view_file) that are protected and require authentication.Forwards user messages from authenticated sessions to the agent.py module.Includes a CLI command flask create_db to initialize the user database.agent.py (Gemini Agent Logic):Handles model initialization, tool definition, file operations, and response generation.HTML Templates (templates/ directory):base.html: Base template providing common structure, navigation (dynamic based on auth status), and flashed messages.index.html: Welcome/landing page.login.html: User login page.register.html: User registration page.chat_interface.html: The main chat UI for authenticated users.Uses Tailwind CSS for styling.Dockerfile: Defines the image build process for Docker.requirements.txt:Lists Python dependencies, now including Flask-Login, Flask-SQLAlchemy, Flask-WTF, and email_validator.Project File Structure.
├── Dockerfile              # Docker image definition
├── agent.py                # Gemini agent logic, tool definitions, file operations
├── app.py                  # Flask web application with authentication
├── requirements.txt        # Python dependencies
├── static/
│   └── style.css           # Custom CSS
├── templates/
│   ├── base.html           # Base HTML structure
│   ├── chat_interface.html # Chat UI for authenticated users
│   ├── index.html          # Welcome/landing page
│   ├── login.html          # User login page
│   └── register.html       # User registration page
└── .gitignore              # Specifies intentionally untracked files
└── entrypoint.sh           # (Optional) For pre-start commands like DB init
(Note: The agent_files directory will be created inside the container at /app/agent_files. The user database users.db will be created inside /app/instance/ within the container. Both should be mapped to Docker volumes for persistence.)Setup and Running the ApplicationPrerequisitesDocker installed and running on your system.A Gemini API Key from Google AI Studio.A strong, randomly generated Flask Secret Key.1. Clone the Repository (or Create Files)Ensure all project files are in your project directory.2. Create/Update .gitignoreEnsure your .gitignore prevents committing secrets, virtual environments, instance data, and database files. Example:instance/
*.db
*.sqlite3
__pycache__/
*.py[cod]
.env
venv/
.venv/
# any other OS or editor specific files
3. Create/Update requirements.txtMake sure it includes:Flask
Flask-Login
Flask-SQLAlchemy
Flask-WTF
Werkzeug
email_validator
gunicorn
google-generativeai
# google-adk # if used
4. Build the Docker ImageNavigate to the project's root directory and run:docker build -t gemini-web-agent .
5. Prepare Host Directories for VolumesCreate directories on your host machine (VPS) to store persistent data:# Example using /srv (adjust paths as needed)
sudo mkdir -p /srv/gemini_web_agent/instance
sudo mkdir -p /srv/gemini_web_agent/agent_files
# Ensure Docker can write to these, adjust permissions if necessary
# sudo chown -R <your_user>:<your_group> /srv/gemini_web_agent # If running Docker as non-root or container as non-root
6. Run the Docker ContainerRun the built image as a container, providing necessary environment variables and volume mounts:docker run -d -p <HOST_PORT>:5000 \
  -e SECRET_KEY="YOUR_ACTUAL_FLASK_SECRET_KEY" \
  -e GEMINI_API_KEY="YOUR_ACTUAL_GEMINI_API_KEY" \
  -e GEMINI_MODEL_NAME="gemini-1.5-flash-latest" \
  -v /srv/gemini_web_agent/instance:/app/instance \
  -v /srv/gemini_web_agent/agent_files:/app/agent_files \
  --name my-gemini-web-app \
  gemini-web-agent
Replace <HOST_PORT> with the port you want to access the app on your VPS (e.g., 80, 8001).Replace placeholders for SECRET_KEY and GEMINI_API_KEY with your actual keys.Adjust host paths for volumes (/srv/gemini_web_agent/...) if you chose different locations.7. Initialize the Database (First Run)After the container starts, execute the database initialization command:docker exec -it my-gemini-web-app flask create_db
You should see a confirmation that tables were created.8. Access the ApplicationOpen your web browser and navigate to http://<your_vps_ip>:<HOST_PORT>. You should see the welcome page, from which you can register and log in.How to UseRegister/Login: Create an account or log in if you already have one.Chatting: Once logged in, navigate to the chat page. Type your message and interact with the AI.Using File Tools: Actions are now tied to the authenticated user session.Inspecting Files in the Container / Logs(This section from your previous README can remain largely the same.)# Find your container ID or name
docker ps

# Access a shell in the container
docker exec -it <container_id_or_name> bash

# Navigate to the workspace
cd /app/agent_files
# Or the instance folder for the database
cd /app/instance

# List files
ls -l

# View file content
cat <filename>

# View Docker container logs
docker logs <container_id_or_name>

# For continuous logs
docker logs -f <container_id_or_name>
Potential Future EnhancementsUser-Specific File Workspaces: Currently, agent_files is shared. For a true multi-user experience, each user's files should be isolated (e.g., /app/agent_files/<user_id>/).More Robust Session Management: Explore server-side sessions if needed for scalability beyond Flask's default client-side sessions.Database Migrations: For schema changes after initial setup, use a tool like Flask-Migrate (Alembic).Streaming AI Responses.Configuration for Workspace Path via environment variable.Resource Limits for File Tools.