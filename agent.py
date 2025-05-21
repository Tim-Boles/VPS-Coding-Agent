import google.generativeai as genai
from google.generativeai import types 
import os
import logging
from pathlib import Path
import json

# --- Configuration ---
# Configure basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(module)s - %(funcName)s - %(message)s')

# Define a workspace for the agent's file operations
# Files will be read/written here, relative to the /app directory in the container
AGENT_FILES_WORKSPACE = Path("agent_files") # Changed to be relative to /app for simplicity in Docker
DEFAULT_MODEL_NAME = 'gemini-2.5-flash-preview-05-20'

# --- Workspace Initialization ---
try:
    # When running in Docker, WORKDIR is /app. So this creates /app/agent_files
    # Ensure the workspace directory exists when the agent module is loaded.
    # If /app is not writable by the user running the script, this will fail.
    # Gunicorn usually runs as root by default unless configured otherwise.
    AGENT_FILES_WORKSPACE.mkdir(parents=True, exist_ok=True)
    logging.info(f"Agent file workspace initialized at: {AGENT_FILES_WORKSPACE.resolve()}")
except Exception as e:
    logging.error(f"Could not create agent workspace at {AGENT_FILES_WORKSPACE.resolve()}: {e}. File operations may fail.")


# --- File Operation Tools (Python Functions) ---
def _resolve_safe_path(relative_filepath: str) -> Path | None:
    """
    Resolves a relative filepath to an absolute path within the AGENT_FILES_WORKSPACE.
    Prevents path traversal by ensuring the resolved path is within the workspace.
    Args:
        relative_filepath (str): The path relative to AGENT_FILES_WORKSPACE.
    Returns:
        Path | None: The absolute Path object if safe and resolved, None otherwise.
    """
    try:
        # Base path for all agent file operations (e.g., /app/agent_files)
        base_path = AGENT_FILES_WORKSPACE.resolve(strict=True)

        # Resolve the combined path (e.g., /app/agent_files/user_provided/file.txt)
        # strict=False allows checking paths that don't exist yet (for writing new files)
        resolved_path = (base_path / relative_filepath).resolve(strict=False)

        # Security check: Ensure the resolved path is still within the base_path
        # This checks if base_path is a parent of resolved_path or if they are the same.
        if base_path != resolved_path and base_path not in resolved_path.parents:
            logging.warning(f"Path traversal attempt or path outside workspace detected: '{relative_filepath}' resolved to '{resolved_path}' which is outside '{base_path}'.")
            return None
        
        # For writing, ensure parent directory exists if it's a new file
        # This needs to happen *after* the security check.
        if not resolved_path.exists():
            resolved_path.parent.mkdir(parents=True, exist_ok=True)
            
        return resolved_path
    except Exception as e:
        logging.error(f"Error resolving path '{relative_filepath}' within workspace '{AGENT_FILES_WORKSPACE}': {e}")
        return None

def read_text_file(relative_filepath: str) -> str:
    """
    Reads content from a text file within the agent's workspace.
    Args:
        relative_filepath (str): The path to the file relative to the agent's workspace.
                                 (e.g., 'data/my_document.txt')
    Returns:
        str: The content of the file, or an error message.
    """
    logging.info(f"Tool: Attempting to read file '{relative_filepath}'")
    safe_path = _resolve_safe_path(relative_filepath)
    if not safe_path:
        return "Error: Invalid or disallowed file path. Path must be within the agent's designated workspace."

    try:
        if not safe_path.is_file(): # Check if it's a file after resolving
            logging.warning(f"Attempt to read non-file or non-existent file: {safe_path}")
            return f"Error: File not found or is not a regular file at '{relative_filepath}'."
        content = safe_path.read_text(encoding="utf-8")
        logging.info(f"Successfully read file '{relative_filepath}'. Content length: {len(content)}")
        return content
    except FileNotFoundError: # Should be caught by is_file, but as a fallback
        logging.warning(f"File not found at resolved path: {safe_path}")
        return f"Error: File not found at '{relative_filepath}'."
    except Exception as e:
        logging.error(f"Error reading file '{safe_path}': {e}")
        return f"Error: Could not read file. Details: {str(e)}"

