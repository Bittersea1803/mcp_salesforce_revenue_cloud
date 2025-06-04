# app.py
import os
import yaml
import json
from flask import Flask, request, jsonify, render_template
from dotenv import load_dotenv
import google.generativeai as genai

from handlers import get_products_salesforce_handler, unsupported_request_handler
from salesforce_auth import get_salesforce_client 

load_dotenv()

app = Flask(__name__)
app.template_folder = 'templates' # Govori Flasku gdje da traži HTML predloške

# --- Salesforce Client Initialization ---
sf_client = None 
def initialize_global_sf_client():
    global sf_client
    if sf_client is None or sf_client == "FAILED_TO_INITIALIZE":
        try:
            print("INFO: app.py - Attempting to initialize global Salesforce client (Session ID only)...")
            sf_client = get_salesforce_client() 
            if sf_client:
                print("INFO: app.py - Global Salesforce client initialized successfully using Session ID.")
            else:
                print("ERROR: app.py - Salesforce client initialization returned None (should be caught by exception).")
                sf_client = "FAILED_TO_INITIALIZE" 
        except Exception as e:
            print(f"ERROR: app.py - Global Salesforce client failed to initialize: {e}")
            sf_client = "FAILED_TO_INITIALIZE"

# --- Gemini API Configuration ---
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
if not GOOGLE_API_KEY:
    raise ValueError("ERROR: GOOGLE_API_KEY is not set in the .env file.")
genai.configure(api_key=GOOGLE_API_KEY)
llm_model_name = 'gemini-1.5-flash-latest'
try:
    llm_model = genai.GenerativeModel(llm_model_name)
    print(f"INFO: Gemini model '{llm_model_name}' configured successfully.")
except Exception as e:
    raise ValueError(f"ERROR: Could not initialize Gemini model '{llm_model_name}': {e}")

# --- MCP Configuration Loading ---
INTENTS_DEFINITION_FOR_PROMPT = "" 
try:
    with open('intents_config.yaml', 'r', encoding='utf-8') as f:
        mcp_config_data = yaml.safe_load(f) 
    INTENTS_DEFINITION_FOR_PROMPT = yaml.dump(mcp_config_data)
    print("INFO: MCP intents configuration loaded successfully from intents_config.yaml.")
except FileNotFoundError:
    raise ValueError("ERROR: intents_config.yaml file not found. Please create it in the project root.")
except yaml.YAMLError as e:
    raise ValueError(f"ERROR: Error parsing intents_config.yaml: {e}")

# --- Initialize Salesforce Client at App Load ---
initialize_global_sf_client()
if sf_client == "FAILED_TO_INITIALIZE" or sf_client is None:
    print("WARNING: Initial Salesforce client setup FAILED during app load. "
          "Ensure SALESSFORCE_SESSION_ID and SALESFORCE_DOMAIN_URL are correctly set in .env "
          "and the session is active. API calls to Salesforce will likely fail.")
else:
    print("INFO: Salesforce client appears to be initialized from app load (check detailed logs).")

MCP_HANDLERS = {
    "GetProducts": get_products_salesforce_handler,
    "UnsupportedRequest": unsupported_request_handler
}

def build_master_prompt(user_query, intents_definition_yaml_string):
    prompt = f"""You are an advanced AI assistant specialized in Salesforce Revenue Cloud.
Your primary task is to analyze the user's query and convert it into a structured JSON object
that corresponds to one of the defined MCP (Model Context Protocol) intents.

Rules:
1. Strictly adhere to the provided intent and slot definitions.
2. If the user's query matches a defined intent, identify the intent and extract all relevant slot values.
3. If the user's query does not match any defined intent, use the "UnsupportedRequest" intent.
4. Your response MUST be ONLY a JSON object with the following structure:
   {{
     "intent": "INTENT_NAME_STRING",
     "slots": {{ "slot_name1": "value1", ... }}
   }}
   If there are no slots for an intent, or no slots were extracted, return an empty object for "slots": {{}}.
   Do NOT include any explanatory text, apologies, or conversational filler before or after the JSON object. Your entire response must be the JSON object itself.

MCP Intent Definitions (from intents_config.yaml):
---
{intents_definition_yaml_string}
---

User's query: "{user_query}"

Your JSON response:
"""
    return prompt

