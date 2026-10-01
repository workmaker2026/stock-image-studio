import os
import base64
import datetime
import json
import anthropic

from constants import STOCK_CATEGORIES

MEDIA_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
}


def _client():
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set (check your .env)")
    return anthropic.Anthropic(api_key=api_key)


def _text_of(message):
    for block in message.content:
        if block.type == "text":
            return block.text
    raise RuntimeError("no text block in model response")


def _parse_json(text):
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        start = min((i for i in (text.find("{"), text.find("[")) if i != -1), default=0)
        end = max(text.rfind("}"), text.rfind("]")) + 1
        text = text[start:end]
    return json.loads(text)


def suggest_topics(n=12):
    today = datetime.date.today().strftime("%Y-%m-%d (%A)")
    message = _client().messages.create(
        model="claude-sonnet-5",
        max_tokens=4096,
        messages=[
            {
                "role": "user",
                "content": (
                    f"Today is {today}. Rank the top {n} stock-image keywords/topics that would sell well on "
                    "Adobe Stock / Freepik / Miricanvas right now, considering the current season, upcoming "
                    "holidays, and general commercial demand (business, lifestyle, tech, food, nature, etc). "
                    "Order from most to least in-demand. For each topic give 3 distinct scene variations "
                    "(different composition/angle/subject) as ready-to-use English generation prompts.\n\n"
                    "Reply with ONLY this JSON array, no other text:\n"
                    '[{"topic": "short Korean label", "scenes": ["English prompt 1", "English prompt 2", "English prompt 3"]}, ...]'
                ),
            }
        ],
    )
    return _parse_json(_text_of(message))


def generate_metadata(image_path, prompt_hint=""):
    ext = os.path.splitext(str(image_path))[1].lower()
    media_type = MEDIA_TYPES.get(ext)
    if not media_type:
        raise ValueError(f"metadata generation needs a raster image (png/jpg/webp), got {ext}")

    client = _client()
    with open(image_path, "rb") as f:
        img_b64 = base64.standard_b64encode(f.read()).decode()

    categories_text = "\n".join(f"{k}: {v}" for k, v in STOCK_CATEGORIES.items())
    message = client.messages.create(
        model="claude-sonnet-5",
        max_tokens=2048,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": img_b64}},
                    {
                        "type": "text",
                        "text": (
                            "This is a stock image for Adobe Stock. "
                            f'Generation prompt: "{prompt_hint}"\n\n'
                            "Reply with ONLY this JSON, no other text:\n"
                            '{"title": "<=70 chars, no commas, English", '
                            '"keywords": "up to 50 English keywords ordered by relevance, comma-separated", '
                            '"keywords_ko": "up to 50 Korean keywords ordered by relevance, comma-separated", '
                            '"category_id": <best matching number from the list below>}\n\n'
                            f"Categories:\n{categories_text}"
                        ),
                    },
                ],
            }
        ],
    )
    return _parse_json(_text_of(message))
