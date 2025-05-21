# Gemini Terminal AI Agent

A simple, Dockerized terminal-based AI agent that uses the Google Gemini API to provide interactive chat capabilities.

## Overview

This project allows you to run a conversational AI agent directly in your terminal. It connects to the Gemini API to understand and respond to your prompts. The entire application is containerized using Docker for easy setup and deployment.

## Current Features

* **Interactive Terminal Chat**: Communicate with the Gemini model in a conversational style.
* **Gemini API Integration**: Leverages the power of Google's Gemini models for responses.
* **Dockerized**: Easy to build and run as a Docker container.
* **Secure API Key Handling**: Expects the Gemini API key to be passed as an environment variable at runtime, not stored in the image.

## Prerequisites

* [Docker](https://www.docker.com/get-started) installed on your system.
* A Google Gemini API Key. You can obtain one from [Google AI Studio](https://ai.google.dev/).

## Setup and Running with Docker

1.  **Clone the Repository (if you haven't already):**
    ```bash
    git clone [https://github.com/your-username/gemini-terminal-agent.git](https://github.com/your-username/gemini-terminal-agent.git)
    cd gemini-terminal-agent
    ```

2.  **Build the Docker Image:**
    ```bash
    docker build -t gemini-terminal-agent .
    ```

3.  **Run the Docker Container:**
    Replace `"your_actual_gemini_api_key_here"` with your actual Gemini API key.
    ```bash
    docker run -it --rm \
      -e GEMINI_API_KEY="your_actual_gemini_api_key_here" \
      --name my-gemini-agent \
      gemini-terminal-agent
    ```
    You can also pass the API key as a command-line argument to the script if preferred:
    ```bash
    docker run -it --rm \
      --name my-gemini-agent \
      gemini-terminal-agent --api_key "your_actual_gemini_api_key_here"
    ```

4.  **Interact with the Agent:**
    Once the container is running, you can start typing your prompts in the terminal. Type `exit` or `quit` to end the session.

## Future Enhancements: Agent Development Kit (ADK) Integration

The next planned phase for this project is to integrate the **Google Agent Development Kit (ADK)**. This will enable more sophisticated agent capabilities, such as:

* **Tool Usage**: Allowing the agent to use external tools and APIs to perform actions or retrieve information.
* **Advanced Orchestration**: Building more complex conversational flows and agent behaviors.
* **State Management**: Implementing more robust memory and context handling for longer interactions.
* **Multi-Agent Systems**: Potentially creating systems where multiple specialized agents can collaborate.

The ADK integration will involve refactoring the current agent logic to leverage ADK's components (`Agent`, `Llm`, `Tool`, etc.) for a more structured and extensible architecture.

## API Key Management

**Important:** Your Gemini API key is sensitive.
* This application is designed to receive the API key via an environment variable (`GEMINI_API_KEY`) or a command-line argument when the Docker container is run.
* **Do not** hardcode your API key into the Python script or the Dockerfile.
* Ensure your `.gitignore` file correctly excludes any local `.env` files or other files where you might temporarily store the key during development.