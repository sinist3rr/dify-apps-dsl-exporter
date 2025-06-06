import asyncio
import os

import httpx
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Settings
DIFY_ORIGIN = os.getenv("DIFY_ORIGIN", "http://localhost")
BASE_URL = f"{DIFY_ORIGIN}/console/api"
DSL_FOLDER_PATH = "./dsl"
EMAIL = os.getenv("EMAIL")
PASSWORD = os.getenv("PASSWORD")

client = httpx.AsyncClient()
MAX_CONCURRENT_TASKS = 3
semaphore = asyncio.Semaphore(MAX_CONCURRENT_TASKS)


async def execute_api(
    url: str,
    access_token: str | None = None,
    params: dict[str, str] | None = None,
    payload: dict[str, str] | None = None,
    method_type: str = "GET",
    retries: int = 3,
) -> dict:
    """
    Execute an API request with retries and optional authorization.

    :param url: Target API endpoint URL
    :param access_token: Bearer token for authentication (optional)
    :param payload: Request payload to send (for POST)
    :param method_type: HTTP method ('GET', 'POST', or 'DELETE')
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

    raise Exception(f"Failed to request API: {url}")


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


async def fetch_app_per_page(
    access_token: str, page: int, limit: int, retries: int = 3
) -> dict:
    """
    Fetch a single page of app data from the Dify API.

    :param access_token: Access token for authentication
    :param page: Page number to fetch
    :param limit: Number of apps per page
    :param retries: Number of retry attempts on failure
    :return: Dictionary containing app data
    """
    return await execute_api(
        f"{BASE_URL}/apps",
        access_token=access_token,
        params={"page": page, "limit": limit},
        method_type="GET",
        retries=retries,
    )


async def get_app_list(access_token: str) -> tuple[list, int]:
    """
    Retrieve all apps available to the authenticated user.

    :param access_token: Access token for authentication
    :return: Tuple of (list of app info dictionaries, total number of apps)
    """
    app_list = []
    page = 1
    limit = 30
    app_num = 0
    while True:
        content = await fetch_app_per_page(access_token, page, limit)

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


async def delete_apps(access_token: str, apps: list):
    """
    Delete all apps concurrently using their IDs.

    :param access_token: Access token for authentication
    :param apps: List of apps with 'id' and 'name' fields
    """
    tasks = [asyncio.create_task(delete_app(access_token, app)) for app in apps]
    await asyncio.gather(*tasks)


async def delete_app(access_token: str, app: dict):
    """
    Delete a single app using its ID.

    :param access_token: Access token for authentication
    :param app: Dictionary with 'id' and 'name' keys
    """
    url = f"{BASE_URL}/apps/{app['id']}"
    try:
        await execute_api(url, access_token=access_token, method_type="DELETE")
        print(f"🗑️  Deleted: {app['name']} (ID: {app['id']})")
    except Exception as e:
        print(f"❌ Failed to delete {app['name']} (ID: {app['id']}): {e}")


async def main():
    """
    Main routine to delete all apps.

    Steps:
    1. Authenticate and get an access token
    2. Fetch all apps
    3. Resolve name conflicts (for logging clarity)
    4. Delete each app concurrently
    """
    access_token = await login_and_get_token()
    apps, app_num = await get_app_list(access_token)

    if not apps:
        print("❌ No apps found.")
        return
    if len(apps) != app_num:
        print("❌ Mismatch in the number of apps.")
        return

    unique_apps = []
    same_app_names = []

    def check_uniquename():
        unique_names = set()
        for x in apps:
            if x['name'] in unique_names:
                modified_name = '【same】' + x['name'] + '-' + x['id'].split('-')[0]
                unique_apps.append({"id": x['id'], "name": modified_name})
                same_app_names.append(x['name'] + ' -> ' + modified_name)
            else:
                unique_apps.append(x)
                unique_names.add(x['name'])
        print(f"Same name app count: {len(apps) - len(unique_names)}, renamed list: {same_app_names}")

    check_uniquename()
    await delete_apps(access_token, unique_apps)
    await client.aclose()


if __name__ == "__main__":
    asyncio.run(main())
