# handlers.py
from simple_salesforce.exceptions import SalesforceMalformedRequest, SalesforceError

def get_products_salesforce_handler(sf_client, mcp_parameters):
    """
    MCP Handler for the 'GetProducts' intent using simple-salesforce.
    Fetches products from Salesforce.

    Args:
        sf_client (simple_salesforce.Salesforce): Authenticated simple-salesforce client.
        mcp_parameters (dict): Parameters from LLM (e.g., {"product_family": "Solar Panels"}).

    Returns:
        dict: Result with product data or an error message.
    """
    print(f"INFO: Handler 'GetProducts' invoked with parameters: {mcp_parameters}")
    
    # Provjera je li sf_client uspješno inicijaliziran
    if not sf_client or sf_client == "FAILED_TO_INITIALIZE": 
        print("ERROR: Handler 'GetProducts' - Salesforce client is not available.")
        return {"status": "error", "message": "Salesforce client is not available or not initialized."}

    # Product2 je standardni Salesforce objekt za proizvode.
    soql_query = "SELECT Id, Name, ProductCode, Description, Family FROM Product2"
    product_family = mcp_parameters.get('product_family') 
    
    where_clauses = []
    if product_family:
        # Osnovno escapiranje za SOQL literal. Za kompleksnije unose, razmotrite druge strategije.
        safe_family = product_family.replace("'", "\\'") 
        where_clauses.append(f"Family = '{safe_family}'")

    if where_clauses:
        soql_query += " WHERE " + " AND ".join(where_clauses)
        
    soql_query += " LIMIT 20" # Uvijek je dobro imati LIMIT.

    try:
        print(f"INFO: Executing SOQL query with simple-salesforce: {soql_query}")
        query_result = sf_client.query_all(soql_query) # query_all obrađuje paginaciju
        
        products = []
        for record in query_result.get('records', []):
            products.append({
                "id": record.get('Id'),
                "name": record.get('Name'),
                "code": record.get('ProductCode'),
                "description": record.get('Description'),
                "family": record.get('Family')
            })

        if not products:
            message = "No products found"
            if product_family:
                message += f" for category '{product_family}'"
            message += "."
            return {"status": "success", "message": message, "data": []}
        
        return {"status": "success", "message": f"Found {len(products)} products.", "data": products}

    except SalesforceMalformedRequest as e:
        error_content = getattr(e, 'content', 'No additional error content')
        print(f"ERROR: Salesforce SOQL Malformed Request: {error_content}")
        error_message = "Salesforce query error."
        # Salesforce greške su često liste objekata
        if isinstance(error_content, list) and error_content: 
            error_detail = error_content[0]
            error_message = f"Salesforce query error: {error_detail.get('errorCode', 'N/A')} - {error_detail.get('message', 'No message')}"
        elif isinstance(error_content, str): # Ponekad je sadržaj greške samo string
             error_message = f"Salesforce query error: {error_content}"
        return {"status": "error", "message": error_message}
    except SalesforceError as e: # Hvatanje ostalih općih Salesforce grešaka
        error_content = getattr(e, 'content', 'No additional error content')
        print(f"ERROR: Salesforce API Error: {error_content}")
        return {"status": "error", "message": f"Salesforce API error: {error_content}"}
    except Exception as e:
        print(f"ERROR: An unexpected error occurred in GetProducts handler: {e}")
        return {"status": "error", "message": f"An unexpected error occurred: {str(e)}"}

def unsupported_request_handler(sf_client, mcp_parameters):
    """
    MCP Handler for the 'UnsupportedRequest' intent.
    sf_client se prosljeđuje radi konzistentnosti handlera, ali se ovdje ne koristi.
    """
    print(f"INFO: Handler 'UnsupportedRequest' invoked with parameters: {mcp_parameters}")
    return {"status": "success", "message": "I'm sorry, I can't help with that request. I am focused on Salesforce related queries."}
