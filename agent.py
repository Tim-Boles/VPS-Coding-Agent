from google import genai
from google.genai import types
from google.adk.agents import Agent as ADK_Agent
from google.adk.tools import FunctionTool
from google.adk.sessions import InMemorySessionService
from google.adk.runners import Runner
from langchain_community.vectorstores import FAISS # UPDATED import
from langchain_google_genai import GoogleGenerativeAIEmbeddings # ADDED: Import for embeddings

import os
import logging
from pathlib import Path
import json
from prompts import return_instruction_prompt
# from vector_db_manager import LocalVectorSearchTool, VectorDBLoader # REMOVED LocalVectorSearchTool import
from vector_db_manager import VectorDBLoader # VectorDBLoader is still used for DB creation/updates

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

# --- Global Variables for FAISS Index and Embeddings ---
GLOBAL_FAISS_VSTORE = None
GLOBAL_EMBEDDINGS = None

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

# --- FAISS Index Initialization Function ---
def _initialize_global_vector_store():
    """Initializes global FAISS vector store and embeddings if they are not already initialized."""
    global GLOBAL_FAISS_VSTORE, GLOBAL_EMBEDDINGS

    if GLOBAL_EMBEDDINGS is None:
        try:
            # Ensure API key is available for embedding model
            if not os.getenv("GOOGLE_API_KEY"):
                logging.error("GOOGLE_API_KEY environment variable not set. Cannot initialize embeddings.")
                return
            GLOBAL_EMBEDDINGS = GoogleGenerativeAIEmbeddings(model="models/text-embedding-004")
            logging.info("Successfully initialized GLOBAL_EMBEDDINGS.")
        except Exception as e:
            logging.error(f"Failed to initialize GLOBAL_EMBEDDINGS: {e}", exc_info=True)
            return # If embeddings fail, we can't load or create the store.

    if GLOBAL_FAISS_VSTORE is None and GLOBAL_EMBEDDINGS is not None:
        faiss_index_file = AGENT_VECTOR_DB / "index.faiss"
        faiss_pkl_file = AGENT_VECTOR_DB / "index.pkl"

        if not AGENT_VECTOR_DB.exists():
            logging.warning(f"FAISS index directory {AGENT_VECTOR_DB} does not exist. Attempting to create.")
            try:
                AGENT_VECTOR_DB.mkdir(parents=True, exist_ok=True)
            except Exception as e_mkdir:
                logging.error(f"Could not create FAISS directory {AGENT_VECTOR_DB}: {e_mkdir}", exc_info=True)
                return # Cannot proceed if directory cannot be created.

        if faiss_index_file.exists() and faiss_pkl_file.exists():
            logging.info(f"FAISS index files found in {AGENT_VECTOR_DB}. Attempting to load.")
            try:
                GLOBAL_FAISS_VSTORE = FAISS.load_local(
                    folder_path=str(AGENT_VECTOR_DB),
                    embeddings=GLOBAL_EMBEDDINGS,
                    index_name="index",
                    allow_dangerous_deserialization=True
                )
                logging.info(f"Successfully loaded FAISS index into GLOBAL_FAISS_VSTORE from {AGENT_VECTOR_DB}")
            except Exception as e_load:
                logging.error(f"Failed to load FAISS index globally from {AGENT_VECTOR_DB}: {e_load}", exc_info=True)
                # GLOBAL_FAISS_VSTORE will remain None
        else:
            logging.warning(f"FAISS index files (index.faiss or index.pkl) not found in {AGENT_VECTOR_DB}. Attempting to initialize an empty vector store.")
            try:
                # Initialize an empty FAISS store
                # FAISS needs at least one document to be initialized, so we can't just create an empty one.
                # For now, we will log that it's not found and the LocalVectorSearchTool will have to handle it.
                # This behavior aligns with the original plan where LocalVectorSearchTool checks if vstore is None.
                # A more robust solution would be to create a dummy document and index it,
                # but that's beyond the current scope of just "loading".
                # The VectorDBLoader is designed to create from documents, not initialize an empty store directly.
                logging.info(f"FAISS index not found at {AGENT_VECTOR_DB}. GLOBAL_FAISS_VSTORE will remain None. Application may need to populate it first.")
                # If you have a mechanism to create an empty DB (e.g., via VectorDBLoader with no docs), call it here.
                # For example, if VectorDBLoader().initialize_vector_db can create an empty one:
                # temp_loader = VectorDBLoader()
                # if temp_loader.initialize_vector_db(AGENT_VECTOR_DB, GLOBAL_EMBEDDINGS, "index", docs=[]): # Assuming it can handle empty docs
                #     GLOBAL_FAISS_VSTORE = temp_loader.vstore
                #     logging.info("Initialized an empty FAISS index globally.")
                # else:
                #     logging.error("Failed to initialize an empty FAISS index.")
            except Exception as e_init_empty:
                logging.error(f"Exception during attempt to initialize an empty FAISS index for {AGENT_VECTOR_DB}: {e_init_empty}", exc_info=True)

