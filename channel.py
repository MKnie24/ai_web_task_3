## channel.py - a simple message channel
##

from flask import Flask, request, render_template, jsonify
import json
import requests
from better_profanity import profanity
from deep_translator import GoogleTranslator
from datetime import datetime
from difflib import get_close_matches


# Class-based application configuration
class ConfigClass(object):
    """ Flask application config """
    # Flask settings
    SECRET_KEY = 'This is an INSECURE secret!! DO NOT use this in production!!'  # change to something random, no matter what


# Create Flask app
app = Flask(__name__)
app.config.from_object(__name__ + '.ConfigClass')  # configuration
app.app_context().push()  # create an app context before initializing db

HUB_URL = 'http://vm146.rz.uni-osnabrueck.de/hub'
HUB_AUTHKEY = 'Crr-K24d-2N'
CHANNEL_AUTHKEY = '0987654321'
CHANNEL_NAME = "AI Multi Translation"
CHANNEL_ENDPOINT = "http://vm146.rz.uni-osnabrueck.de/u042/channel.wsgi"  # don't forget to adjust in the bottom of the file
CHANNEL_FILE = 'messages.json'
CHANNEL_TYPE_OF_SERVICE = 'aiweb24:chat'
SUPPORTED_LANGUAGES = ["en", "fr", "de", "es", "it", "nl", "pt"]
MESSAGE_LIMIT = 50


@app.cli.command('register')
def register_command():
    global CHANNEL_AUTHKEY, CHANNEL_NAME, CHANNEL_ENDPOINT
    # send a POST request to server /channels
    response = requests.post(HUB_URL + '/channels', headers={'Authorization': 'authkey ' + HUB_AUTHKEY},
                             json={
                                 "name": CHANNEL_NAME,
                                 "endpoint": CHANNEL_ENDPOINT,
                                 "authkey": CHANNEL_AUTHKEY,
                                 "type_of_service": CHANNEL_TYPE_OF_SERVICE,
                             })
    if response.status_code != 200:
        print("Error creating channel: " + str(response.status_code))
        print(response.text)
        return


# Check Authorization
def check_authorization(request):
    global CHANNEL_AUTHKEY
    # check if Authorization header is present
    if 'Authorization' not in request.headers:
        return False
    # check if authorization header is valid
    if request.headers['Authorization'] != 'authkey ' + CHANNEL_AUTHKEY:
        return False
    return True


@app.route('/health', methods=['GET'])
def health_check():
    global CHANNEL_NAME
    if not check_authorization(request):
        return "Invalid authorization", 400
    return jsonify({'name': CHANNEL_NAME}), 200

def read_messages():
    global CHANNEL_FILE
    try:
        with open(CHANNEL_FILE, 'r') as f:
            messages = json.load(f)
    except (FileNotFoundError, json.decoder.JSONDecodeError):
        messages = []
    return messages


def save_messages(messages):
    global CHANNEL_FILE
    with open(CHANNEL_FILE, 'w') as f:
        json.dump(messages[-MESSAGE_LIMIT:], f)

# GET: Return list of messages
@app.route('/', methods=['GET'])
def home_page():
    if not check_authorization(request):
        return "Invalid authorization", 400
    return jsonify(read_messages())


# POST: Send a message
@app.route('/', methods=['POST'])
def send_message():
    # Checks if the request is authorized
    if not check_authorization(request):
        return "Invalid authorization", 400

    # Extracts the JSON payload from the request
    message = request.json

    # Validates that a message was provided
    if not message:
        return "No message", 400

    # Ensures the message contains required fields
    if 'content' not in message:
        return "No content", 400
    if 'sender' not in message:
        return "No sender", 400
    if 'timestamp' not in message:
        return "No timestamp", 400

    # Extracts optional extra data from the message
    extra = message.get('extra', None)

# Extracts and cleans up the message content
content = message['content'].strip()

# Detects the language of the message by translating it to English
detected_lang = GoogleTranslator(source='auto', target='en').translate(content)

