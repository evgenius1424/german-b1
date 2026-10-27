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


def _exam_file(exam_dir, rel, post_id):
    """Resolve a manifest file while keeping uploads inside the exam directory."""
    if not isinstance(rel, str) or not rel:
        raise PublishError(f"missing audio file for {post_id}")
    root = exam_dir.resolve()
    path = (exam_dir / rel).resolve()
    if not path.is_relative_to(root):
        raise PublishError(f"audio file for {post_id} is outside the exam directory")
    if not path.is_file():
        raise PublishError(f"missing audio file for {post_id}")
    return path


TEIL_POSTS = ["teil1", "teil2", "teil3", "teil4"]
VOCAB_POST = "vocab"


def _validate_vocab(post):
    """The optional fifth post: one plain HTML message, no comments."""
    if post.get("method") != "sendMessage" or post.get("comments"):
        raise PublishError("vocab post must be a single sendMessage without comments")
    text = post.get("params", {}).get("text", "")
    if not text or visible_len(text) > TG_MESSAGE:
        raise PublishError(f"vocab post is empty or exceeds {TG_MESSAGE} chars")


def validate_manifest(manifest, exam_dir):
    """Four Teil posts in order, optionally followed by the vocab post."""
    posts = manifest["posts"]
    ids = [post.get("id") for post in posts]
    if ids not in (TEIL_POSTS, TEIL_POSTS + [VOCAB_POST]):
        raise PublishError(f"expected posts {', '.join(TEIL_POSTS)} [+ {VOCAB_POST}], found {ids}")
    vocab = posts[4:]
    for post in vocab:
        _validate_vocab(post)
    posts = posts[:4]
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
            _exam_file(exam_dir, rel, post.get("id"))
            audio_files += 1
        if post.get("method") == "sendMediaGroup":
            media = post.get("media", [])
            if not 2 <= len(media) <= 10:
                raise PublishError(f"invalid media group size for {post.get('id')}")
            for item in media:
                _exam_file(exam_dir, item.get("file"), post.get("id"))
                audio_files += 1
        for comment in post.get("comments", []):
            if visible_len(comment.get("text", "")) > TG_MESSAGE:
                raise PublishError(f"comment on {post.get('id')} exceeds {TG_MESSAGE} chars")
            comments += 1
    return {"posts": len(posts) + len(vocab), "audio_files": audio_files, "comments": comments,
            "vocab": len(vocab)}


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
        # Album uploads can take Telegram well over 35 s to acknowledge.
        self.client = httpx.Client(timeout=httpx.Timeout(35, read=120))

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
            path = _exam_file(self.exam_dir, rel, post.get("id"))
            with path.open("rb") as audio:
                files = {"audio": (_upload_name(post["params"], path), audio, mimetypes.guess_type(path.name)[0] or "audio/mpeg")}
                return [self._request(method, params=params, files=files)]
        if method == "sendMediaGroup":
            media = []
            handles = []
            files = {}
            try:
                for i, item in enumerate(post["media"]):
                    path = _exam_file(self.exam_dir, item.get("file"), post.get("id"))
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
            # Every channel post gets a discussion-group copy; comments reply to it and
            # unpublish deletes it. Without comments (vocab) a missing copy is not fatal.
            forwarded = record.get("forwarded")
            if not forwarded and (post.get("comments") or "forwarded" not in record):
                try:
                    forwarded = self._find_forward(record["channel_message_ids"][0])
                except PublishError:
                    if post.get("comments"):
                        raise
                record["forwarded"] = forwarded
                self._save()
            if post.get("comments"):
                sent = record.setdefault("comment_message_ids", [])
                for comment in post["comments"][len(sent):]:
                    params = dict(comment)
                    params["chat_id"] = forwarded["chat_id"]
                    params["reply_parameters"] = {"message_id": forwarded["message_id"]}
                    result = self._request("sendMessage", params=params)
                    sent.append(result["message_id"])
                    self._save()
        self._pin_first()
        return self.state

    def _pin_first(self, timeout=15):
        """Pin the exam's Teil 1 post silently and delete the channel's "pinned" notice.

        A failed pin (e.g. the bot lacks the pin right) only warns: the exam is out.
        """
        record = self.state["posts"].get(TEIL_POSTS[0], {})
        if record.get("pinned") or not record.get("channel_message_ids"):
            return
        try:
            self._request("pinChatMessage", params={
                "chat_id": self.chat_id, "message_id": record["channel_message_ids"][0],
                "disable_notification": True})
        except PublishError as exc:
            print(f"warning: could not pin teil1: {exc}")
            return
        record["pinned"] = True
        self._save()
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            params = {"timeout": 3}
            if self.state.get("update_offset") is not None:
                params["offset"] = self.state["update_offset"]
            for update in self._request("getUpdates", params=params):
                self.state["update_offset"] = update["update_id"] + 1
                post = update.get("channel_post") or {}
                if post.get("pinned_message", {}).get("message_id") == record["channel_message_ids"][0]:
                    self._save()
                    try:
                        self._request("deleteMessage", params={
                            "chat_id": post["chat"]["id"], "message_id": post["message_id"]})
                    except PublishError as exc:
                        print(f"warning: could not delete the pin notice: {exc}")
                    return
            self._save()


