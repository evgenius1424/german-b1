"""Publish a generated Telegram manifest and its discussion-group comments."""

import json
import mimetypes
import os
import time
from pathlib import Path

import httpx

from .spec import TG_MESSAGE
from .telegram import TG_CAPTION, visible_len

DEFAULT_CHANNEL = "@german_b1_horen"
PUBLISH_STATE = "published.json"
MIN_INTERVAL = 3.1


class PublishError(RuntimeError):
    pass


def _load_dotenv(path):
    if not path.exists():
        return
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        key, value = line.split("=", 1)
        key, value = key.strip(), value.strip()
        if value[:1] in ("'", '"') and value[-1:] == value[:1]:
            value = value[1:-1]
        os.environ.setdefault(key, value)


def _load_manifest(exam_dir):
    path = exam_dir / "telegram.json"
    if not path.exists():
        raise PublishError(f"missing manifest: {path}")
    manifest = json.loads(path.read_text())
    if not isinstance(manifest.get("posts"), list):
        raise PublishError("telegram.json is not using the posts manifest layout")
    return manifest


def validate_manifest(manifest, exam_dir):
    posts = manifest["posts"]
    if len(posts) != 4:
        raise PublishError(f"expected 4 posts, found {len(posts)}")
    audio_files = 0
    comments = 0
    for post in posts:
        if post.get("method") not in {"sendMessage", "sendAudio", "sendMediaGroup"}:
            raise PublishError(f"unsupported method in manifest: {post.get('method')}")
        captions = [post.get("params", {}).get("caption", "")]
        captions += [item.get("caption", "") for item in post.get("media", [])]
        if any(visible_len(c) > TG_CAPTION for c in captions):
            raise PublishError(f"caption on {post.get('id')} exceeds {TG_CAPTION} chars")
        if post.get("method") == "sendAudio":
            rel = post.get("files", {}).get("audio")
            if not rel or not (exam_dir / rel).is_file():
                raise PublishError(f"missing audio file for {post.get('id')}")
            audio_files += 1
        if post.get("method") == "sendMediaGroup":
            media = post.get("media", [])
            if not 2 <= len(media) <= 10:
                raise PublishError(f"invalid media group size for {post.get('id')}")
            for item in media:
                rel = item.get("file")
                if not rel or not (exam_dir / rel).is_file():
                    raise PublishError(f"missing audio file for {post.get('id')}")
                audio_files += 1
        for comment in post.get("comments", []):
            if visible_len(comment.get("text", "")) > TG_MESSAGE:
                raise PublishError(f"comment on {post.get('id')} exceeds {TG_MESSAGE} chars")
            comments += 1
    return {"posts": len(posts), "audio_files": audio_files, "comments": comments}


def _upload_name(item, path):
    """Clean file name for listeners who save the audio: "Teil 1 - Text 1.mp3"."""
    title = item.get("title")
    return f"{title.replace(' · ', ' - ')}{path.suffix}" if title else path.name


