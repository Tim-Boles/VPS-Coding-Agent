import google.generativeai as genai
import os
import logging

# Configure basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def initialize_gemini_model(api_key: str = None) -> genai.GenerativeModel | None:
    """
    Configures and initializes the Gemini generative model.

    Args:
        api_key (str, optional): The Gemini API key.
                                 If not provided, it attempts to read from
                                 the GEMINI_API_KEY environment variable.

    Returns:
        genai.GenerativeModel | None: An initialized model instance if successful,
                                      None otherwise.
    """
    if api_key is None:
        api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        logging.error("🚨 In agent.py: Gemini API key not found. "
                      "Provide it as an argument or set GEMINI_API_KEY env variable.")
        return None

    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-2.5-flash-preview-05-20') # As specified
        logging.info("🤖 Gemini AI Model initialized successfully via agent.py.")
        return model
    except Exception as e:
        logging.error(f"💥 An error occurred during Gemini model initialization in agent.py: {e}")
        return None

def get_gemini_response(model: genai.GenerativeModel, user_message: str, chat_history: list = None) -> str | None:
    """
    Sends a message to the Gemini model and returns its text response.

    Args:
        model: The initialized Gemini GenerativeModel.
        user_message: The message from the user.
        chat_history: Optional list of previous chat messages for context.

    Returns:
        The model's text response, or None if an error occurs.
    """
    if not model:
        logging.error("🚨 Error in agent.py: Model not provided to get_gemini_response.")
        return None
    try:
        chat = model.start_chat(history=chat_history if chat_history else [])
        response = chat.send_message(user_message)
        return response.text
    except Exception as e:
        
        return None