# --- Web UI Route ---
@app.route('/', methods=['GET'])
def home_page():
    """Serves the main HTML page for the web UI."""
    print("INFO: Serving index.html for / route")
    return render_template('index.html') # Renders templates/index.html

# --- API Endpoint for MCP Gateway (used by the web UI's JavaScript) ---
@app.route('/mcp_gateway', methods=['POST'])
def mcp_gateway_endpoint():
    global sf_client 

    if sf_client == "FAILED_TO_INITIALIZE" or sf_client is None:
        print("ERROR: /mcp_gateway - Salesforce client is not available (failed at startup).")
        return jsonify({"status": "error", "message": "Salesforce service is currently unavailable. Please check server logs."}), 503
            
    request_data = request.get_json()
    if not request_data or 'query' not in request_data:
        return jsonify({"status": "error", "message": "Missing 'query' in request body."}), 400
    
    user_query = request_data['query']
    print(f"\nINFO: Received user query via /mcp_gateway: '{user_query}'")

    master_prompt_for_llm = build_master_prompt(user_query, INTENTS_DEFINITION_FOR_PROMPT)
    
    mcp_data_from_llm = None
    llm_output_text = ""
    try:
        print("INFO: Sending query to LLM (Gemini)...")
        llm_api_response = llm_model.generate_content(master_prompt_for_llm) 
        
        if llm_api_response.parts:
            llm_output_text = "".join(part.text for part in llm_api_response.parts).strip()
        elif hasattr(llm_api_response, 'text'):
            llm_output_text = llm_api_response.text.strip()
        else: 
            llm_output_text = str(llm_api_response) 

        print(f"INFO: Raw response from LLM: {llm_output_text}")
        
        if llm_output_text.startswith("```json"):
            llm_output_text = llm_output_text[len("```json"):].strip()
        if llm_output_text.endswith("```"):
            llm_output_text = llm_output_text[:-len("```")].strip()

        mcp_data_from_llm = json.loads(llm_output_text)
        print(f"INFO: Parsed MCP data from LLM: {mcp_data_from_llm}")

    except json.JSONDecodeError as e:
        print(f"ERROR: JSON decoding failed for LLM response: {e}. LLM Raw Output: '{llm_output_text}'")
        return jsonify({"status": "error", "message": "Error parsing AI response.", "llm_raw_output": llm_output_text }), 500
    except Exception as e: 
        print(f"ERROR: Error with LLM: {e}")
        error_details = str(e)
        if hasattr(e, 'response') and hasattr(e.response, 'prompt_feedback'):
             error_details += f" | Prompt Feedback: {e.response.prompt_feedback}"
        if hasattr(e, 'message') and e.message: 
            error_details = e.message 
        return jsonify({"status": "error", "message": f"Error with AI assistant: {error_details}", "llm_raw_output": llm_output_text}), 500

    intent_name = mcp_data_from_llm.get("intent")
    slots = mcp_data_from_llm.get("slots", {})

    if not intent_name:
        return jsonify({"status": "error", "message": "AI did not return an 'intent'."}), 500

    handler_function = MCP_HANDLERS.get(intent_name)

    if handler_function:
        print(f"INFO: Invoking handler '{intent_name}' with slots: {slots}")
        try:
            handler_result = handler_function(sf_client, slots) 
            return jsonify(handler_result)
        except Exception as e_handler:
            print(f"ERROR: Exception in handler '{intent_name}': {e_handler}")
            return jsonify({"status": "error", "message": f"Error in handler '{intent_name}'."}), 500
    else:
        print(f"ERROR: Handler for intent '{intent_name}' not found.")
        return jsonify({"status": "error", "message": f"Unsupported intent: {intent_name}"}), 400

if __name__ == '__main__':
    print("INFO: Starting MCP Salesforce Revenue Cloud Gateway server (with Web UI)...")
    port = int(os.getenv("PORT", 5000)) 
    app.run(host='0.0.0.0', port=port, debug=True)
