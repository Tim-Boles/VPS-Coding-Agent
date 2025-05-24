import google.generativeai as genai
from google.generativeai import types
from google.adk.agents import Agent as ADK_Agent
from google.adk.tools import FunctionTool
from google.adk.sessions import InMemorySessionService
from google.adk.runners import Runner
from langchain.vectorstores import FAISS 

import os
import logging
from pathlib import Path
import json
from prompts import return_instruction_prompt
from vector_db_manager import LocalVectorSearchTool, VectorDBLoader

# Requires: PyPDF2
try:
    from PyPDF2 import PdfReader
    from PyPDF2.errors import PdfReadError as OriginalPdfReadError # Renamed for clarity and to avoid direct use
    # PasswordRequiredError will be imported directly in the function where it's used.
    PYPDF2_INSTALLED = True
    logging.info("PyPDF2 and necessary components (PdfReader, OriginalPdfReadError) imported successfully for PDF processing.")
except ImportError as e:
    PYPDF2_INSTALLED = False
    logging.error(f"Failed to import PyPDF2 components (PdfReader or OriginalPdfReadError) at module load time: {e}. PDF processing will be disabled.", exc_info=True)

# --- Configuration ---
# Configure basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(module)s - %(funcName)s - %(message)s')

# Define a workspace for the agent's file operations
# Files will be read/written here, relative to the /app directory in the container
AGENT_FILES_WORKSPACE = Path("agent_files") # Changed to be relative to /app for simplicity in Docker
AGENT_VECTOR_DB = Path("agent_files/vector_db")
DEFAULT_MODEL_NAME = 'gemini-2.0-flash'

# --- Workspace Initialization ---
try:
    # When running in Docker, WORKDIR is /app. So this creates /app/agent_files
    # Ensure the workspace directory exists when the agent module is loaded.
    # If /app is not writable by the user running the script, this will fail.
    # Gunicorn usually runs as root by default unless configured otherwise.
    AGENT_FILES_WORKSPACE.mkdir(parents=True, exist_ok=True)
    AGENT_VECTOR_DB.mkdir(parents=True, exist_ok=True)
    logging.info(f"Agent file workspace initialized at: {AGENT_FILES_WORKSPACE.resolve()}")
    logging.info(f"Agent file workspace initialized at: {AGENT_VECTOR_DB.resolve()}")
except Exception as e:
    logging.error(f"Could not create agent workspace at {AGENT_FILES_WORKSPACE.resolve()}: {e}. File operations may fail.")
    logging.error(f"Could not create agent workspace at {AGENT_VECTOR_DB.resolve()}: {e}. File operations may fail.")

# --- Gemini Model Interaction ---
async def initialize_gemini_model(user_id: int, api_key: str = None) -> Runner | None:
    """
    Configures and initializes the Gemini generative model.
    Args:
        api_key (str, optional): The Gemini API key.
                                 If not provided, it attempts to read from
                                 the GEMINI_API_KEY environment variable.
    Returns:
        adk.agents.Agent | None: An initialized agent instance if successful, None otherwise.
    """
    # Handle api_key and model configuration
    if api_key is None:
        api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        logging.error("Gemini API key not found. Provide it as an argument or set GEMINI_API_KEY env variable.")
        return None

    model_name_to_use = os.getenv("GEMINI_MODEL_NAME", DEFAULT_MODEL_NAME)
    logging.info(f"Attempting to initialize Gemini model: {model_name_to_use}")

    # Handle Vector DB init
    try:
        vector_search = LocalVectorSearchTool(AGENT_VECTOR_DB)
        vector_loader = VectorDBLoader()
        local_faiss_search = FunctionTool(func=LocalVectorSearchTool.run_vector_search)
    except Exception as e:
        logging.error(f"💥 An error occurred during Vector DB initialization: {e}")
        return None
    
    # Handle ADK service init
    try:
        current_service = InMemorySessionService()
        session = await current_service.create_session(
            app_name="my-gemini-web-app",
            user_id=user_id,
            session_id="001"
        )
    except Exception as e:
        logging.error(f"💥 An error occurred during Vector DB initialization: {e}")
        return None
    
    try:
        root_agent = ADK_Agent(
            name = "rag_agent",
            model = model_name_to_use,
            description=(
                "Agent to answer questions about the content available on our website. It uses a Vertex DB and RAG setup to give the most context possible."
            ),
            instruction=(
                return_instruction_prompt()
            ),
            tools=[local_faiss_search]
        )
        runner = Runner(
            agent=root_agent, # The agent we want to run
            app_name="my-gemini-web-app",   # Associates runs with our app
            session_service=current_service # Uses our session manager
        )
        logging.info(f"🤖 Gemini AI Model '{model_name_to_use}' initialized successfully with system instruction.")
        return runner
    except Exception as e:
        logging.error(f"💥 An error occurred during Gemini model '{model_name_to_use}' initialization: {e}")
        return None


async def get_gemini_response(agent_runner: Runner , user_message: str, user_id: int, session_id: str="001") -> str | None:
    """
    Sends a message to the Gemini model, handles potential tool calls, and returns its final text response.
    Manages chat history implicitly via the 'chat' object.
    Args:
        model: The initialized Gemini GenerativeModel instance.
        user_message: The message from the user.
        chat_history: Optional list of previous chat messages for context.
                      Format: [{'role': 'user'/'model', 'parts': ['text']}]
    Returns:
        The model's final text response, or None if an error occurs.
    """
    if not agent_runner:
        logging.error("Runner not provided to get_gemini_response.")
        return None

    logging.info(f"User message: '{user_message[:100]}...'")
    content = types.ContentDict(role="user", parts=[types.PartDict(text=user_message)])
    final_response_text = "Agent did not produce a final response."

    async for event in agent_runner.run_async(user_id=user_id, session_id=session_id, new_message=content):

        # Key Concept: is_final_response() marks the concluding message for the turn.
      if event.is_final_response():
            if event.content and event.content.parts:
               # Assuming text response in the first part
               final_response_text = event.content.parts[0].text
            elif event.actions and event.actions.escalate: # Handle potential errors/escalations
               final_response_text = f"Agent escalated: {event.error_message or 'No specific message.'}"
            # Add more checks here if needed (e.g., specific error codes)
            break # Stop processing events once the final response is found
      
    return final_response_text


