import os
import requests

BASE_URL = "https://external.api.recraft.ai/v1"


def _headers():
    key = os.environ.get("RECRAFT_API_KEY")
    if not key:
        raise RuntimeError("RECRAFT_API_KEY is not set (check your .env)")
    return {"Authorization": f"Bearer {key}"}


def generate_image(prompt, model, style, n=1):
    is_vector = model.endswith("_vector")
    payload = {"prompt": prompt, "model": model, "n": n}
    if style:
        payload["style"] = style
    if not is_vector:
        payload["image_format"] = "png"
    resp = requests.post(f"{BASE_URL}/images/generations", headers=_headers(), json=payload, timeout=180)
    resp.raise_for_status()
    return resp.json()["data"]


def _post_file(endpoint, file_path, extra=None):
    with open(file_path, "rb") as f:
        files = {"file": f}
        data = {"image_format": "png", **(extra or {})}
        resp = requests.post(f"{BASE_URL}/images/{endpoint}", headers=_headers(), files=files, data=data, timeout=180)
    resp.raise_for_status()
    return resp.json()["image"]["url"]


def remove_background(file_path):
    return _post_file("removeBackground", file_path)


def vectorize(file_path):
    with open(file_path, "rb") as f:
        resp = requests.post(f"{BASE_URL}/images/vectorize", headers=_headers(), files={"file": f}, timeout=180)
    resp.raise_for_status()
    return resp.json()["image"]["url"]


def upscale(file_path, mode="crisp"):
    endpoint = "crispUpscale" if mode == "crisp" else "creativeUpscale"
    return _post_file(endpoint, file_path)
