import asyncio
import glob
import os

import httpx

import dify_api

from typing import Optional

DSL_FOLDER_PATH = "./dsl"


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


async def upload_yml_files(access_token: str, yml_files: list[str], client: httpx.AsyncClient):
    """
    Upload multiple YML files to the Dify API concurrently.

    :param access_token: Access token for authentication
    :param yml_files: List of paths to YML files to be uploaded
    :param client: An instance of httpx.AsyncClient
    """
    tasks = [
        asyncio.create_task(upload_yml_file(access_token, file_path, client))
        for file_path in yml_files
    ]
    await asyncio.gather(*tasks)


async def upload_yml_file(
    access_token: str,
    file_path: str,
    client: httpx.AsyncClient
):
    """
    Upload a single YML file to the Dify API, updating existing workflows if they exist.

    :param access_token: Access token for authentication
    :param file_path: Path to the YML file
    :param client: An instance of httpx.AsyncClient
    """
    if not os.path.exists(file_path):
        print(f"❌ File not found: {file_path}")
        return

    # Read YAML content
    with open(file_path, "r", encoding="utf-8") as file:
        yaml_content = file.read()

    if not yaml_content:
        print(f"❌ Skipping empty file: {file_path}")
        return

    # Determine application name from file name
    app_name = os.path.splitext(os.path.basename(file_path))[0]

    # Fetch existing apps to find a matching one
    try:
        apps, _ = await dify_api.get_app_list(access_token, client)
    except Exception as e:
        print(f"❌ Failed to fetch app list: {e}")
        return

    # Match by name
    match = next((a for a in apps if a["name"] == app_name), None)
    app_id: Optional[str] = match["id"] if match else None

    # Import (create or update)
    try:
        response = await dify_api.import_app(
            access_token=access_token,
            yaml_content=yaml_content,
            client=client,
            app_id=app_id
        )
    except Exception as e:
        print(f"❌ Exception during import: {e}")
        return

    # Report result
    if response.get("status") == "completed":
        updated = "Updated" if app_id else "Created"
        print(f"✅ {updated}: {app_name} -> App ID: {response.get('app_id')}")
    else:
        error_msg = response.get("error", response.get("message", "Unknown error"))
        print(f"❌ Failed to import {app_name}: {error_msg}")


async def main():
    yml_files = get_dsl_files()
    if not yml_files:
        print("No YML files found to upload.")
        return

    async with httpx.AsyncClient() as client:
        access_token = await dify_api.login_and_get_token(client)
        await upload_yml_files(access_token, yml_files, client)


if __name__ == "__main__":
    asyncio.run(main())
