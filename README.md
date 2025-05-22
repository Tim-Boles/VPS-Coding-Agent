# Gemini AI Chat Web Application

## Description

This is a web-based chat application that allows users to interact with Google's Gemini AI. Users can register, log in, and engage in conversations with the AI. The application also provides a workspace where users can view files that the AI can interact with.

## Features

*   User registration and login
*   Chat interface for interacting with Gemini AI
*   AI interaction powered by the Gemini API
*   Ability to list and view files in the AI's workspace

## Technologies Used

*   Python
*   Flask
*   Gemini API
*   SQLAlchemy
*   Docker

## Project Structure

*   `app.py`: The main Flask application file. It handles routing, user authentication (registration, login, logout), request handling, and initializes the application. It defines the User model using Flask-SQLAlchemy for storing credentials.
*   `agent.py`: Contains the logic for interacting with the Gemini AI model, including model initialization, tool definition, and response generation.
*   `models.py`: (Currently, the User model is defined in `app.py`. If more models are added, they might be moved here.)
*   `templates/`: Contains HTML templates for rendering web pages (e.g., `index.html`, `login.html`, `register.html`, `chat_interface.html`).
*   `static/`: Stores static assets like CSS, JavaScript, and images.
*   `Dockerfile`: Used to build a Docker image for the application.
*   `requirements.txt`: Lists the Python dependencies for the project.

## Setup and Running the Application

### Prerequisites

*   Python 3.8 or higher
*   pip (Python package installer)
*   Git
*   Docker (optional, for Docker-based setup)

### Steps

1.  **Clone the repository:**
    ```bash
    git clone <repository-url>
    cd <repository-directory>
    ```

2.  **Set up a Python virtual environment:**
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows, use `venv\Scripts\activate`
    ```

3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Set environment variables:**
    Create a `.env` file in the root directory of the project and add the following variables:
    ```env
    SECRET_KEY='your_very_secret_flask_key'
    GEMINI_API_KEY='your_gemini_api_key'
    ```
    Replace `'your_very_secret_flask_key'` and `'your_gemini_api_key'` with your actual keys. The application uses SQLite, and the database file is hardcoded in `app.py` to be stored at `instance/users.db`. Ensure the `instance` folder is created (Flask usually handles this) or create it manually in the root of your project.

5.  **Initialize the database:**
    If you have a Flask CLI command for database creation (e.g., `flask create_db` defined in `app.py`):
    ```bash
    flask create_db
    ```
    Alternatively, you might need to initialize it via a Python script or ORM-specific commands if `create_db` is not available.

6.  **Run the Flask development server:**
    ```bash
    flask run
    ```
    The application will typically be accessible at `http://127.0.0.1:5000/`.

### Running with Gunicorn (Production)

For a more production-ready setup, use a WSGI server like Gunicorn:
```bash
gunicorn -w 4 'app:app' # Assuming your Flask app instance is named 'app' in 'app.py'
```

### Running with Docker

1.  **Build the Docker image:**
    ```bash
    docker build -t gemini-chat-app .
    ```

2.  **Run the Docker container:**
    ```bash
    docker run -p 5000:5000 \
      -e SECRET_KEY='your_very_secret_flask_key' \
      -e GEMINI_API_KEY='your_gemini_api_key' \
      -e DATABASE_URL='sqlite:///instance/users.db' \
      -v $(pwd)/instance:/app/instance \
      # Add other volume mounts if needed, e.g., for agent_files
      # -v $(pwd)/agent_files:/app/agent_files \
      --name gemini-chat-container \
      gemini-chat-app
    ```
    Make sure to replace the environment variable placeholders with your actual values. The volume mount `$(pwd)/instance:/app/instance` ensures database persistence if using SQLite in the `instance` folder.

## API Endpoints

*   `/register` (POST): Registers a new user.
*   `/login` (POST, GET): Logs in an existing user (GET to display form, POST to submit).
*   `/logout` (GET): Logs out the current user.
*   `/chat` (GET): Renders the chat page. (Protected: Requires login)
*   `/ask` (POST): Sends a message to the AI. (Protected: Requires login, called by chat UI)
*   `/list_files` (GET): Displays the files in the AI's workspace. (Protected: Requires login)
*   `/view_file/<filename>` (GET): Displays the content of a specific file in the workspace. (Protected: Requires login)

## Contributing

Contributions are welcome! If you'd like to contribute, please follow these steps:
1.  Fork the repository.
2.  Create a new branch (`git checkout -b feature/your-feature-name`).
3.  Make your changes and commit them (`git commit -m 'Add some feature'`).
4.  Push to the branch (`git push origin feature/your-feature-name`).
5.  Open a Pull Request.

Please ensure your code follows the project's coding style and includes tests for new features.

## License

This project is licensed under the MIT License. See the `LICENSE` file for details. (You will need to create a `LICENSE` file with the MIT License text if you choose this license).