# Checks if the message contains inappropriate words
if profanity.contains_profanity(detected_lang):
    # Prepare a response indicating the message is not allowed
    response = "⚠️ Sorry, but your message contains inappropriate words and cannot be translated. Please try again with respectful language."

    # Reads the current messages from file
    messages = read_messages()

    # Appends a system-generated warning message
    messages.append({'content': response, 'sender': 'System 🤖', 'timestamp': message['timestamp']})

    # Saves the updated messages list
    save_messages(messages)

    # Returns success response, indicating the message was rejected
    return "OK", 200

# Attempts to translate the message
response = handle_translation(content)

# Checks if translation was unsuccessful

if not response:
    # Prepares an error response, indicating translation failure
    response = "⚠️ Sorry, but your message could not be translated. Please check the language code or try again."

    # Reads the current messages from file
    messages = read_messages()

    # Appends a system-generated error message
    messages.append({'content': response, 'sender': 'System 🤖', 'timestamp': message['timestamp']})

    # Saves the updated messages list
    save_messages(messages)

    # Return success response indicating the failure was recorded
    return "OK", 200

# Reads the current messages from file
messages = read_messages()

# Appends the user's message to the message list
messages.append(
    {'content': content, 'sender': message['sender'], 'timestamp': message['timestamp'], 'extra': extra}
)

# Appends the system's response (translated message or error message)
messages.append({'content': response, 'sender': 'System 🤖', 'timestamp': message['timestamp']})

# Saves the updated message list back to the file
save_messages(messages)

# Returns success response, indicating the message was processed
return "OK", 200

# Read the current messages from the file
messages = read_messages()

# Checks if the message history is empty or the first message is not from the system
if not messages or messages[0]['sender'] != "System 🤖":

    # Insert a welcome message at the top of the message list
    messages.insert(0, {
        'content': (
            "👋 Welcome to the Translation Channel! \n"
            "Simply type your message with the target language in brackets, like this: **[fr] Hello**. \n"
            "If you don't specify a language (or omit brackets), I'll automatically translate it to English! 🌎✨ \n"
            "Available languages: English (en), French (fr), German (de), Spanish (es), Italian (it), Dutch (nl), and Portuguese (pt). Enjoy! 😊"
        ),
        'sender': 'System 🤖',  # Indicating this is a system-generated message
        'timestamp': datetime.utcnow().isoformat()  # Set the current timestamp
    })

    # Saves the updated messages list back to the file
    save_messages(messages)

def suggest_language_code(input_code):
    """
    Suggests the closest supported language code if the user inputs an invalid one.
    """
    # Finds the closest match to the input code from the supported languages
    close_matches = get_close_matches(input_code, SUPPORTED_LANGUAGES, n=1, cutoff=0.6)

    # If a close match is found, suggest the correct language code
    if close_matches:
        return f"❌ Oops! Unsupported language code. Did you mean **[{close_matches[0]}]**?"

    # If no close match is found, provide a list of supported language codes
    return f"❌ Oops! Unsupported language code. Please use one of the following: {', '.join(SUPPORTED_LANGUAGES)}"

def handle_translation(content):
    """
    Extracts the target language code from the message and translates the text.
    """

    # Checks if the content starts with a language code in brackets (e.g., [fr] Hello)
    if content.startswith("[") and "]" in content:
        # Extract the language code from within the brackets
        lang_code = content[1:content.index("]")].strip()
        # Extract the actual text to be translated
        text = content[content.index("]") + 1:].strip()
    else:
        # Defaults to English if no language code is provided
        lang_code = "en"
        text = content.strip()

    # Validatse if the extracted language code is supported
    if lang_code not in SUPPORTED_LANGUAGES:
        return None  # Return None if the language is not supported

    # Translates the text to the target language
    translated_text = GoogleTranslator(source='auto', target=lang_code).translate(text)

    # Returns formatted translation response
    return f"✅ **Translation:** \n> {translated_text}"

# Start development web server
# run flask --app channel.py register
# to register channel with hub

if __name__ == '__main__':
    app.run(port=5001, debug=True)
