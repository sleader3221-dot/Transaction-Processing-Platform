from pathlib import Path

from azure.storage.blob import BlobServiceClient

from app.config import get_settings


settings = get_settings()


def is_enabled() -> bool:
    return bool(settings.BLOB_CONNECTION_STRING)


def upload_file(local_path: str, blob_name: str) -> str:
    service = BlobServiceClient.from_connection_string(settings.BLOB_CONNECTION_STRING)
    container = service.get_container_client(settings.BLOB_CONTAINER)
    try:
        container.create_container()
    except Exception:
        pass
    with Path(local_path).open("rb") as file_handle:
        container.upload_blob(name=blob_name, data=file_handle, overwrite=True)
    return f"blob://{settings.BLOB_CONTAINER}/{blob_name}"


def download_file(blob_uri: str, local_path: str) -> None:
    _, path = blob_uri.split("blob://", 1)
    container_name, blob_name = path.split("/", 1)
    service = BlobServiceClient.from_connection_string(settings.BLOB_CONNECTION_STRING)
    blob = service.get_blob_client(container=container_name, blob=blob_name)
    with Path(local_path).open("wb") as file_handle:
        blob.download_blob().readinto(file_handle)
