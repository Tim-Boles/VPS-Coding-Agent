from flask import Flask, render_template, request, jsonify
import agent
import os

app = Flask(__name__)



@app.route('/')
def index():
    """Serves the main chat page."""
    return render_template('index.html')

@app.route('/ask', methods=['POST'])
def ask():
    """Handles chat messages from the user and returns the AI's response."""
    if not model:
        return jsonify({'error': 'Gemini model not initialized. Check API key and server logs.'}), 500
    if not API_KEY: # Double check here as well
        return jsonify({'error': 'GEMINI_API_KEY not configured on the server.'}), 500

    try:
        user_message = request.json.get('message')
        if not user_message:
            return jsonify({'error': 'No message provided.'}), 400

        # For more complex ADK integration, you would call your ADK agent logic here
        # For this example, we'll make a direct call to the Gemini model

        # response = model.generate_content(user_message)
        # ai_response = response.text

        # Using streaming for a more interactive feel on the frontend is possible,
        # but for simplicity in this first version, we'll use a non-streaming response.
        # For a terminal, streaming is easier. For web, it requires more JS handling.

        chat = model.start_chat(history=[]) # You might want to manage history for context
        response = chat.send_message(user_message)
        ai_response = response.text

        return jsonify({'reply': ai_response})

    except Exception as e:
        print(f"💥 Error in /ask endpoint: {e}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    # This is for local development.
    # For production, use a WSGI server like Gunicorn.
    app.run(host='0.0.0.0', port=5000, debug=True)