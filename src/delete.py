import asyncio

import httpx

import dify_api


async def delete_apps(access_token: str, apps: list, client: httpx.AsyncClient):
    """
    Delete all apps concurrently using their IDs.

    :param access_token: Access token for authentication
    :param apps: List of apps with 'id' and 'name' fields
    :param client: HTTP client for making requests
    """
    tasks = [asyncio.create_task(dify_api.delete_app(access_token, app, client)) for app in apps]
    await asyncio.gather(*tasks)


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
    Main routine to delete all apps.

    Steps:
    1. Authenticate and get an access token
    2. Fetch all apps
    3. Resolve name conflicts (for logging clarity)
    4. Delete each app concurrently
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

    # 3. Check download feasibility
    if not apps:
        print("❌ No apps found.")
        return
    if len(apps) != app_num:
        print("❌ Mismatch in the number of apps.")
        return

    # 4. Check unique app name
    unique_apps, same_app_names = make_unique_app_names(apps)
    print(f"Same name app count: {len(apps) - len(unique_apps)}, renamed list: {same_app_names}")

    async with httpx.AsyncClient() as client:
        # 5. Delete all apps concurrently
        print("Deleting apps...")
        await delete_apps(access_token, unique_apps, client)


if __name__ == "__main__":
    asyncio.run(main())