class Publisher:
    def __init__(self, exam_dir, manifest, token, chat_id, state):
        self.exam_dir = exam_dir
        self.manifest = manifest
        self.token = token
        self.chat_id = chat_id
        self.state = state
        self.last_request = 0.0
        self.base_url = f"https://api.telegram.org/bot{token}"
        self.client = httpx.Client(timeout=35)

    def close(self):
        self.client.close()

    def _wait(self):
        delay = MIN_INTERVAL - (time.monotonic() - self.last_request)
        if delay > 0:
            time.sleep(delay)

    def _request(self, method, params=None, files=None):
        while True:
            self._wait()
            url = f"{self.base_url}/{method}"
            if files:
                response = self.client.post(url, data=params or {}, files=files)
            else:
                response = self.client.post(url, json=params or {})
            self.last_request = time.monotonic()
            try:
                body = response.json()
            except ValueError as exc:
                raise PublishError(f"Telegram returned HTTP {response.status_code}") from exc
            if body.get("ok"):
                return body["result"]
            if body.get("error_code") == 429:
                retry = body.get("parameters", {}).get("retry_after", 5)
                time.sleep(max(1, int(retry)))
                continue
            description = body.get("description", f"HTTP {response.status_code}")
            raise PublishError(f"Telegram {method} failed: {description}")

    def _send_post(self, post):
        method = post["method"]
        if method == "sendMessage":
            params = dict(post["params"])
            params["chat_id"] = self.chat_id
            return [self._request(method, params=params)]
        if method == "sendAudio":
            params = dict(post["params"])
            params["chat_id"] = self.chat_id
            rel = post["files"]["audio"]
            path = self.exam_dir / rel
            with path.open("rb") as audio:
                files = {"audio": (_upload_name(post["params"], path), audio, mimetypes.guess_type(path.name)[0] or "audio/mpeg")}
                return [self._request(method, params=params, files=files)]
        if method == "sendMediaGroup":
            media = []
            handles = []
            files = {}
            try:
                for i, item in enumerate(post["media"]):
                    path = self.exam_dir / item["file"]
                    handle = path.open("rb")
                    handles.append(handle)
                    field = f"audio{i}"
                    media.append({k: v for k, v in item.items() if k != "file"} | {"media": f"attach://{field}"})
                    files[field] = (_upload_name(item, path), handle, mimetypes.guess_type(path.name)[0] or "audio/mpeg")
                params = {"chat_id": self.chat_id, "media": json.dumps(media, ensure_ascii=False)}
                return self._request(method, params=params, files=files)
            finally:
                for handle in handles:
                    handle.close()
        raise PublishError(f"unsupported method: {method}")

    def _save(self):
        target = self.exam_dir / PUBLISH_STATE
        temp = target.with_suffix(".tmp")
        temp.write_text(json.dumps(self.state, ensure_ascii=False, indent=2) + "\n")
        temp.replace(target)

    def _webhook_guard(self):
        info = self._request("getWebhookInfo")
        if info.get("url"):
            raise PublishError("Telegram webhook is configured; disable it before publishing comments")
        if not self._request("getChat", params={"chat_id": self.chat_id}).get("linked_chat_id"):
            raise PublishError(f"{self.chat_id} has no linked discussion group; comments would fail. "
                               "Link one in the channel settings (Discussion) and make the bot an admin there")

    def _find_forward(self, channel_message_id, timeout=30):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            params = {"timeout": 5}
            if self.state.get("update_offset") is not None:
                params["offset"] = self.state["update_offset"]
            updates = self._request("getUpdates", params=params)
            for update in updates:
                self.state["update_offset"] = update["update_id"] + 1
                message = update.get("message")
                if not message:
                    continue
                origin = message.get("forward_origin", {})
                origin_chat = origin.get("chat", {})
                origin_username = origin_chat.get("username", "")
                wanted_username = str(self.chat_id).lstrip("@")
                origin_matches = (str(origin_chat.get("id")) == str(self.chat_id) or
                                  origin_username == wanted_username)
                if (origin.get("type") == "channel" and origin_matches and
                        origin.get("message_id") == channel_message_id):
                    self._save()
                    return {"chat_id": message["chat"]["id"], "message_id": message["message_id"]}
                legacy_chat = message.get("forward_from_chat") or {}
                legacy_matches = (str(legacy_chat.get("id")) == str(self.chat_id) or
                                  legacy_chat.get("username") == wanted_username)
                if legacy_matches:
                    if message.get("forward_from_message_id") == channel_message_id:
                        self._save()
                        return {"chat_id": message["chat"]["id"], "message_id": message["message_id"]}
            self._save()
        raise PublishError(
            f"did not receive discussion-group forward for channel message {channel_message_id}. "
            f"Posts sent before the discussion group was linked never get one: delete them in the "
            f"channel, delete {PUBLISH_STATE} and publish again")

    def publish(self):
        self._webhook_guard()
        for post in self.manifest["posts"]:
            record = self.state["posts"].setdefault(post["id"], {})
            if not record.get("channel_message_ids"):
                record["channel_message_ids"] = [m["message_id"] for m in self._send_post(post)]
                self._save()
            if post.get("comments"):
                forwarded = record.get("forwarded")
                if not forwarded:
                    forwarded = self._find_forward(record["channel_message_ids"][0])
                    record["forwarded"] = forwarded
                    self._save()
                sent = record.setdefault("comment_message_ids", [])
                for comment in post["comments"][len(sent):]:
                    params = dict(comment)
                    params["chat_id"] = forwarded["chat_id"]
                    params["reply_parameters"] = {"message_id": forwarded["message_id"]}
                    result = self._request("sendMessage", params=params)
                    sent.append(result["message_id"])
                    self._save()
        return self.state


def publish(exam_dir, chat_id=None, dry_run=False):
    _load_dotenv(Path.cwd() / ".env")
    manifest = _load_manifest(exam_dir)
    counts = validate_manifest(manifest, exam_dir)
    if dry_run:
        print(f"dry-run: {counts['posts']} posts, {counts['audio_files']} audio files, "
              f"{counts['comments']} comments")
        return
    token = os.environ.get("BOT_KEY")
    if not token:
        raise PublishError("BOT_KEY is not set in .env or the environment")
    chat_id = chat_id or os.environ.get("BOT_CHAT_ID") or manifest.get("channel") or DEFAULT_CHANNEL
    state_path = exam_dir / PUBLISH_STATE
    if state_path.exists():
        state = json.loads(state_path.read_text())
        if state.get("exam_id") != manifest.get("exam_id") or state.get("chat_id") != chat_id:
            raise PublishError(f"{state_path} belongs to another exam or chat")
    else:
        state = {"exam_id": manifest["exam_id"], "chat_id": chat_id, "posts": {}}
    publisher = Publisher(exam_dir, manifest, token, chat_id, state)
    try:
        publisher.publish()
    finally:
        publisher.close()
    print(f"published {counts['posts']} posts, {counts['comments']} comments")
