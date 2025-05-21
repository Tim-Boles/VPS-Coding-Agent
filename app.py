from flask import Flask, render_template, request, jsonify
from agent import initialize_gemini_model, get_gemini_response
import os
import logging

# Configure basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

app = Flask(__name__)

# Initialize Gemini model when the app starts
model = initialize_gemini_model()

if not model# Configure basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
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
        print(f"💥 Error in /ask endpoint: {e}") 
        return jsonify({'error': 'An internal error occurred.'}), 500
