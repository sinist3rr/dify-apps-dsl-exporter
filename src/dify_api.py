import asyncio
import logging
import os

import httpx
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DIFY_ORIGIN = os.getenv("DIFY_ORIGIN", "http://localhost")
BASE_URL = f"{DIFY_ORIGIN}/console/api"
EMAIL = os.getenv("EMAIL")
PASSWORD = os.getenv("PASSWORD")
logger.info(f"Using Dify API at {BASE_URL} with email {EMAIL}")

MAX_CONCURRENT_TASKS = 3
semaphore = asyncio.Semaphore(MAX_CONCURRENT_TASKS)


async def execute_api(
    client: httpx.AsyncClient,
    url: str,
    access_token: str | None = None,
    params: dict[str, str] | None = None,
    payload: dict | None = None,
    method_type: str = "POST",
    retries: int = 3,
) -> dict:
    """
    Execute an API request with retries and optional authorization.

    :param client: An instance of httpx.AsyncClient
    :param url: Target API endpoint URL
    :param access_token: Bearer token for authentication (optional)
    :param params: Query parameters to include in the request (for GET)
    :param payload: Request payload to send (for POST)
    :param method_type: HTTP method (currently supports only 'POST')
    :param retries: Number of retry attempts on failure
    :return: Response body as a dictionary
    :raises Exception: If all retry attempts fail
    """
    headers = {"Authorization": f"Bearer {access_token}"} if access_token else None
    async with semaphore:
        for attempt in range(retries):
            match method_type:
                case "POST":
                    response = await client.post(url, headers=headers, params=params, json=payload)
                case "GET":
                    response = await client.get(url, headers=headers, params=params)
                case "DELETE":
                    response = await client.delete(url, headers=headers)
                case _:
                    raise ValueError("Invalid method type")

            if response.status_code == 200:
                return response.json() if response.content else {}
            if method_type == "DELETE" and response.status_code == 204:
                return {}
            else:
                print(f"Attempt {attempt + 1} failed: {response.status_code} - {url}")
                await asyncio.sleep(0.5)

    raise Exception(f"API call failed after {retries} attempts: {url}")


async def login_and_get_token(client: httpx.AsyncClient) -> str:
    """
    Log in to the Dify API and retrieve an access token.

    :param client: An instance of httpx.AsyncClient
    :return: Access token string
    :raises Exception: If login fails or API call fails
    """
    payload = {"email": EMAIL, "password": PASSWORD}
    url = f"{BASE_URL}/login"
    response = await execute_api(client, url, payload=payload, method_type="POST")
    if response.get("result") == "success":
        access_token = response["data"]["access_token"]
        print("Access token obtained successfully")
        return access_token
    else:
        print(f"Login API error: {response.get('result')} - {url}")
    raise Exception("Login failed")


async def fetch_app_per_page(
    access_token: str, page: int, limit: int, client: httpx.AsyncClient
) -> dict:
    """
    Fetch a single page of app data from the Dify API.

    :param access_token: Access token for authentication
    :param page: Page number to fetch
    :param limit: Number of apps per page
    :param retries: Number of retry attempts on failure
    :param client: An instance of httpx.AsyncClient
    :return: Dictionary containing app data
    """
    return await execute_api(
        client,
        f"{BASE_URL}/apps",
        access_token=access_token,
        params={"page": page, "limit": limit},
        method_type="GET"
    )


async def get_app_list(access_token: str, client: httpx.AsyncClient) -> tuple[list, int]:
    """
    Retrieve all apps available to the authenticated user.

    :param access_token: Access token for authentication
    :param client: An instance of httpx.AsyncClient
    :return: Tuple of (list of app info dictionaries, total number of apps)
    """
    app_list = []
    page = 1
    limit = 30
    app_num = 0
    while True:
        content = await fetch_app_per_page(access_token, page, limit, client)

        if page == 1:
            app_num = content.get("total", 0)
            max_page_num = app_num // limit + (app_num % limit > 0)
            print(f"Total apps: {app_num}, Total pages: {max_page_num}")

        if app_num == 0:
            return [], 0

        if page > max_page_num:
            break

        app_per_page = [
            {"id": app.get("id"), "name": app.get("name")}
            for app in content.get("data", [])
        ]
        app_list.extend(app_per_page)
        page += 1

    return app_list, app_num


async def delete_app(access_token: str, app: dict, client: httpx.AsyncClient):
    """
    Delete a single app using its ID.

    :param access_token: Access token for authentication
    :param app: Dictionary with 'id' and 'name' keys
    :param client: HTTP client for making requests
    :return: None
    """
    url = f"{BASE_URL}/apps/{app['id']}"
    try:
        await execute_api(client, url, access_token=access_token, method_type="DELETE")
        print(f"🗑️  Deleted: {app['name']} (ID: {app['id']})")
    except Exception as e:
        print(f"❌ Failed to delete {app['name']} (ID: {app['id']}): {e}")


async def export_app(access_token: str, app_id: str, client: httpx.AsyncClient) -> bytes:
    """
    Export the app's DSL data as a bytes.

    :param access_token: Access token for authentication
    :param app_id: ID of the app to export
    :param client: An instance of httpx.AsyncClient
    :return: App DSL data as bytes
    :raises Exception: If the API call fails
    """
    url = f"{BASE_URL}/apps/{app_id}/export?include_secret=true"
    response = await execute_api(client, url, access_token, method_type="GET")
    return response.get("data").encode("utf-8")


async def import_app(access_token: str, yaml_content: str, client: httpx.AsyncClient) -> dict:
    """
    Import an app using YAML content.
    :param access_token: Access token for authentication
    :param yaml_content: YAML content to import
    :param client: An instance of httpx.AsyncClient
    :return: Response from the API
    """
    url = f"{BASE_URL}/apps/imports"
    payload = {
        "mode": "yaml-content",
        "yaml_content": yaml_content
    }
    return await execute_api(client, url, access_token, payload=payload, method_type="POST")