def publish(exam_dir, chat_id=None, dry_run=False):
    _load_dotenv(Path.cwd() / ".env")
    manifest = _load_manifest(exam_dir)
    counts = validate_manifest(manifest, exam_dir)
    if dry_run:
        print(f"dry-run: {counts['posts']} posts, {counts['audio_files']} audio files, "
              f"{counts['comments']} comments, vocab post: {'yes' if counts['vocab'] else 'no'}")
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


def _delete_targets(state):
    """Message ids to delete, in order: comments, discussion-group copies, then channel posts."""
    channel = state["chat_id"]
    comments, copies, posts = [], [], []
    for post_id, record in state["posts"].items():
        forwarded = record.get("forwarded")
        for mid in record.get("comment_message_ids", []):
            comments.append((post_id, "comment_message_ids", forwarded["chat_id"], mid))
        if forwarded:
            copies.append((post_id, "forwarded", forwarded["chat_id"], forwarded["message_id"]))
        for mid in record.get("channel_message_ids", []):
            posts.append((post_id, "channel_message_ids", channel, mid))
    return comments + copies + posts


def _forget(state, post_id, field, mid):
    """Drop one deleted message from the state so a retry skips it."""
    record = state["posts"][post_id]
    if field == "forwarded":
        record.pop("forwarded", None)
    else:
        record[field] = [m for m in record[field] if m != mid]


def unpublish(exam_dir, dry_run=False, token=None):
    """Delete an exam's Telegram messages and clear published.json as each one goes.

    Resumable: a message that is already gone counts as deleted, and anything that
    fails stays in published.json so the next run retries only that.
    """
    _load_dotenv(Path.cwd() / ".env")
    state_path = exam_dir / PUBLISH_STATE
    if not state_path.exists():
        print(f"nothing to delete: {state_path} does not exist")
        return
    state = json.loads(state_path.read_text())
    targets = _delete_targets(state)
    if dry_run:
        for post_id, field, chat, mid in targets:
            print(f"would delete {post_id} {field} {chat} {mid}")
        print(f"dry-run: {len(targets)} messages")
        return
    token = token or os.environ.get("BOT_KEY")
    if not token:
        raise PublishError("BOT_KEY is not set in .env or the environment")
    client = httpx.Client(timeout=35)
    url = f"https://api.telegram.org/bot{token}/deleteMessage"
    failed = []
    try:
        for post_id, field, chat, mid in targets:
            body = _delete_request(client, url, chat, mid)
            if body.get("ok") or "not found" in body.get("description", "").lower():
                _forget(state, post_id, field, mid)
                tmp = state_path.with_suffix(".tmp")
                tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n")
                tmp.replace(state_path)
                print(f"deleted {post_id} {chat} {mid}")
            else:
                failed.append(f"{post_id} {chat} {mid}: {body.get('description')}")
                print(f"FAILED {post_id} {chat} {mid}: {body.get('description')}")
    finally:
        client.close()
    if failed:
        raise PublishError(f"{len(failed)} messages could not be deleted; {state_path} keeps them for a retry")
    state_path.unlink()
    print(f"unpublished {len(targets)} messages; removed {state_path}")


def _delete_request(client, url, chat, mid):
    while True:
        time.sleep(MIN_INTERVAL)
        body = client.post(url, json={"chat_id": chat, "message_id": mid}).json()
        if body.get("error_code") == 429:
            time.sleep(max(1, int(body.get("parameters", {}).get("retry_after", 5))))
            continue
        return body
