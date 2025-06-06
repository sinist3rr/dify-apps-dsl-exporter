import asyncio
import os
import shutil

from dotenv import load_dotenv
import httpx

# Load environment variables from .env file
load_dotenv()

# Settings
DIFY_ORIGIN = os.getenv("DIFY_ORIGIN", "http://localhost")  # Dify origin URL
BASE_URL = f"{DIFY_ORIGIN}/console/api"  # Base URL for API
DSL_FOLDER_PATH = "./dsl"  # Folder to save YML files
EMAIL = os.getenv("EMAIL")  # Login email
PASSWORD = os.getenv("PASSWORD")  # Login password

client = httpx.AsyncClient()  # Global AsyncClient instance
# Set a maximum of 3 concurrent tasks
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
                    response = await client.post(
                        url, headers=headers, params=params, json=payload
                    )
                case "GET":
                    response = await client.get(url, headers=headers, params=params)
                case _:
                    raise ValueError("Invalid method type")

            if response.status_code == 200:
                return response.json()
            else:
                print(f"Attempt {attempt + 1} failed: {response.status_code} - {url}")
                await asyncio.sleep(0.5)  # Wait before retrying

    raise Exception(f"Failed to request api: {url}")


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
        print(f"Login API error: {response.get("result")} - {url}")
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
            # Calculate total pages from the first API response
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


def create_dsl_folder():
    """
    Ensure a clean DSL folder by removing it if it exists and creating a new one.
    """
    if os.path.exists(DSL_FOLDER_PATH):
        shutil.rmtree(DSL_FOLDER_PATH)
    os.makedirs(DSL_FOLDER_PATH)


async def download_yml_files(access_token: str, apps: list):
    """
    Download YML configuration files for each app concurrently.

    :param access_token: Access token for authentication
    :param apps: List of apps with 'id' and 'name' fields
    """
    create_dsl_folder()  # Create folder to save YML files
    tasks = [asyncio.create_task(download_yml_file(access_token, app)) for app in apps]
    await asyncio.gather(*tasks)  # Run all download tasks concurrently


async def download_yml_file(access_token, app):
    """
    Download the YML configuration file for a single app and save it locally.

    :param access_token: Access token for authentication
    :param app: Dictionary with 'id' and 'name' keys for the app
    """
    url = f"{BASE_URL}/apps/{app["id"]}/export?include_secret=true"
    # Limit the maximum number of concurrent tasks using a semaphore
    response = await execute_api(url, access_token, method_type="GET")
    dsl_data = response.get("data").encode("utf-8")
    replace_app_name = replace_appname(app["name"])
    file_name = f"{DSL_FOLDER_PATH}/{replace_app_name}.yml"

    with open(file_name, "wb") as file:
        file.write(dsl_data)
    print(f"✅ Downloaded: {file_name}")


def replace_appname(app_name):
    """
    Sanitize the app name by replacing slashes to make it file-system safe.

    :param app_name: Original app name string
    :return: Sanitized app name string
    """
    return app_name.replace("/", "-")


async def main():
    """
    Main routine to export all apps as YML files.

    Steps:
    1. Authenticate and get an access token
    2. Fetch all apps
    3. Resolve name conflicts
    4. Download YML for each app into the local folder
    """
    # 1. Get access token
    access_token = await login_and_get_token()
    if not access_token:
        print("Failed to obtain access token.")
        return

    # 2. Get the list of apps
    apps, app_num = await get_app_list(access_token)

    # 3. Check download feasibility
    if not apps:
        print("❌ No apps found.")
        return
    if len(apps) != app_num:
        print("❌ Mismatch in the number of apps.")
        return

    # 4. Check unique app name
    unique_apps = []
    same_app_names = []
    def check_uniquename():
        # all unique app names
        unique_names= set()
        for x in apps:
            # find same name
            if x['name'] in unique_names:
                # modify name
                modify_name = '【same】' + x['name'] + '-' + x['id'].split('-')[0]
                unique_apps.append({"id": x['id'], "name": modify_name})
                same_app_names.append(x['name'] + '->' + modify_name)
            else:
                unique_apps.append(x)
                unique_names.add(x['name'])
        # print notes
        print(f"Same name app nums: {len(apps)-len(unique_names)}, same name list : {same_app_names}")

    check_uniquename()

    # 4. Download YML files for all apps concurrently
    await download_yml_files(access_token, unique_apps)

    # 5. Close the client after finishing
    await client.aclose()


if __name__ == "__main__":
    asyncio.run(main())
