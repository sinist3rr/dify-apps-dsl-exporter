import asyncio
import glob
import os
import httpx
import dify_api
import logging
from typing import Optional

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

DSL_FOLDER_PATH = "./dsl"


def get_dsl_files() -> list[str]:
    """
    Retrieve all .yml files from the DSL folder.

    :return: List of file paths to .yml files
    """
    yml_files = glob.glob(f"{DSL_FOLDER_PATH}/*.yml")
    if not yml_files:
        logger.error("❌ No YML files found in %s", DSL_FOLDER_PATH)
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
        logger.error("❌ File not found: %s", file_path)
        return

    # Read YAML content
    with open(file_path, "r", encoding="utf-8") as file:
        yaml_content = file.read()

    if not yaml_content:
        logger.warning("Skipping empty file: %s", file_path)
        return

    # Determine application name from file name
    app_name = os.path.splitext(os.path.basename(file_path))[0]

    # Fetch existing apps to find a matching one
    try:
        apps, _ = await dify_api.get_app_list(access_token, client)
    except Exception as e:
        logger.error("❌ Failed to fetch app list: %s", e)
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
        logger.error("❌ Exception during import: %s", e)
        return

    # Report result and publish if successful
    if response.get("status") == "completed":
        # Determine if it was an update or a create
        was_update = bool(app_id)
        app_id_result = response.get("app_id")
        action = "Updated" if was_update else "Created"
        logger.info("✅ %s: %s -> App ID: %s", action, app_name, app_id_result)

        # Publish the workflow
        try:
            pub_resp = await dify_api.publish_app(
                access_token=access_token,
                app_id=app_id_result,
                client=client
            )
            if pub_resp.get("result") == "success":
                logger.info("🚀 Published: %s", app_name)
            else:
                logger.error("❌ Publish indicated failure for %s: result=%s", app_name, pub_resp.get("result"))
        except Exception as e:
            logger.error("❌ Exception during publish: %s", e)
    else:
        error_msg = response.get("error", response.get("message", "Unknown error"))
        logger.error("❌ Failed to import %s: %s", app_name, error_msg)


async def main():
    yml_files = get_dsl_files()
    if not yml_files:
        logger.error("❌ No YML files found to upload.")
        return

    async with httpx.AsyncClient() as client:
        access_token = await dify_api.login_and_get_token(client)
        await upload_yml_files(access_token, yml_files, client)


if __name__ == "__main__":
    asyncio.run(main())
