import asyncio
import glob
import os

import httpx
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

DIFY_ORIGIN = os.getenv("DIFY_ORIGIN", "http://localhost")
BASE_URL = f"{DIFY_ORIGIN}/console/api"
EMAIL = os.getenv("EMAIL")
PASSWORD = os.getenv("PASSWORD")
DSL_FOLDER_PATH = "./dsl"

client = httpx.AsyncClient()
MAX_CONCURRENT_TASKS = 3
semaphore = asyncio.Semaphore(MAX_CONCURRENT_TASKS)


async def execute_api(
    url: str,
    access_token: str | None = None,
    payload: dict | None = None,
    method_type: str = "POST",
    retries: int = 3,
) -> dict:
    """
    Execute an API request with retries and optional authorization.

    :param url: Target API endpoint URL
    :param access_token: Bearer token for authentication (optional)
    :param payload: Request payload to send (for POST)
    :param method_type: HTTP method (currently supports only 'POST')
    :param retries: Number of retry attempts on failure
    :return: Response body as a dictionary
    :raises Exception: If all retry attempts fail
    """
    headers = {"Authorization": f"Bearer {access_token}"} if access_token else None

    for attempt in range(retries):
        try:
            async with semaphore:
                if method_type == "POST":
                    response = await client.post(url, headers=headers, json=payload)
                else:
                    raise ValueError("Only POST method is supported for import")

                if response.status_code == 200:
                    return response.json()
                else:
                    print(f"[{attempt+1}] Failed: {response.status_code} - {response.text}")
                    await asyncio.sleep(0.5)
        except Exception as e:
            print(f"[{attempt+1}] Exception: {e}")
            await asyncio.sleep(0.5)

    raise Exception(f"API call failed after {retries} attempts: {url}")


async def login_and_get_token() -> str:
    """
    Log in to the Dify API and retrieve an access token.

    :return: Access token string
    :raises Exception: If login fails or API call fails
    """
    payload = {"email": EMAIL, "password": PASSWORD}
    url = f"{BASE_URL}/login"
    response = await execute_api(url, payload=payload, method_type="POST")
    if response.get("result") == "success":
        access_token = response["data"]["access_token"]
        print("Access token obtained successfully")
        return access_token
    else:
        print(f"Login API error: {response.get('result')} - {url}")
    raise Exception("Login failed")


def get_dsl_files() -> list[str]:
    """
    Retrieve all .yml files from the DSL folder.

    :return: List of file paths to .yml files
    """
    yml_files = glob.glob(f"{DSL_FOLDER_PATH}/*.yml")
    if not yml_files:
        print("No YML files found in ./dsl")
        return []
    return yml_files


async def upload_yml_files(access_token: str, yml_files: list[str]):
    """
    Upload multiple YML files to the Dify API concurrently.

    :param access_token: Access token for authentication
    :param yml_files: List of paths to YML files to be uploaded
    """
    if not yml_files:
        print("No YML files to upload.")
        return

    tasks = [
        asyncio.create_task(upload_yml_file(access_token, file_path))
        for file_path in yml_files
    ]
    await asyncio.gather(*tasks)


async def upload_yml_file(access_token: str, file_path: str):
    """
    Upload a single YML file to the Dify API.

    :param access_token: Access token for authentication
    :param file_path: Path to the YML file
    """
    if not os.path.exists(file_path):
        print(f"❌ File not found: {file_path}")
        return

    with open(file_path, "r", encoding="utf-8") as file:
        yaml_content = file.read()

    if not yaml_content:
        print(f"❌ Skipping empty file: {file_path}")
        return

    payload = {
        "mode": "yaml-content",
        "yaml_content": yaml_content
    }

    url = f"{BASE_URL}/apps/imports"
    response = await execute_api(url, access_token, payload=payload, method_type="POST")
    app_name = os.path.basename(file_path)
    if response.get("status") == "completed":
        print(f"✅ Imported: {app_name} -> App ID: {response.get('app_id')}")
    else:
        print(f"❌ Failed to import: {app_name} -> Error: {response.get('error', 'Unknown error')}")


async def main():
    access_token = await login_and_get_token()
    yml_files = get_dsl_files()
    await upload_yml_files(access_token, yml_files)
    await client.aclose()


if __name__ == "__main__":
    asyncio.run(main())
