# app.py

import os                     # For environment variables.
import yaml                   # For loading the intents_config.yaml file.
import json                   # For parsing JSON from the LLM response.
from flask import Flask, request, jsonify # Flask for the web server.
from dotenv import load_dotenv # To load .env variables.
import google.generativeai as genai # Google AI SDK for Gemini.

# Import handler functions from our handlers.py module.
from handlers import get_products_salesforce_handler, unsupported_request_handler

# Load environment variables from the .env file.
load_dotenv()

# --- Flask App Initialization ---
app = Flask(__name__) # Create a new Flask web server application.

# --- Gemini API Configuration ---
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
if not GOOGLE_API_KEY:
    # Critical: API key must be set.
    raise ValueError("ERROR: GOOGLE_API_KEY is not set in the .env file.")
genai.configure(api_key=GOOGLE_API_KEY) # Configure the Gemini SDK with the API key.
# Select the Gemini model to use. 'gemini-1.5-flash-latest' is fast and capable for NLU.
# For more complex tasks or higher accuracy, you might consider 'gemini-1.5-pro-latest'.
llm_model = genai.GenerativeModel('gemini-1.5-flash-latest')

# --- MCP Configuration Loading ---
INTENTS_DEFINITION_FOR_PROMPT = "" # This will hold the string content of intents_config.yaml for the LLM prompt.
try:
    # Load the MCP intent definitions from the YAML file.
    with open('intents_config.yaml', 'r', encoding='utf-8') as f:
        mcp_config_data = yaml.safe_load(f) # Parse the YAML content.
    # Convert the loaded YAML data back into a string to include in the LLM prompt.
    # This ensures the LLM gets the exact structure and examples.
    INTENTS_DEFINITION_FOR_PROMPT = yaml.dump(mcp_config_data)
    print("INFO: MCP intents configuration loaded successfully.")
except FileNotFoundError:
    raise ValueError("ERROR: intents_config.yaml file not found. Please create it.")
except yaml.YAMLError as e:
    raise ValueError(f"ERROR: Error parsing intents_config.yaml: {e}")

# --- MCP Handler Mapping ---
# This dictionary maps recognized intent names (strings) to their corresponding handler functions.
MCP_HANDLERS = {
    "GetProducts": get_products_salesforce_handler,
    "UnsupportedRequest": unsupported_request_handler
    # Add more intent-to-handler mappings here as you develop more intents.
    # "CalculatePrice": calculate_price_handler,
    # "CreateQuote": create_quote_handler,
}

def build_master_prompt(user_query, intents_definition_yaml_string):
    """
    Constructs the master prompt to send to the LLM (Gemini).
    This prompt guides the LLM to understand the user's query in the context of our MCP intents.

    Args:
        user_query (str): The raw text query from the user.
        intents_definition_yaml_string (str): The string content of intents_config.yaml.

    Returns:
        str: The fully constructed prompt for the LLM.
    """
    # The prompt is carefully engineered to instruct the LLM:
    # 1. Its role (Salesforce Revenue Cloud assistant).
    # 2. Its task (convert user query to structured JSON based on MCP intents).
    # 3. Strict rules for output format (JSON only, specific structure).
    # 4. The actual MCP intent definitions (from intents_config.yaml).
    # 5. The user's current query.
    # 6. A final instruction to provide the JSON response.
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
   Do NOT include any explanatory text before or after the JSON object.

MCP Intent Definitions (from intents_config.yaml):
---
{intents_definition_yaml_string}
---

User's query: "{user_query}"

