import requests
import json
import os
import logging
import time  # Added for delay


# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load configuration from environment or config file
BASE_URL = os.getenv("BASE_URL", "https://sudocodes.com")
USERNAME = os.getenv("API_USERNAME", "admin")
PASSWORD = os.getenv("API_PASSWORD", "admin")
TOKEN_FILE = "token.json"

class APIClient:
    def __init__(self, base_url=BASE_URL):
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/vnd.cvat+json",
            "Content-Type": "application/json",
        })
        self.token = self._load_token()
        self.S3_ID = None  # ✅ Instance variable to store S3_ID

        if not self.token:  # Authenticate if no valid token
            self.token = self._authenticate()

    def _load_token(self):
        """Load token from file if it exists."""
        if os.path.exists(TOKEN_FILE):
            with open(TOKEN_FILE, "r") as file:
                token_data = json.load(file)
                logger.info("🔑 Using stored token")
                return token_data.get("token")
        return None

    def _save_token(self, token):
        """Save token to file."""
        with open(TOKEN_FILE, "w") as file:
            json.dump({"token": token}, file)

    def _delete_token(self):
        """Delete the expired token file."""
        if os.path.exists(TOKEN_FILE):
            os.remove(TOKEN_FILE)
            logger.info("🚮 Expired token deleted.")

    def _authenticate(self):
        """Authenticate and retrieve a new token, with a delay to avoid instant failures."""
        login_url = f"{self.base_url}/api/auth/login"
        login_data = {"username": USERNAME, "password": PASSWORD}

        # 🌟 Adding a short delay before retrying authentication
        time.sleep(3)  # Wait for 3 seconds before attempting authentication
        logger.info("⏳ Waiting 3 seconds before re-authenticating...")

        try:
            response = self.session.post(login_url, json=login_data)
            response.raise_for_status()
            token = response.json().get("key")
            if token:
                self._save_token(token)
                logger.info("✅ Authenticated. New token received.")
                return token
            else:
                logger.error("❌ Authentication failed: Token not found in response")
                raise Exception("Token not found")
        except requests.RequestException as e:
            logger.error(f"❌ Authentication error: {e}")
            raise

    def _update_headers(self):
        """Ensure Authorization header is updated with the latest token."""
        self.session.headers.update({
            "Authorization": f"Token {self.token}",
        })

    def get(self, endpoint, params=None, retry=True):
        """Perform a GET request with auto token refresh and delay handling."""
        self._update_headers()
        url = f"{self.base_url}{endpoint}"
        try:
            response = self.session.get(url, params=params)
            # 🔴 If token is expired (401 Unauthorized), refresh and retry
            if response.status_code == 401 and retry:
                logger.info("🔄 Token expired or invalid. Re-authenticating after delay...")
                self._delete_token()  # Remove expired token
                self.token = self._authenticate()  # Get new token
                self._update_headers()  # Update headers with new token
                return self.get(endpoint, params, retry=False)  # Retry the request

            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f"❌ GET {url} failed: {e}")
            return None

    def get_cloudstorages(self):
        """Fetch Cloud Storages and store S3_ID in the instance variable."""
        endpoint = "/api/cloudstorages"
        query_params = {"page_size": 10}
        result = self.get(endpoint, params=query_params)

        if result and 'results' in result and len(result['results']) > 0:
            logger.info("✅ Cloud Storages fetched successfully")
            print(result)

            response = result['results'][0]  # Extract first result
            self.S3_ID = response['id']  # ✅ Store inside the object instance

            print(f"✅ Extracted S3_ID: {self.S3_ID}")  # Debugging print
        else:
            logger.error("❌ Failed to fetch Cloud Storages")
            self.S3_ID = None  # Ensure it's defined even if no data is found

    def list_s3_contents(self):
        """Fetch and display all contents (folders & files) in S3 storage."""
        if self.S3_ID is None:
            logger.error("❌ S3_ID not set. Fetch cloud storages first.")
            return None

        endpoint = f"/api/cloudstorages/{self.S3_ID}/content-v2"
        params = {"org": "", "prefix": "/"}  # List all root folders & files
        result = self.get(endpoint, params=params)

        if result and "content" in result:
            folders = []
            files = []

            # Separate folders and files
            for item in result["content"]:
                if item["type"] == "DIR":
                    folders.append(item["name"])
                else:
                    files.append(f"{item['name']} ({item['mime_type'].capitalize()})")

            # ✅ Print formatted output without pandas
            if folders:
                print("\n📂 **Folders in S3 Storage**")
                print("-" * 40)
                for folder in folders:
                    print(f"📁 {folder.ljust(30)}")

            if files:
                print("\n🖼️ **Files in S3 Storage**")
                print("-" * 40)
                for file in files:
                    print(f"📄 {file.ljust(30)}")
        else:
            logger.error("❌ Failed to fetch S3 contents")

    def list_projects(self):
        """Fetch and display all projects."""
        endpoint = "/api/projects"
        result = self.get(endpoint)

        if not result or "results" not in result:
            logger.error("❌ Failed to fetch projects")
            return

        print("\n📌 **List of Projects**")
        print("-" * 80)
        print(f"📦 Total Projects Found: {result['count']}\n")

        for project in result["results"]:
            print(f"🆔 Project ID     : {project['id']}")
            print(f"📌 Name           : {project['name']}")
            print(f"🔗 URL            : {project['url']}")
            print(f"👤 Owner          : {project['owner']['username']} (ID: {project['owner']['id']})")
            if project["assignee"]:
                print(f"👤 Assignee       : {project['assignee']['username']} (ID: {project['assignee']['id']})")
            else:
                print(f"👤 Assignee       : None")
            print(f"📅 Created Date   : {project['created_date']}")
            print(f"🔄 Updated Date   : {project['updated_date']}")
            print(f"📌 Status        : {project['status'].capitalize()}")
            print(f"📏 Dimension     : {project['dimension']}")

            # ✅ Storage Details
            print("\n🗄️ **Storage Details**")
            print(f"📂 Source Storage ID : {project['source_storage']['id']} (Cloud ID: {project['source_storage']['cloud_storage_id']})")
            print(f"📂 Target Storage ID : {project['target_storage']['id']} (Cloud ID: {project['target_storage']['cloud_storage_id']})")

            # ✅ Tasks and Labels
            print("\n📜 **Tasks & Labels**")
            print(f"📝 Total Tasks      : {project['tasks']['count']}")
            print(f"🔗 Tasks URL        : {project['tasks']['url']}")
            print(f"🏷️ Labels URL       : {project['labels']['url']}")

            # ✅ Task Subsets
            print("\n📂 **Task Subsets**")
            if project["task_subsets"]:
                for subset in project["task_subsets"]:
                    print(f"✅ {subset}")
            else:
                print("❌ No task subsets available")

            print("-" * 80)  # Divider between projects

        # ✅ Pagination Handling
        if result.get("next"):
            print(f"\n🔜 More projects available: {result['next']}")




    def get_project_details(self, project_id):
        """Fetch and display project details in a readable format."""
        endpoint = f"/api/projects/{project_id}"
        project = self.get(endpoint)

        if not project:
            logger.error("❌ Failed to fetch project details")
            return

        # ✅ Print project details in a readable format
        print("\n📌 **Project Details**")
        print("-" * 60)
        print(f"📌 Project Name      : {project['name']}")
        print(f"🔗 Project URL       : {project['url']}")
        print(f"🆔 Project ID        : {project['id']}")
        print(f"📅 Created Date      : {project['created_date']}")
        print(f"🔄 Last Updated      : {project['updated_date']}")
        print(f"📌 Status           : {project['status'].capitalize()}")
        print(f"📏 Dimension        : {project['dimension']}")
        print(f"👤 Owner Username   : {project['owner']['username']} (ID: {project['owner']['id']})")

        # ✅ Display Cloud Storage Info
        print("\n🗄️ **Storage Details**")
        print("-" * 60)
        print(f"📂 Source Storage ID : {project['source_storage']['id']} (Cloud ID: {project['source_storage']['cloud_storage_id']})")
        print(f"📂 Target Storage ID : {project['target_storage']['id']} (Cloud ID: {project['target_storage']['cloud_storage_id']})")

        # ✅ Display Tasks & Labels
        print("\n📜 **Tasks & Labels**")
        print("-" * 60)
        print(f"📝 Total Tasks      : {project['tasks']['count']}")
        print(f"🔗 Tasks URL        : {project['tasks']['url']}")
        print(f"🏷️ Labels URL       : {project['labels']['url']}")

        # ✅ Display Task Subsets
        print("\n📂 **Task Subsets**")
        print("-" * 60)
        for subset in project["task_subsets"]:
            print(f"✅ {subset}")




    def list_labels(self):  # ✅ Now inside APIClient class
        """Fetch and display all labels."""
        endpoint = "/api/labels"
        result = self.get(endpoint)

        if not result or "results" not in result:
            logger.error("❌ Failed to fetch labels")
            return

        print("\n🏷️ **List of Labels**")
        print("-" * 80)
        print(f"📦 Total Labels Found: {result['count']}\n")

        for label in result["results"]:
            print(f"🆔 Label ID    : {label.get('id', 'N/A')}")
            print(f"🏷️ Name        : {label.get('name', 'N/A')}")
            print(f"🎨 Color       : {label.get('color', 'N/A')}")
            print(f"📌 Type        : {label.get('type', 'N/A')}")
            print(f"📂 Project ID  : {label.get('project_id', 'N/A')}")
            print(f"📂 Task ID     : {label.get('task_id', 'N/A')}")  # ✅ Handles missing task_id safely
            print(f"👨‍👩‍👦 Has Parent? : {'Yes' if label.get('has_parent', False) else 'No'}")

            # ✅ Sublabels
            if label.get("sublabels"):
                print("\n  🔽 Sublabels:")
                for sublabel in label["sublabels"]:
                    print(f"    🆔 Sublabel ID : {sublabel.get('id', 'N/A')}")
                    print(f"    🏷️ Name        : {sublabel.get('name', 'N/A')}")
                    print(f"    🎨 Color       : {sublabel.get('color', 'N/A')}")
                    print(f"    📌 Type        : {sublabel.get('type', 'N/A')}")
                    print(f"    👨‍👩‍👦 Has Parent? : {'Yes' if sublabel.get('has_parent', False) else 'No'}\n")
            else:
                print("  🔽 No sublabels available")

            print("-" * 80)  # Divider between labels

        # ✅ Pagination Handling
        if result.get("next"):
            print(f"\n🔜 More labels available: {result['next']}")





if __name__ == "__main__":
    client = APIClient()

    # ✅ Fetch Cloud Storages and update self.S3_ID
    client.get_cloudstorages()

    # ✅ Fetch and List Folders inside S3 Storage
    #client.list_s3_contents()

    #client.list_projects()

    #client.get_project_details(1)  #need to send project_id not raw inputs

    #client.list_labels()