def write_text_file(relative_filepath: str, content: str) -> str:
    """
    Writes (or overwrites) content to a text file within the agent's workspace.
    Args:
        relative_filepath (str): The path to the file relative to the agent's workspace.
                                 (e.g., 'output/report.txt')
        content (str): The text content to write to the file.
    Returns:
        str: A success message, or an error message.
    """
    logging.info(f"Tool: Attempting to write to file '{relative_filepath}'. Content length: {len(content)}")
    safe_path = _resolve_safe_path(relative_filepath) # This also creates parent dirs if needed
    if not safe_path:
        return "Error: Invalid or disallowed file path for writing. Path must be within the agent's designated workspace."

    try:
        # _resolve_safe_path should have created parent directories if they didn't exist
        # and the path is for a new file.
        safe_path.write_text(content, encoding="utf-8")
        logging.info(f"Successfully wrote content to file '{relative_filepath}' at '{safe_path}'.")
        return f"Success: Content written to file '{relative_filepath}'."
    except Exception as e:
        logging.error(f"Error writing file '{safe_path}': {e}")
        return f"Error: Could not write to file. Details: {str(e)}"

# --- Gemini Tool Definitions ---
AVAILABLE_TOOLS_PYTHON_FUNCTIONS = {
    "read_text_file": read_text_file,
    "write_text_file": write_text_file,
}

FILE_TOOLS_DECLARATIONS = [
    types.Tool(
        function_declarations=[
            types.FunctionDeclaration(
                name="read_text_file",
                description="Reads the entire content of a specified text file from the agent's private workspace. Use this to retrieve information previously stored in files by the agent.",
                parameters={
                    "type": "OBJECT",
                    "properties": {
                        "relative_filepath": {
                            "type": "STRING",
                            "description": "The path to the file relative to the agent's workspace (e.g., 'input.txt' or 'documents/report.md'). Do NOT use absolute paths like '/app/...' or '../'."
                        }
                    },
                    "required": ["relative_filepath"]
                }
            ),
            types.FunctionDeclaration(
                name="write_text_file",
                description="Writes or overwrites content to a specified text file in the agent's private workspace. Use this to save information, code, or notes. If the file exists, it will be overwritten. If the file or its directory doesn't exist, they will be created within the workspace.",
                parameters={
                    "type": "OBJECT",
                    "properties": {
                        "relative_filepath": {
                            "type": "STRING",
                            "description": "The path to the file relative to the agent's workspace (e.g., 'output.txt' or 'notes/draft.txt'). Do NOT use absolute paths or '../'."
                        },
                        "content": {
                            "type": "STRING",
                            "description": "The text content to be written to the file."
                        }
                    },
                    "required": ["relative_filepath", "content"]
                }
            ),
        ]
    )
]

