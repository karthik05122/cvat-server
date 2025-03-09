import requests
import json
import os

# ✅ API Base URL
BASE_URL = "https://sudocodes.com"  # ✅ Ensure the URL includes 
LOGIN_URL = f"{BASE_URL}/api/auth/login"
CLOUDSTORAGE_URL = f"{BASE_URL}/api/cloudstorages"
TOKEN_FILE = "token.json"  # File to store token

# ✅ Credentials (Only needed once)
USERNAME = "admin"
PASSWORD = "admin"

# ✅ Function to Load Stored Token
def load_token():
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, "r") as file:
            return json.load(file)
    return None

# ✅ Function to Save Token
def save_token(token):
    with open(TOKEN_FILE, "w") as file:
        json.dump(token, file)

# ✅ Function to Authenticate (Only if No Valid Token Exists)
def authenticate():
    session = requests.Session()
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/vnd.cvat+json",
        "Content-Type": "application/json",
    }
    login_data = {"username": USERNAME, "password": PASSWORD}
    
    auth_response = session.post(LOGIN_URL, json=login_data, headers=headers)
    
    if auth_response.status_code == 200:
        token = auth_response.json().get("key")
        print("✅ Authenticated. Token received.")
        save_token({"token": token})  # Save token for future use
        return token
    else:
        print(f"❌ Authentication Failed: {auth_response.status_code} - {auth_response.text}")
        exit()

# ✅ Get a Valid Token (Load from File or Authenticate)
token_data = load_token()
if token_data and "token" in token_data:
    api_token = token_data["token"]
    print("🔑 Using Stored Token")
else:
    api_token = authenticate()

# ✅ Prepare Headers for API Requests
headers = {
    "Authorization": f"Token {api_token}",  # Use stored token
    "Accept": "application/vnd.cvat+json",
}

# ✅ Function to Fetch Cloud Storages
def get_cloudstorages():
    query_params = {"page_size": 10}  # Adjust filters as needed
    response = requests.get(CLOUDSTORAGE_URL, headers=headers, params=query_params)

    if response.status_code == 200:
        print("✅ Cloud Storages:", response.json())
    else:
        print(f"❌ Error: {response.status_code} - {response.text}")

# ✅ Call the API without re-authenticating
get_cloudstorages()
