# handlers.py

import requests # For making HTTP API calls to Salesforce.
from salesforce_auth import get_salesforce_session # Our module for Salesforce authentication.

def get_products_salesforce_handler(mcp_parameters):
    """
    MCP Handler for the 'GetProducts' intent.
    Fetches products from Salesforce Revenue Cloud based on parameters extracted by the LLM.

    Args:
        mcp_parameters (dict): A dictionary containing slot values extracted by the LLM.
                               Example: {"product_family": "Solar Panels"}

    Returns:
        dict: A result dictionary, either with product data or an error message.
    """
    print(f"INFO: Handler 'GetProducts' invoked with parameters: {mcp_parameters}")
    
    # Step 1: Authenticate with Salesforce and get a session.
    sf_session = get_salesforce_session()
    if not sf_session or 'access_token' not in sf_session or 'instance_url' not in sf_session:
        # If authentication fails or session data is incomplete, return an error.
        return {"status": "error", "message": "Salesforce authentication failed or session is invalid."}

    # Step 2: Construct the SOQL (Salesforce Object Query Language) query.
    # Product2 is the standard Salesforce object for products.
    soql_query = "SELECT Id, Name, ProductCode, Description, Family FROM Product2"
    
    # Get the 'product_family' slot value provided by the LLM, if any.
    product_family = mcp_parameters.get('product_family') 
    
    where_clauses = [] # List to hold WHERE conditions for the SOQL query.
    if product_family:
        # If a product family is specified, add a WHERE clause to filter by it.
        # Basic sanitization for SOQL injection prevention (single quote).
        # For production, use more robust sanitization or parameterized queries if supported by the API client.
        safe_family = product_family.replace("'", "\\'") 
        where_clauses.append(f"Family = '{safe_family}'")

    # Add other filters here based on other extracted slots if needed.
    # Example: if 'max_price' in mcp_parameters: where_clauses.append(f"Price < {mcp_parameters['max_price']}")

    if where_clauses:
        # Append all WHERE conditions to the SOQL query.
        soql_query += " WHERE " + " AND ".join(where_clauses)
        
    # Always add a LIMIT to prevent fetching too much data and to control performance.
    soql_query += " LIMIT 20"

    # Step 3: Prepare and execute the API call to Salesforce.
    # Construct the full URL for the Salesforce Query API endpoint.
    # Using v61.0, ensure this matches your Salesforce instance's API version capabilities.
    query_url = f"{sf_session['instance_url']}/services/data/v61.0/query" 
    
    # Set necessary headers, including the Authorization header with the access token.
    headers = {
        'Authorization': f"Bearer {sf_session['access_token']}",
        'Content-Type': 'application/json' # Although it's a GET, good to be explicit.
    }
    # Pass the SOQL query as a URL parameter 'q'.
    params = {'q': soql_query}

    try:
        print(f"INFO: Executing SOQL query: {soql_query}")
        # Make the GET request to Salesforce.
        response = requests.get(query_url, headers=headers, params=params)
        # Raise an HTTPError for bad responses (4xx or 5xx).
        response.raise_for_status() 
        # Parse the JSON response from Salesforce.
        data = response.json()
        
        # Step 4: Process and format the response.
        products = []
        # Iterate through the 'records' array in the Salesforce response.
        for record in data.get('records', []):
            products.append({
                "id": record.get('Id'),
                "name": record.get('Name'),
                "code": record.get('ProductCode'),
                "description": record.get('Description'),
                "family": record.get('Family')
            })

        if not products:
            # If no products are found, return a user-friendly message.
            message = "No products found"
            if product_family:
                message += f" for category '{product_family}'"
            message += "."
            return {"status": "success", "message": message, "data": []}
        
        # If products are found, return them with a success message.
        return {"status": "success", "message": f"Found {len(products)} products.", "data": products}

    except requests.exceptions.HTTPError as e:
        # Handle HTTP errors from the Salesforce API call.
        error_details_text = "No additional details from server."
        try:
            error_details = e.response.json() if e.response else str(e)
            error_details_text = str(error_details) # Convert to string for uniform handling
        except ValueError: # Handle cases where response is not JSON
             error_details_text = e.response.text if e.response else str(e)
             
        print(f"ERROR: Salesforce API HTTPError: {e}. Details: {error_details_text}")
        return {"status": "error", "message": f"Error communicating with Salesforce API: {error_details_text}"}
    except Exception as e:
        # Handle any other unexpected errors during handler execution.
        print(f"ERROR: An unexpected error occurred in GetProducts handler: {e}")
        return {"status": "error", "message": f"An unexpected error occurred: {str(e)}"}

def unsupported_request_handler(mcp_parameters):
    """
    MCP Handler for the 'UnsupportedRequest' intent.
    Called when the LLM determines the user's query is out of scope.

    Args:
        mcp_parameters (dict): A dictionary of slots (likely empty for this intent).

    Returns:
        dict: A standardized response indicating the request is unsupported.
    """
    print(f"INFO: Handler 'UnsupportedRequest' invoked with parameters: {mcp_parameters}")
    return {"status": "success", "message": "I'm sorry, I can't help with that request. I am focused on Salesforce Revenue Cloud products."}