# --- Gemini Model Interaction ---
def initialize_gemini_model(api_key: str = None) -> genai.GenerativeModel | None:
    """
    Configures and initializes the Gemini generative model.
    Args:
        api_key (str, optional): The Gemini API key.
                                 If not provided, it attempts to read from
                                 the GEMINI_API_KEY environment variable.
    Returns:
        genai.GenerativeModel | None: An initialized model instance if successful, None otherwise.
    """
    if api_key is None:
        api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        logging.error("Gemini API key not found. Provide it as an argument or set GEMINI_API_KEY env variable.")
        return None

    model_name_to_use = os.getenv("GEMINI_MODEL_NAME", DEFAULT_MODEL_NAME)
    logging.info(f"Attempting to initialize Gemini model: {model_name_to_use}")

    try:
        genai.configure(api_key=api_key)
        safety_settings = [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"} ]
        model = genai.GenerativeModel(
            model_name_to_use,
            # Pass the tool declarations to the model during initialization
            # This allows the model to know about the tools from the start.
            # Some SDK versions might prefer tools passed in send_message,
            # but declaring them here is often beneficial.
            tools=FILE_TOOLS_DECLARATIONS,
            safety_settings=safety_settings
            )
        logging.info(f"🤖 Gemini AI Model '{model_name_to_use}' initialized successfully.")
        return model
    except Exception as e:
        logging.error(f"💥 An error occurred during Gemini model '{model_name_to_use}' initialization: {e}")
        return None


def get_gemini_response(model: genai.GenerativeModel, user_message: str, chat_history: list = None) -> str | None:
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
    if not model:
        logging.error("Model not provided to get_gemini_response.")
        return None

    logging.info(f"User message: '{user_message[:100]}...'")

    try:
        # Start a chat session. The model was initialized with tools,
        # but we can also pass them to send_message if needed or for more dynamic toolsets.
        # For simplicity, relying on model initialization tools.
        # If chat_history is None, an empty list is used.
        current_chat_history = chat_history if chat_history else []
        chat = model.start_chat(history=current_chat_history)
        
        # Send the user message. Tools are already configured with the model.
        # If not, you would pass tools=FILE_TOOLS_DECLARATIONS here.
        response = chat.send_message(user_message) # Tools are part of the model config now

        # Loop to handle potential function calls from the model
        while True:
            # Check for function call in the response
            # The structure of response.candidates[0].content.parts needs careful handling
            function_call_part = None
            if response.candidates and \
               response.candidates[0].content and \
               response.candidates[0].content.parts:
                for part in response.candidates[0].content.parts:
                    if part.function_call:
                        function_call_part = part
                        break
            
            if function_call_part:
                fc = function_call_part.function_call
                tool_name = fc.name
                tool_args = {key: value for key, value in fc.args.items()}
                
                logging.info(f"🤖 Gemini requested to use tool: '{tool_name}' with args: {tool_args}")

                if tool_name in AVAILABLE_TOOLS_PYTHON_FUNCTIONS:
                    tool_function = AVAILABLE_TOOLS_PYTHON_FUNCTIONS[tool_name]
                    
                    tool_result = "" # Initialize tool_result
                    try:
                        # Execute the actual Python function for the tool
                        tool_result = tool_function(**tool_args)
                        logging.info(f"Tool '{tool_name}' executed. Result snippet: {str(tool_result)[:200]}...")
                    except TypeError as te: # Catch argument mismatches specifically
                        logging.error(f"💥 Argument mismatch for tool {tool_name} with args {tool_args}: {te}")
                        tool_result = f"Error: Tool '{tool_name}' called with incorrect arguments. Details: {te}"
                    except Exception as e:
                        logging.error(f"💥 Error executing tool '{tool_name}': {e}")
                        tool_result = f"Error: Exception during tool '{tool_name}' execution. Details: {e}"
                    
                    # Send the tool's result back to Gemini
                    # Note: The structure for FunctionResponse content might be just a string
                    # or a dict like {"content": tool_result} or {"result": tool_result}.
                    # The Gemini API documentation for function calling is the source of truth.
                    # Assuming a simple string or a dict with a "content" key is common.
                    # Let's try a dict with "content" as it's often more structured.
                    function_response_content = {"content": str(tool_result)}

                    response = chat.send_message(
                        genai.protos.Part(
                            function_response=genai.protos.FunctionResponse(
                                name=tool_name,
                                response=function_response_content # Pass the dict here
                            )
                        )
                        # tools=FILE_TOOLS_DECLARATIONS # Not needed if model initialized with tools
                    )
                else:
                    logging.error(f"🚨 Error: Gemini called unknown tool '{tool_name}'")
                    # Send an error back to Gemini indicating the tool is not known
                    response = chat.send_message(
                         genai.protos.Part(
                            function_response=genai.protos.FunctionResponse(
                                name=tool_name,
                                response={"error": f"Unknown tool: {tool_name}. Available tools are: {list(AVAILABLE_TOOLS_PYTHON_FUNCTIONS.keys())}"}
                            )
                        )
                        # tools=FILE_TOOLS_DECLARATIONS
                    )
            else:
                # No function call, this should be the final text response from the model
                final_text_response = ""
                if response.candidates and \
                   response.candidates[0].content and \
                   response.candidates[0].content.parts:
                    # Concatenate text from all parts that have text
                    final_text_response = "".join(part.text for part in response.candidates[0].content.parts if hasattr(part, 'text') and part.text)
                
                if not final_text_response and response.prompt_feedback and response.prompt_feedback.block_reason:
                    logging.warning(f"Gemini response was blocked. Reason: {response.prompt_feedback.block_reason_message or response.prompt_feedback.block_reason}")
                    return f"Sorry, your request was blocked by the content safety filter. Reason: {response.prompt_feedback.block_reason_message or response.prompt_feedback.block_reason}"

                if not final_text_response:
                     logging.warning(f"Gemini response had no usable text parts. Full response candidate: {response.candidates[0] if response.candidates else 'No candidates'}")
                     # Check if there's an error message in the response itself
                     if response.candidates and response.candidates[0].finish_reason.name != "STOP":
                         return f"Sorry, the AI model finished unexpectedly. Reason: {response.candidates[0].finish_reason.name}"
                     return "Sorry, I couldn't generate a text response for that."

                logging.info(f"Gemini final response: '{final_text_response[:200]}...'")
                # The 'chat' object now holds the updated history including this interaction.
                # If you need to explicitly manage history outside this function, you'd extract it from chat.history
                return final_text_response

    except Exception as e:
        logging.error(f"💥 Error in get_gemini_response (outer try-except): {e}", exc_info=True)
        # Provide a more generic error if something unexpected happens at a high level
        return "Sorry, an unexpected error occurred while processing your request with the AI."


