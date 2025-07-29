import asyncio
import os
import shutil

import httpx

import dify_api

from dotenv import load_dotenv

load_dotenv()
DSL_FOLDER_PATH = "./dsl"
TAG_ENV = os.getenv("DSL_EXPORT_TAGS")
TAG_FILTERS = [t.strip() for t in TAG_ENV.split(",") if t.strip()]


def create_dsl_folder():
    """
    Ensure a clean DSL folder by removing it if it exists and creating a new one.
    """
    if os.path.exists(DSL_FOLDER_PATH):
        shutil.rmtree(DSL_FOLDER_PATH)
    os.makedirs(DSL_FOLDER_PATH)


async def download_yml_files(access_token: str, apps: list, client: httpx.AsyncClient):
    """
    Download YML configuration files for each app concurrently.

    :param access_token: Access token for authentication
    :param apps: List of apps with 'id' and 'name' fields
    :param client: An instance of httpx.AsyncClient
    """
    create_dsl_folder()  # Create folder to save YML files
    tasks = [asyncio.create_task(download_yml_file(access_token, app, client)) for app in apps]
    await asyncio.gather(*tasks)  # Run all download tasks concurrently


async def download_yml_file(access_token: str, app: dict, client: httpx.AsyncClient) -> None:
    """
    Download the YML configuration file for a single app and save it locally.

    :param access_token: Access token for authentication
    :param app: Dictionary with 'id' and 'name' keys for the app
    :param client: An instance of httpx.AsyncClient
    """
    dsl_data = await dify_api.export_app(access_token, app["id"], client)
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


def make_unique_app_names(apps: list[dict]) -> tuple[list[dict], list[str]]:
    """
    Ensure all app names are unique by appending ID prefix to duplicates.

    :param apps: List of app dictionaries with 'id' and 'name'
    :return: Tuple of (list with unique app names, list of renamed name mappings)
    """
    unique_apps = []
    same_app_names = []
    seen_names = set()

    for app in apps:
        name = app["name"]
        if name in seen_names:
            modified_name = f"【same】{name}-{app['id'].split('-')[0]}"
            unique_apps.append({"id": app["id"], "name": modified_name})
            same_app_names.append(f"{name} -> {modified_name}")
        else:
            unique_apps.append(app)
            seen_names.add(name)

    return unique_apps, same_app_names


async def main():
    """
    Main routine to export all apps as YML files.

    Steps:
    1. Authenticate and get an access token
    2. Fetch all apps
    3. Resolve name conflicts
    4. Download YML for each app into the local folder
    """
    async with httpx.AsyncClient() as client:
        # 1. Get access token
        access_token = await dify_api.login_and_get_token(client)
    if not access_token:
        print("Failed to obtain access token.")
        return

    async with httpx.AsyncClient() as client:
        # 2. Get the list of apps
        apps, app_num = await dify_api.get_app_list(access_token, client)
        # right after fetch — dump what we got
        print(f"🔍 Found {len(apps)} apps:")
        for a in apps:
            print(f" • {a['name']}  (id={a['id']}), tags={a['tags'] or '‹no tags›'}")

        if TAG_FILTERS:
            filtered = [
                app for app in apps
                if set(TAG_FILTERS).intersection(set(app.get("tags", [])))
            ]
            print(f"🗂️ Exporting {len(filtered)}/{len(apps)} apps matching tags {TAG_FILTERS}")
            apps = filtered

    # 3. Check download feasibility
    if not apps:
        print("❌ No apps found.")
        return

    # 4. Check unique app name
    unique_apps, same_app_names = make_unique_app_names(apps)
    print(f"Same name app count: {len(apps) - len(unique_apps)}, renamed list: {same_app_names}")

    async with httpx.AsyncClient() as client:
        # 5. Download YML files for all apps concurrently
        print("Starting to download YML files...")
        await download_yml_files(access_token, unique_apps, client)


if __name__ == "__main__":
    asyncio.run(main())
