from flask import Flask, render_template, request, jsonify
from agent import initialize_gemini_model, get_gemini_response, list_files_in_workspace, read_text_file
import os
import logging

# Configure basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

app = Flask(__name__)

# Initialize Gemini model when the app starts
model = initialize_gemini_model()

if not model:
    logging.error("🔴 Gemini model failed to initialize. The /ask endpoint will not work.")

@app.route('/')
def index():
    """Serves the main chat page."""
    return render_template('index.html')

@app.route('/ask', methods=['POST'])
def ask():
    """Handles chat messages from the user and returns the AI's response."""
    if not model:
        return jsonify({'error': 'Gemini model not initialized. Check server logs.'}), 500

    try:
        user_message = request.json.get('message')
        if not user_message:
            return jsonify({'error': 'No message provided.'}), 400

        ai_response = get_gemini_response(model, user_message)
        
        if ai_response is None: # Added check
            # This assumes get_gemini_response returning None means an error occurred internally
            return jsonify({'error': 'Failed to get response from AI. Please check server logs.'}), 500
            
        return jsonify({'reply': ai_response})

    except Exception as e:
        # Consider using app.logger.error() here instead of print for production
        logging.error(f"💥 Error in /ask endpoint: {e}") 
        return jsonify({'error': 'An internal error occurred.'}), 500

@app.route('/list_files', methods=['GET'])
def list_agent_files():
    """Lists files in the agent's workspace."""
    try:
        file_list = list_files_in_workspace()
        return jsonify(files=file_list)
    except Exception as e:
        logging.error(f"💥 Error in /list_files endpoint: {e}")
        return jsonify({'error': 'Could not list files due to an internal server error.'}), 500

@app.route('/view_file/<path:filename>', methods=['GET'])
def view_agent_file(filename):
    """Serves the content of a specific file from the agent's workspace."""
    if not filename:
        return jsonify({'error': 'No filename provided.'}), 400
    
    logging.info(f"Attempting to view file: {filename}")
    try:
        file_content = read_text_file(filename) # This function is from the agent module

        if file_content.startswith("Error: File not found"):
            logging.warning(f"File not found: {filename}")
            return jsonify({'error': file_content}), 404
        elif file_content.startswith("Error:"):
            logging.error(f"Error reading file '{filename}': {file_content}")
            return jsonify({'error': file_content}), 500
        
        return jsonify({'filename': filename, 'content': file_content})

    except Exception as e:
        logging.error(f"💥 Unexpected error in /view_file/{filename} endpoint: {e}")
        return jsonify({'error': f'An unexpected error occurred while trying to read the file {filename}.'}), 500