# --- Local Vector Search Tool (moved into agent.py) ---
class LocalVectorSearchTool():
    name = "local_faiss_search"
    description = (
        "Searches a local FAISS vector store to find and retrieve text segments "
        "that are semantically similar to a given query. Useful for question answering "
        "over a local knowledge base or finding relevant information."
    )

    def __init__(self, index_path: Path = AGENT_VECTOR_DB): # index_path can be defaulted or passed
        _initialize_global_vector_store() # Ensure global objects are initialized

        self.embeddings = GLOBAL_EMBEDDINGS
        self.vstore = GLOBAL_FAISS_VSTORE
        self.index_path = index_path # Store for reference, though global is used

        if self.vstore is None:
            logging.error(f"LocalVectorSearchTool initialized for {self.index_path} but FAISS vstore (GLOBAL_FAISS_VSTORE) is not available globally. Search functionality will be impaired.")
            # Depending on strictness, could raise an error:
            # raise ValueError(f"FAISS vector store not loaded globally for {self.index_path}. Tool cannot operate.")
        else:
            logging.info(f"LocalVectorSearchTool initialized, using globally loaded FAISS index from {self.index_path}")

    def run_vector_search(self, query: str, k: int = 5) -> dict: # Added default k
        """
        Retrieves the top k text segments from the globally loaded FAISS vector store
        that are most semantically similar to the input query.
        """
        if self.vstore is None:
            logging.error("FAISS vstore is not loaded. Cannot perform vector search.")
            return {
                "status": "error",
                "error_message": "FAISS vector store not available. Cannot perform search."
            }

        if not isinstance(k, int) or k <= 0:
            return {
                "status": "error",
                "error_message": f"Invalid value for k: must be a positive integer, but got {k}."
            }
        
        if not self.embeddings:
            logging.error("Embeddings are not loaded. Cannot perform vector search.")
            return {
                "status": "error",
                "error_message": "Embeddings not available. Cannot perform search."
            }

        try:
            logging.info(f"Performing similarity search for query: '{query[:50]}...' with k={k}")
            docs = self.vstore.similarity_search(query, k=k)
            retrieved_contents = [d.page_content for d in docs]
            logging.info(f"Retrieved {len(retrieved_contents)} documents for query '{query[:50]}...'")
            return {
                "status": "success",
                "retrieved_documents": retrieved_contents
            }
        except Exception as e:
            logging.error(f"Error during FAISS similarity search for query '{query[:50]}...': {e}", exc_info=True)
            return {
                "status": "error",
                "error_message": f"An error occurred during vector search: {str(e)}"
            }