Your JSON response:
"""
    return prompt

# --- API Endpoint for MCP Gateway ---
@app.route('/mcp_gateway', methods=['POST']) # Defines a Flask route that accepts POST requests.
def mcp_gateway_endpoint():
    """
    Main API endpoint that receives user queries, processes them using an LLM (Gemini)
    to determine intent and slots, and then dispatches to the appropriate handler.
    """
    # Step 1: Get the user's query from the request body.
    # Expects a JSON payload like: {"query": "User's question here"}
    request_data = request.get_json()
    if not request_data or 'query' not in request_data:
        print("ERROR: Request body missing 'query' field.")
        return jsonify({"status": "error", "message": "Missing 'query' in request body."}), 400 # Bad Request
    
    user_query = request_data['query']
    print(f"\nINFO: Received user query: '{user_query}'")

    # Step 2: Construct the master prompt for the LLM.
    master_prompt_for_llm = build_master_prompt(user_query, INTENTS_DEFINITION_FOR_PROMPT)
    
    mcp_data_from_llm = None # Variable to store the parsed JSON from the LLM.
    try:
        # Step 3: Send the prompt to the LLM (Gemini) and get its response.
        print("INFO: Sending query to LLM (Gemini)...")
        # For debugging, you might want to print the full prompt:
        # print(f"--- LLM PROMPT START ---\n{master_prompt_for_llm}\n--- LLM PROMPT END ---")
        
        llm_api_response = llm_model.generate_content(master_prompt_for_llm)
        
        # Step 4: Extract and parse the JSON from the LLM's response.
        # LLM responses are text; we need to extract the JSON part.
        llm_output_text = llm_api_response.text.strip()
        print(f"INFO: Raw response from LLM: {llm_output_text}")
        
        # LLMs sometimes wrap JSON in markdown ```json ... ``` blocks.
        # This code attempts to clean that up.
        if llm_output_text.startswith("```json"):
            llm_output_text = llm_output_text[len("```json"):].strip()
        if llm_output_text.endswith("```"):
            llm_output_text = llm_output_text[:-len("```")].strip()

        print(f"INFO: Cleaned response from LLM (attempting JSON parse): {llm_output_text}")
        mcp_data_from_llm = json.loads(llm_output_text) # Parse the cleaned text as JSON.
        print(f"INFO: Parsed MCP data from LLM: {mcp_data_from_llm}")

    except json.JSONDecodeError as e:
        # Handle cases where the LLM's response is not valid JSON.
        print(f"ERROR: JSON decoding failed for LLM response: {e}. LLM Raw Output: '{llm_output_text}'")
        return jsonify({
            "status": "error", 
            "message": "Error in parsing the response from the AI assistant. It was not valid JSON.",
            "llm_raw_output": llm_output_text # Include LLM output for debugging.
        }), 500 # Internal Server Error
    except Exception as e:
        # Handle other potential errors during LLM communication.
        # This could include API errors, network issues, etc.
        print(f"ERROR: Error communicating with LLM: {e}")
        # Try to get more details if it's a Google API error
        error_details = str(e)
        if hasattr(e, 'response') and hasattr(e.response, 'text'):
            error_details = e.response.text
        return jsonify({"status": "error", "message": f"Error communicating with the AI assistant: {error_details}"}), 500

    # Step 5: Extract the intent and slots from the LLM's parsed JSON response.
    intent_name = mcp_data_from_llm.get("intent")
    slots = mcp_data_from_llm.get("slots", {}) # Default to an empty dict if 'slots' is missing.

    if not intent_name:
        # The LLM must return an 'intent'.
        print("ERROR: LLM response missing 'intent' field.")
        return jsonify({"status": "error", "message": "AI assistant did not return an 'intent'."}), 500

    # Step 6: Dispatch to the appropriate handler based on the recognized intent.
    handler_function = MCP_HANDLERS.get(intent_name)

    if handler_function:
        # If a handler is found for the intent, call it with the extracted slots.
        print(f"INFO: Invoking handler '{intent_name}' with slots: {slots}")
        handler_result = handler_function(slots)
        return jsonify(handler_result) # Return the result from the handler to the client.
    else:
        # If no handler is defined for the recognized intent.
        print(f"ERROR: Handler for intent '{intent_name}' not found.")
        return jsonify({"status": "error", "message": f"Unknown or unsupported intent: {intent_name}"}), 400 # Bad Request (or 501 Not Implemented)

# --- Main Execution Block ---
if __name__ == '__main__':
    # This block runs when the script is executed directly (e.g., python app.py).
    print("INFO: Starting MCP Salesforce Revenue Cloud Gateway server...")
    
    # Optional: Perform an initial Salesforce authentication check at startup.
    # This helps catch configuration issues early.
    from salesforce_auth import get_salesforce_session
    if not get_salesforce_session():
         print("WARNING: Salesforce authentication failed at startup. Please check .env configuration and Salesforce Connected App settings.")
    else:
        print("INFO: Salesforce initial authentication check successful.")
    
    # Start the Flask development server.
    # host='0.0.0.0' makes the server accessible from other devices on the network.
    # port=5000 is the default Flask port.
    # debug=True enables debug mode, which provides helpful error messages and auto-reloads on code changes.
    # Do NOT use debug=True in a production environment.
    app.run(host='0.0.0.0', port=5000, debug=True)