# Gemini AI Agent with File Interaction Tools

This project is a web-based AI agent powered by Google's Gemini model. It provides a chat interface for users to interact with the AI, and includes tools that allow the agent to read and write text files within its containerized environment. The application is built with Python, Flask, and the Google Generative AI SDK, and is designed to be deployed using Docker.

## Features

* **Web-based Chat Interface:** Clean and simple UI for interacting with the Gemini AI.
* **Gemini Model Integration:** Leverages the power of Google's Gemini models for generating responses.
* **File System Tools:**
    * **Read Text Files:** The agent can read the content of specified text files from a designated workspace within its container.
    * **Write Text Files:** The agent can write or overwrite text content to specified files in its workspace.
* **Dockerized Deployment:** Easy to build and deploy using Docker, ensuring a consistent environment.
* **Configurable:** API keys and model names can be configured via environment variables.
* **Basic Path Safety:** File operations are restricted to a specific subdirectory (`/app/agent_files`) to mitigate path traversal risks.

## How It Works

The application consists of several key components:

1.  **`app.py` (Flask Application):**
    * Serves the main HTML page (`index.html`) for the chat interface.
    * Provides an API endpoint (`/ask`) that receives user messages from the frontend.
    * Forwards user messages to the `agent.py` module to get a response from the Gemini model.
    * Returns the AI's response (or error messages) to the frontend as JSON.

2.  **`agent.py` (Gemini Agent Logic):**
    * **Model Initialization:** Initializes the Gemini Generative Model using an API key (from environment variables).
    * **Tool Definition:** Defines the `read_text_file` and `write_text_file` tools with their schemas for the Gemini model.
    * **File Operations:** Contains the Python functions that perform the actual file reading and writing within a sandboxed directory (`/app/agent_files`). Includes path safety checks.
    * **Response Generation (`get_gemini_response`):**
        * Sends the user's message to the Gemini model.
        * Handles function calls if the model decides to use one of the file tools.
        * Executes the corresponding Python function for the tool.
        * Sends the tool's output back to the model.
        * Receives the final text response from the model and returns it to `app.py`.
        * Includes error handling for blocked prompts and other API issues.

3.  **`index.html` (Frontend):**
    * A single-page HTML application providing the chat UI.
    * Uses Tailwind CSS for styling.
    * JavaScript handles:
        * Sending user messages to the `/ask` backend endpoint.
        * Displaying user messages, AI responses, loading indicators, and error messages in the chat box.

4.  **`Dockerfile`:**
    * Defines the steps to build a Docker image for the application.
    * Uses a Python base image, installs dependencies from `requirements.txt`, copies the application code, and sets up Gunicorn as the WSGI server to run the Flask app.

5.  **`requirements.txt`:**
    * Lists the Python dependencies required for the project (e.g., Flask, google-generativeai, gunicorn).

## Project File Structure


.
├── Dockerfile              # Docker image definition
├── agent.py                # Gemini agent logic, tool definitions, file operations
├── app.py                  # Flask web application
├── requirements.txt        # Python dependencies
├── static/
│   └── style.css           # (Optional) Custom CSS if not solely relying on Tailwind via CDN
└── templates/
└── index.html          # Main HTML page for the chat interface
*(Note: The `agent_files` directory will be created inside the container at `/app/agent_files` when the agent runs and attempts to use file tools.)*

## Setup and Running the Application

### Prerequisites

* Docker installed and running on your system.
* A Gemini API Key from Google AI Studio.

### 1. Clone the Repository (or Create Files)

Ensure all the project files (`Dockerfile`, `agent.py`, `app.py`, `requirements.txt`, `templates/index.html`, `static/style.css` if used) are in a single directory.

### 2. Create `requirements.txt`

Make sure your `requirements.txt` file contains at least:

```txt
Flask
google-generativeai
gunicorn

3. Build the Docker Image
Navigate to the project's root directory in your terminal and run:
docker build -t gemini-ai-agent .

You can replace gemini-ai-agent with your preferred image name.
4. Run the Docker Container
Run the built image as a container:
docker run -d -p 5000:5000 \
  -e GEMINI_API_KEY="YOUR_ACTUAL_GEMINI_API_KEY" \
  -e GEMINI_MODEL_NAME="gemini-1.5-flash-latest" \  # Optional, defaults to gemini-1.5-flash-latest
  --name my-gemini-app \
  gemini-ai-agent

 * Replace "YOUR_ACTUAL_GEMINI_API_KEY" with your real Gemini API key.
 * -d: Runs the container in detached mode (in the background).
 * -p 5000:5000: Maps port 5000 on your host machine to port 5000 inside the container (where Gunicorn is listening). You can change the host port if needed (e.g., -p 80:5000 to map to host port 80).
 * -e GEMINI_API_KEY: Sets the environment variable for the API key.
 * -e GEMINI_MODEL_NAME: (Optional) Sets the environment variable for the Gemini model name. If not provided, agent.py uses a default.
 * --name my-gemini-app: Assigns a recognizable name to your running container.
5. Access the Application
Open your web browser and navigate to http://localhost:5000 (or http://<your_vps_ip>:5000 if running on a VPS and the port is open).
How to Use
 * Chatting: Type your message in the input field and click "Send" or press Enter. The AI's response will appear in the chatbox.
 * Using File Tools: You can ask the agent to perform file operations. For example:
   * "Write 'Hello from Gemini!' to a file named greeting.txt."
   * "Can you save this conversation to a file called chat_summary.md?"
   * "Read the content of greeting.txt and tell me what it says."
   * "Create a Python script that prints 'Hello, World!' and save it as hello_world.py."
   The agent will use its tools to interact with files in the /app/agent_files/ directory inside the container.
Inspecting Files in the Container (for Developers)
If you need to see the files the agent is creating/modifying:
 * Find your container ID or name: docker ps
 * Access a shell in the container: docker exec -it <container_id_or_name> bash
 * Navigate to the workspace: cd /app/agent_files
 * List files: ls -l
 * View file content: cat <filename>
Logging
The application uses Python's logging module. Docker container logs can be viewed using:
docker logs <container_id_or_name>

For continuous logs:
docker logs -f <container_id_or_name>

Potential Future Enhancements
 * Persistent Chat History: Implement session management to allow multi-turn conversations where the AI remembers previous interactions across separate /ask requests.
 * More Advanced File Tools:
   * List files in the workspace.
   * Delete files.
   * Append to files.
   * Edit specific parts of files (more complex).
 * User Authentication: If deploying in a multi-user environment.
 * Streaming Responses: For a more interactive feel, implement streaming of AI responses.
 * Configuration for Workspace Path: Allow the AGENT_FILES_WORKSPACE to be configured via an environment variable.
 * Resource Limits for File Tools: Implement checks to prevent the agent from creating excessively large files or too many files.
This README provides a good starting point. Feel free to adapt and expand it as your project evolves!