# --- Gemini Model Interaction ---
async def initialize_gemini_model(user_id: int, api_key: str = None) -> Runner | None:
    """
    Configures and initializes the Gemini generative model.
    Args:
        api_key (str, optional): The GOOGLE_API_KEY.
                                 If not provided, it attempts to read from
                                 the GOOGLE_API_KEY environment variable.
    Returns:
        adk.agents.Agent | None: An initialized agent instance if successful, None otherwise.
    """
    # Handle api_key and model configuration
    if api_key is None:
        api_key = os.getenv("GOOGLE_API_KEY")

    if not api_key:
        logging.error("Gemini API key not found. Provide it as an argument or set GOOGLE_API_KEY env variable.")
        return None

    model_name_to_use = os.getenv("GEMINI_MODEL_NAME", DEFAULT_MODEL_NAME)
    logging.info(f"Attempting to initialize Gemini model: {model_name_to_use}")

    # Handle Vector DB init
    try:
        # Initialize the LocalVectorSearchTool. This will trigger the global FAISS loading on first call.
        vector_search = LocalVectorSearchTool(index_path=AGENT_VECTOR_DB) # Pass AGENT_VECTOR_DB explicitly
        
        # Check if the vector store was successfully loaded by the tool's init
        if vector_search.vstore is None:
            logging.error(f"💥 FAISS vector store failed to load globally. Vector search tool will not be available for agent {user_id}.")
            # Decide if we should return None or continue without the tool.
            # For now, let's allow agent initialization but log the absence of the tool.
            local_faiss_search = None # Indicate tool is not available
        else:
            local_faiss_search = FunctionTool(func=vector_search.run_vector_search)
            logging.info(f"✅ LocalVectorSearchTool successfully initialized and FAISS store is available for agent {user_id}.")

        # VectorDBLoader is for creating/updating the DB, not for the search tool itself.
        # It's not directly part of the agent's tools but might be used by other functions if needed.
        # For this agent, we primarily need the search tool.
        # vector_loader = VectorDBLoader() # This line can be kept if vector_loader is used elsewhere or for other functionalities.
                                           # If only used for creating the DB by a separate script, it might not be needed here during agent init.
                                           # For now, assuming it might be used by other parts or future extensions.

    except Exception as e:
        logging.error(f"💥 An error occurred during LocalVectorSearchTool setup: {e}", exc_info=True)
        return None
    
    # Handle ADK service init
    try:
        current_service = InMemorySessionService()
        session = await current_service.create_session(
            app_name="my-gemini-web-app",
            user_id=str(user_id),
            session_id="001"
        )
    except Exception as e:
        logging.error(f"💥 An error occurred during ADK initialization: {e}")
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
            tools=[local_faiss_search] if local_faiss_search else [] # Only add tool if it's available
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

async def get_gemini_response(agent_runner: Runner, user_message: str, user_id: int, session_id: str="001") -> str | None:
    """
    Sends a message to the Gemini model, handles potential tool calls, and returns its final text response.
    Manages chat history implicitly via the 'chat' object.
    Args:
        agent_runner: The initialized ADK Runner instance.
        user_message: The message from the user.
        user_id: The ID of the user.
        session_id: The ID of the current session.
    Returns:
        The model's final text response, or None if an error occurs.
    """
    if not agent_runner:
        logging.error("Runner not provided to get_gemini_response.")
        return None

    logging.info(f"User message for user {user_id}, session {session_id}: '{user_message[:100]}...'")
    content = types.Content(role="user", parts=[types.Part(text=user_message)])
    final_response_text = "Agent did not produce a final response."  # Default response

    user_id_str = str(user_id) # ADK expects user_id as a string

    try:
        async for event in agent_runner.run_async(user_id=user_id_str, session_id=session_id, new_message=content):
            # event.is_final_response() marks the concluding message for the turn.
            if event.is_final_response():
                final_event_content_obj = getattr(event, 'content', None)

                if final_event_content_obj and \
                   hasattr(final_event_content_obj, 'parts') and \
                   isinstance(final_event_content_obj.parts, list) and \
                   len(final_event_content_obj.parts) > 0:
                    
                    first_part_obj = final_event_content_obj.parts[0]
                    if hasattr(first_part_obj, 'text') and first_part_obj.text is not None:
                        final_response_text = first_part_obj.text
                    else:
                        logging.warning(f"User {user_id_str}, Session {session_id}: Final response part object is missing 'text' attribute or its value is None. Part object: {first_part_obj}")
                        final_response_text = "Received response part without text or text is None."
                
                elif hasattr(event, 'actions') and event.actions and hasattr(event.actions, 'escalate') and event.actions.escalate:
                    error_message_details = getattr(event.actions, 'error_message', "No specific message provided by agent.")
                    final_response_text = f"Agent escalated: {error_message_details}"
                    logging.warning(f"User {user_id_str}, Session {session_id}: Agent run escalated. Message: {error_message_details}")
                
                else:
                    # This is a final response, but doesn't fit the expected content structure or known escalation.
                    logging.warning(f"User {user_id_str}, Session {session_id}: Final response received without standard content structure or clear escalation. Event: {event}")
                    generic_error_msg = getattr(event, 'error_message', None) # Attempt to get an error message from the event itself
                    if generic_error_msg:
                        final_response_text = f"Agent error: {generic_error_msg}"
                    else:
                        final_response_text = "Agent provided an unclassified or empty final response."
                break # Stop processing events once the final response is handled
    except Exception as e:
        logging.error(f"💥 Exception during agent_runner.run_async for user {user_id_str}, session {session_id}: {e}", exc_info=True)
        return f"An error occurred while communicating with the AI agent: {e}"
      
    return final_response_text
