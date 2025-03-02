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

HUB_URL = 'http://localhost:5555'
HUB_AUTHKEY = '1234567890'
CHANNEL_AUTHKEY = '0987654321'
CHANNEL_NAME = "AI Multi Translation"
CHANNEL_ENDPOINT = "http://localhost:5001"  # don't forget to adjust in the bottom of the file
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
    if not check_authorization(request):
        return "Invalid authorization", 400
    message = request.json
    if not message:
        return "No message", 400
    if 'content' not in message:
        return "No content", 400
    if 'sender' not in message:
        return "No sender", 400
    if 'timestamp' not in message:
        return "No timestamp", 400
    extra = message.get('extra', None)

    content = message['content'].strip()
    detected_lang = GoogleTranslator(source='auto', target='en').translate(content)
    if profanity.contains_profanity(detected_lang):
        response = "⚠️ Sorry, but your message contains inappropriate words and cannot be translated. Please try again with respectful language."
        messages = read_messages()
        messages.append({'content': response, 'sender': 'System 🤖', 'timestamp': message['timestamp']})
        save_messages(messages)
        return "OK", 200

    response = handle_translation(content)
    if not response:
        response = "⚠️ Sorry, but your message could not be translated. Please check the language code or try again."
        messages = read_messages()
        messages.append({'content': response, 'sender': 'System 🤖', 'timestamp': message['timestamp']})
        save_messages(messages)
        return "OK", 200

    messages = read_messages()
    messages.append(
        {'content': content, 'sender': message['sender'], 'timestamp': message['timestamp'], 'extra': extra})

    messages.append({'content': response, 'sender': 'System 🤖', 'timestamp': message['timestamp']})

    save_messages(messages)
    return "OK", 200


# Ensure welcome message exists
messages = read_messages()
if not messages or messages[0]['sender'] != "System 🤖":
    messages.insert(0, {
        'content': (
            "👋 Welcome to the Translation Channel! \n"
            "Simply type your message with the target language in brackets, like this: **[fr] Hello**. \n"
            "If you don't specify a language (or omit brackets), I'll automatically translate it to English! 🌎✨ \n"
            "Available languages: English (en), French (fr), German (de), Spanish (es), Italian (it), Dutch (nl), and Portuguese (pt). Enjoy! 😊"
        ),
        'sender': 'System 🤖',
        'timestamp': datetime.utcnow().isoformat()
    })
    save_messages(messages)


def suggest_language_code(input_code):
    close_matches = get_close_matches(input_code, SUPPORTED_LANGUAGES, n=1, cutoff=0.6)
    if close_matches:
        return f"❌ Oops! Unsupported language code. Did you mean **[{close_matches[0]}]**?"
    return f"❌ Oops! Unsupported language code. Please use one of the following: {', '.join(SUPPORTED_LANGUAGES)}"


def handle_translation(content):
    if content.startswith("[") and "]" in content:
        lang_code = content[1:content.index("]")].strip()
        text = content[content.index("]") + 1:].strip()
    else:
        lang_code = "en"
        text = content.strip()

    if lang_code not in SUPPORTED_LANGUAGES:
        return None

    translated_text = GoogleTranslator(source='auto', target=lang_code).translate(text)
    return f"✅ **Translation:** \n> {translated_text}"

# Start development web server
# run flask --app channel.py register
# to register channel with hub

if __name__ == '__main__':
    app.run(port=5001, debug=True)