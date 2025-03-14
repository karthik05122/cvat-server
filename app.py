#!/usr/bin/env python3
import os
import sys
import time
import json
import logging
from typing import Any, Dict, List, Optional
from dotenv import load_dotenv

import requests

# -----------------------------------------------------------------------------
# Logging and Configuration
# -----------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

# Configuration from environment or defaults
load_dotenv()

BASE_URL: str = os.getenv("BASE_URL", "https://sudocodes.com")
USERNAME: str = os.getenv("API_USERNAME", "admin")
PASSWORD: str = os.getenv("API_PASSWORD", "admin")
TOKEN_FILE: str = "token.json"
CREATE_TASK_FILE: str = "create_task.json"

# Example server file paths (use raw strings or forward slashes)
server_files: List[str] = [
    r"D:\Orochi\Cvat-server\images\1.jpg",
    r"D:\Orochi\Cvat-server\images\2.jpg"
]

# -----------------------------------------------------------------------------
# APIClient Class
# -----------------------------------------------------------------------------
class APIClient:
    def __init__(self, base_url: str = BASE_URL) -> None:
        self.base_url: str = base_url
        self.session: requests.Session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/vnd.cvat+json",
            "Content-Type": "application/json",
        })
        self.token: Optional[str] = self._load_token()
        self.S3_ID: Optional[int] = None

        if not self.token:
            self.token = self._authenticate()

    # --- Authentication Methods ---
    def _load_token(self) -> Optional[str]:
        """Load token from file if it exists."""
        if os.path.exists(TOKEN_FILE):
            try:
                with open(TOKEN_FILE, "r") as file:
                    token_data = json.load(file)
                    logger.info("🔑 Using stored token")
                    return token_data.get("token")
            except Exception as e:
                logger.error("Error loading token: %s", e)
        return None

    def _save_token(self, token: str) -> None:
        """Save token to file."""
        try:
            with open(TOKEN_FILE, "w") as file:
                json.dump({"token": token}, file)
        except Exception as e:
            logger.error("Error saving token: %s", e)

    def _delete_token(self) -> None:
        """Delete the expired token file."""
        if os.path.exists(TOKEN_FILE):
            os.remove(TOKEN_FILE)
            logger.info("🚮 Expired token deleted.")

    def _authenticate(self) -> str:
        """Authenticate and return a new token."""
        login_url = f"{self.base_url}/api/auth/login"
        login_data = {"username": USERNAME, "password": PASSWORD}
        logger.info("⏳ Waiting 3 seconds before re-authenticating...")
        time.sleep(3)
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
            logger.error("❌ Authentication error: %s", e)
            raise

    def _update_headers(self) -> None:
        """Update session headers with the latest token."""
        self.session.headers.update({
            "Authorization": f"Token {self.token}",
        })

    # --- Generic GET Method ---
    def get(self, endpoint: str, params: Optional[Dict[str, Any]] = None, retry: bool = True) -> Optional[Dict[str, Any]]:
        """
        Perform a GET request with automatic token refresh.
        
        :param endpoint: API endpoint.
        :param params: Query parameters.
        :param retry: Whether to retry on token expiration.
        :return: JSON response as dictionary.
        """
        self._update_headers()
        url = f"{self.base_url}{endpoint}"
        try:
            response = self.session.get(url, params=params)
            if response.status_code == 401 and retry:
                logger.info("🔄 Token expired or invalid. Re-authenticating...")
                self._delete_token()
                self.token = self._authenticate()
                self._update_headers()
                return self.get(endpoint, params=params, retry=False)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error("❌ GET %s failed: %s", url, e)
            return None

    # --- Cloud Storage Methods ---
    def get_cloudstorages(self) -> None:
        """Fetch cloud storages and store S3_ID."""
        endpoint = "/api/cloudstorages"
        params = {"page_size": 10}
        result = self.get(endpoint, params=params)
        if result and "results" in result and result["results"]:
            logger.info("✅ Cloud Storages fetched successfully")
            storage = result["results"][0]
            self.S3_ID = storage.get("id")
            print(f"✅ Extracted S3_ID: {self.S3_ID}")
        else:
            logger.error("❌ Failed to fetch Cloud Storages")
            self.S3_ID = None

    def list_s3_contents(self) -> None:
        """Fetch and display contents of the S3 storage."""
        if self.S3_ID is None:
            logger.error("❌ S3_ID not set. Fetch cloud storages first.")
            return
        endpoint = f"/api/cloudstorages/{self.S3_ID}/content-v2"
        params = {"org": "", "prefix": "/"}
        result = self.get(endpoint, params=params)
        if result and "content" in result:
            folders, files = [], []
            for item in result["content"]:
                if item["type"] == "DIR":
                    folders.append(item["name"])
                else:
                    files.append(f"{item['name']} ({item['mime_type'].capitalize()})")
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

    # --- Project Methods ---
    def list_projects(self) -> None:
        """Fetch and display all projects."""
        endpoint = "/api/projects"
        result = self.get(endpoint)
        if not result or "results" not in result:
            logger.error("❌ Failed to fetch projects")
            return
        print("\n📌 **List of Projects**")
        print("-" * 80)
        print(f"📦 Total Projects Found: {result.get('count', 0)}\n")
        for project in result["results"]:
            print(f"🆔 Project ID     : {project.get('id')}")
            print(f"📌 Name           : {project.get('name')}")
            print(f"🔗 URL            : {project.get('url')}")
            owner = project.get("owner", {})
            print(f"👤 Owner          : {owner.get('username')} (ID: {owner.get('id')})")
            assignee = project.get("assignee")
            if assignee:
                print(f"👤 Assignee       : {assignee.get('username')} (ID: {assignee.get('id')})")
            else:
                print("👤 Assignee       : None")
            print(f"📅 Created Date   : {project.get('created_date')}")
            print(f"🔄 Updated Date   : {project.get('updated_date')}")
            print(f"📌 Status         : {project.get('status', 'N/A').capitalize()}")
            print(f"📏 Dimension      : {project.get('dimension')}")
            print("\n🗄️ **Storage Details**")
            source_storage = project.get("source_storage", {})
            target_storage = project.get("target_storage", {})
            print(f"📂 Source Storage ID : {source_storage.get('id')} (Cloud ID: {source_storage.get('cloud_storage_id')})")
            print(f"📂 Target Storage ID : {target_storage.get('id')} (Cloud ID: {target_storage.get('cloud_storage_id')})")
            print("\n📜 **Tasks & Labels**")
            tasks = project.get("tasks", {})
            labels = project.get("labels", {})
            print(f"📝 Total Tasks      : {tasks.get('count')}")
            print(f"🔗 Tasks URL        : {tasks.get('url')}")
            print(f"🏷️ Labels URL       : {labels.get('url')}")
            print("\n📂 **Task Subsets**")
            subsets = project.get("task_subsets")
            if subsets:
                for subset in subsets:
                    print(f"✅ {subset}")
            else:
                print("❌ No task subsets available")
            print("-" * 80)
        if result.get("next"):
            print(f"\n🔜 More projects available: {result['next']}")

    def get_project_details(self, project_id: int) -> None:
        """Fetch and display details for a specific project."""
        endpoint = f"/api/projects/{project_id}"
        project = self.get(endpoint)
        if not project:
            logger.error("❌ Failed to fetch project details")
            return
        print("\n📌 **Project Details**")
        print("-" * 60)
        print(f"📌 Project Name      : {project.get('name')}")
        print(f"🔗 Project URL       : {project.get('url')}")
        print(f"🆔 Project ID        : {project.get('id')}")
        print(f"📅 Created Date      : {project.get('created_date')}")
        print(f"🔄 Last Updated      : {project.get('updated_date')}")
        print(f"📌 Status            : {project.get('status', 'N/A').capitalize()}")
        print(f"📏 Dimension         : {project.get('dimension')}")
        owner = project.get("owner", {})
        print(f"👤 Owner Username   : {owner.get('username')} (ID: {owner.get('id')})")
        print("\n🗄️ **Storage Details**")
        source_storage = project.get("source_storage", {})
        target_storage = project.get("target_storage", {})
        print(f"📂 Source Storage ID : {source_storage.get('id')} (Cloud ID: {source_storage.get('cloud_storage_id')})")
        print(f"📂 Target Storage ID : {target_storage.get('id')} (Cloud ID: {target_storage.get('cloud_storage_id')})")
        print("\n📜 **Tasks & Labels**")
        tasks = project.get("tasks", {})
        labels = project.get("labels", {})
        print(f"📝 Total Tasks      : {tasks.get('count')}")
        print(f"🔗 Tasks URL        : {tasks.get('url')}")
        print(f"🏷️ Labels URL       : {labels.get('url')}")
        print("\n📂 **Task Subsets**")
        subsets = project.get("task_subsets")
        if subsets:
            for subset in subsets:
                print(f"✅ {subset}")
        else:
            print("❌ No task subsets available")

    def list_labels(self, project_id: int, org: str = "", page_size: int = 500, page: int = 1) -> None:
        """Fetch and display all labels for a given project."""
        endpoint = "/api/labels"
        params = {
            "project_id": project_id,
            "org": org,
            "page_size": page_size,
            "page": page
        }
        result = self.get(endpoint, params=params)
        if not result or "results" not in result:
            logger.error("❌ Failed to fetch labels")
            return
        print("\n🏷️ **List of Labels**")
        print("-" * 80)
        print(f"📦 Total Labels Found: {result.get('count', 0)}\n")
        for label in result["results"]:
            print(f"🆔 Label ID    : {label.get('id', 'N/A')}")
            print(f"🏷️ Name        : {label.get('name', 'N/A')}")
            print(f"🎨 Color       : {label.get('color', 'N/A')}")
            print(f"📌 Type        : {label.get('type', 'N/A')}")
            print(f"📂 Project ID  : {label.get('project_id', 'N/A')}")
            print(f"📂 Task ID     : {label.get('task_id', 'N/A')}")
            print(f"👨‍👩‍👦 Has Parent? : {'Yes' if label.get('has_parent', False) else 'No'}")
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
            print("-" * 80)
        if result.get("next"):
            print(f"\n🔜 More labels available: {result['next']}")

    def get_tasks(self, query_params: Optional[Dict[str, Any]] = None, fields: Optional[List[str]] = None) -> None:
        """
        Fetch and display tasks with optional filtering.
        
        :param query_params: Dictionary of query parameters.
        :param fields: List of specific fields to display.
        """
        endpoint = "/api/tasks"
        tasks = self.get(endpoint, params=query_params)
        if not tasks or "results" not in tasks:
            logger.error("❌ Failed to fetch tasks")
            return
        print("\n🏷️ **List of Tasks**")
        print("-" * 80)
        print(f"📦 Total Tasks Found: {tasks.get('count', 0)}\n")
        for task in tasks["results"]:
            if fields:
                for field in fields:
                    value = task.get(field, 'N/A')
                    print(f"🔹 {field.capitalize()} : {value}")
            else:
                print(f"🆔 Task ID     : {task.get('id', 'N/A')}")
                print(f"📌 Name        : {task.get('name', 'N/A')}")
                print(f"🔗 Task URL    : {task.get('url', 'N/A')}")
                print(f"📂 Project ID  : {task.get('project_id', 'N/A')}")
                print(f"📅 Created     : {task.get('created_date', 'N/A')}")
                print(f"🔄 Updated     : {task.get('updated_date', 'N/A')}")
                print(f"📌 Status      : {task.get('status', 'N/A').capitalize()}")
                print(f"📏 Dimension   : {task.get('dimension', 'N/A')}")
            print("-" * 80)
        if tasks.get("next"):
            print(f"\n🔜 More tasks available: {tasks['next']}")

    def create_task(self, json_file_path: str) -> Optional[Dict[str, Any]]:
        """
        Create a new task using data from a JSON file.
        
        :param json_file_path: Path to the JSON file containing task details.
        :return: Formatted API response as dictionary.
        """
        endpoint = "/api/tasks"
        url = f"{self.base_url}{endpoint}"
        try:
            with open(json_file_path, "r") as file:
                data = json.load(file)
        except FileNotFoundError:
            print("❌ Error: JSON file not found.")
            return None
        except json.JSONDecodeError:
            print("❌ Error: Invalid JSON format.")
            return None
        headers = {
            "Authorization": f"Token {self.token}",
            "Content-Type": "application/json"
        }
        try:
            response = self.session.post(url, json=data, headers=headers)
            response.raise_for_status()
            print("\n✅ **Task Created Successfully**")
            response_data = response.json()
            formatted_response = {
                "url": response_data.get("url", "http://example.com"),
                "id": response_data.get("id", 0),
                "name": response_data.get("name", "string"),
                "project_id": response_data.get("project_id", 0),
                "mode": response_data.get("mode", "string"),
                "owner": response_data.get("owner", {
                    "url": "http://example.com",
                    "id": 0,
                    "username": "^w$",
                    "first_name": "string",
                    "last_name": "string"
                }),
                "assignee": response_data.get("assignee", {
                    "url": "http://example.com",
                    "id": 0,
                    "username": "^w$",
                    "first_name": "string",
                    "last_name": "string"
                }),
                "bug_tracker": response_data.get("bug_tracker", "string"),
                "created_date": response_data.get("created_date", "2019-08-24T14:15:22Z"),
                "updated_date": response_data.get("updated_date", "2019-08-24T14:15:22Z"),
                "overlap": response_data.get("overlap", 0),
                "segment_size": response_data.get("segment_size", 0),
                "status": response_data.get("status", "annotation"),
                "data_chunk_size": response_data.get("data_chunk_size", 2147483647),
                "data_compressed_chunk_type": response_data.get("data_compressed_chunk_type", "video"),
                "guide_id": response_data.get("guide_id", 0),
                "data_original_chunk_type": response_data.get("data_original_chunk_type", "video"),
                "size": response_data.get("size", 2147483647),
                "image_quality": response_data.get("image_quality", 32767),
                "data": response_data.get("data", 0),
                "dimension": response_data.get("dimension", "string"),
                "subset": response_data.get("subset", "string"),
                "organization": response_data.get("organization", 0),
                "target_storage": response_data.get("target_storage", {
                    "id": 0,
                    "location": "cloud_storage",
                    "cloud_storage_id": 0
                }),
                "source_storage": response_data.get("source_storage", {
                    "id": 0,
                    "location": "cloud_storage",
                    "cloud_storage_id": 0
                }),
                "jobs": response_data.get("jobs", {
                    "count": 0,
                    "completed": 0,
                    "validation": 0,
                    "url": "http://example.com"
                }),
                "labels": response_data.get("labels", {
                    "url": "http://example.com"
                }),
                "assignee_updated_date": response_data.get("assignee_updated_date", "2019-08-24T14:15:22Z"),
                "validation_mode": response_data.get("validation_mode", "string"),
                "consensus_enabled": response_data.get("consensus_enabled", True)
            }
            print(json.dumps(formatted_response, indent=4))
            return formatted_response
        except requests.RequestException as e:
            print(f"❌ Failed to create task:", e)
            return None

    def upload_image_to_taskID(self, task_id: int, server_files: List[str], cloud_storage_id: int = 1) -> Optional[Dict[str, Any]]:
        """
        Upload image paths to a task.
        
        :param task_id: ID of the task.
        :param server_files: List of file paths for the images.
        :param cloud_storage_id: Cloud storage ID.
        :return: API response as dictionary.
        """
        endpoint = f"/api/tasks/{task_id}/data"
        url = f"{self.base_url}{endpoint}"
        headers = {
            "Authorization": f"Token {self.token}",
            "Content-Type": "application/json"
        }
        missing_files = [file for file in server_files if not os.path.exists(file)]
        if missing_files:
            print("\n❌ **Error: The following files were not found:**")
            for missing_file in missing_files:
                print(f"   → {missing_file}")
            print("\n🔹 **Check if your file paths are correct!**")
            return None
        payload = {
            "server_files": server_files,
            "remote_files": [],
            "image_quality": 70,
            "use_zip_chunks": True,
            "use_cache": True,
            "sorting_method": "lexicographical",
            "cloud_storage_id": cloud_storage_id
        }
        try:
            response = self.session.post(url, headers=headers, json=payload)
            if response.status_code == 500:
                print("\n❌ **Server Error (500) - The API Crashed**")
                print("👉 **Possible Causes:** Invalid file paths, unsupported formats, or API issues.")
                print("👉 **API Response:**", response.text)
                return None
            response.raise_for_status()
            print("\n✅ **Images Added to Task Successfully**")
            print(response.json())
            return response.json()
        except requests.RequestException as e:
            print(f"❌ Failed to upload images:", e)
            return None

    def get_labels_for_task(self, task_id: int) -> Optional[Dict[str, Any]]:
        """
        Fetch and display all labels for a specific task.
        
        :param task_id: ID of the task.
        :return: JSON response with label data.
        """
        endpoint = "/api/labels"
        url = f"{self.base_url}{endpoint}"
        headers = {
            "Authorization": f"Token {self.token}"
        }
        params = {"task_id": task_id}
        try:
            response = self.session.get(url, headers=headers, params=params)
            response.raise_for_status()
            labels_data = response.json()
            if not labels_data.get("results"):
                print(f"\n❌ No labels found for Task ID {task_id}")
                return None
            print(f"\n🏷️ **Labels for Task ID {task_id}**")
            print("-" * 60)
            for label in labels_data["results"]:
                print(f"🆔 Label ID    : {label.get('id')}")
                print(f"🏷️ Name        : {label.get('name')}")
                print(f"🎨 Color       : {label.get('color')}")
                print(f"📂 Project ID  : {label.get('project_id')}")
                print(f"👨‍👩‍👦 Has Parent? : {'Yes' if label.get('has_parent', False) else 'No'}")
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
                print("-" * 60)
            return labels_data
        except requests.RequestException as e:
            print(f"❌ Failed to fetch labels for Task {task_id}: {e}")
            return None

# -----------------------------------------------------------------------------
# Main Function
# -----------------------------------------------------------------------------
def main() -> None:
    client = APIClient()

    # Uncomment the functions you want to execute.

    # Cloud Storage Discovery:
    #client.get_cloudstorages()
    #client.list_s3_contents()

    # Project Setup:
    #client.list_projects()
    #client.get_project_details(1)
    #client.list_labels(project_id=2)

    # Task Creation:
    # client.create_task(CREATE_TASK_FILE)

    # Data Import:
    # client.upload_image_to_taskID(task_id=5, server_files=server_files, cloud_storage_id=1)

    # Get Labels for a Task:
    client.get_labels_for_task(1)

if __name__ == "__main__":
    main()
