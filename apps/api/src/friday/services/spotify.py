from __future__ import annotations

import base64
import hashlib
import secrets
import subprocess
import time
from urllib.parse import urlencode

import httpx


class SpotifyService:
    def __init__(self, client_id: str, redirect_uri: str) -> None:
        self.client_id = client_id
        self.redirect_uri = redirect_uri
        self.pending: dict[str, str] = {}
        self.access_token: str | None = None
        self.refresh_token: str | None = None

    @property
    def connected(self) -> bool:
        return self.access_token is not None

    def authorization_url(self) -> str:
        state = secrets.token_urlsafe(24)
        verifier = secrets.token_urlsafe(64)
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
        self.pending[state] = verifier
        return "https://accounts.spotify.com/authorize?" + urlencode({
            "client_id": self.client_id, "response_type": "code", "redirect_uri": self.redirect_uri,
            "scope": "user-read-playback-state user-modify-playback-state user-top-read",
            "state": state, "code_challenge_method": "S256", "code_challenge": challenge,
        })

    def exchange(self, code: str, state: str) -> None:
        verifier = self.pending.pop(state, None)
        if not verifier:
            raise PermissionError("Invalid Spotify OAuth state")
        response = httpx.post("https://accounts.spotify.com/api/token", data={
            "client_id": self.client_id, "grant_type": "authorization_code", "code": code,
            "redirect_uri": self.redirect_uri, "code_verifier": verifier,
        }, timeout=20)
        response.raise_for_status()
        payload = response.json()
        self.access_token = payload["access_token"]
        self.refresh_token = payload.get("refresh_token")

    def refresh_access_token(self) -> None:
        if not self.refresh_token:
            raise PermissionError("Reconnect Spotify to obtain a refresh token")
        response = httpx.post("https://accounts.spotify.com/api/token", data={
            "client_id": self.client_id,
            "grant_type": "refresh_token",
            "refresh_token": self.refresh_token,
        }, timeout=20)
        if response.status_code in {400, 401}:
            raise PermissionError("Spotify authorization expired; reconnect Spotify")
        response.raise_for_status()
        payload = response.json()
        self.access_token = payload["access_token"]
        self.refresh_token = payload.get("refresh_token", self.refresh_token)

    def search_and_play(self, query: str) -> dict[str, str]:
        if not self.access_token:
            raise PermissionError("Connect Spotify before requesting playback")
        self.refresh_access_token()
        headers = {"Authorization": f"Bearer {self.access_token}"}
        search = httpx.get("https://api.spotify.com/v1/search", params={"q": query, "type": "track", "limit": 1}, headers=headers, timeout=20)
        search.raise_for_status()
        items = search.json().get("tracks", {}).get("items", [])
        if not items:
            raise ValueError("No matching Spotify track was found")
        track = items[0]
        subprocess.run(["open", "-a", "Spotify"], check=False, capture_output=True)
        devices: list[dict] = []
        for attempt in range(5):
            devices_response = httpx.get("https://api.spotify.com/v1/me/player/devices", headers=headers, timeout=20)
            devices_response.raise_for_status()
            devices = [item for item in devices_response.json().get("devices", []) if item.get("id") and not item.get("is_restricted")]
            if devices:
                break
            if attempt < 4:
                time.sleep(1)
        if not devices:
            raise RuntimeError("No available Spotify Connect device after opening Spotify. Select this Mac once in Spotify's device picker.")
        device = next((item for item in devices if item.get("is_active")), devices[0])
        if not device.get("is_active"):
            transfer = httpx.put("https://api.spotify.com/v1/me/player", json={"device_ids": [device["id"]], "play": False}, headers=headers, timeout=20)
            transfer.raise_for_status()
        play = httpx.put("https://api.spotify.com/v1/me/player/play", params={"device_id": device["id"]}, json={"uris": [track["uri"]]}, headers=headers, timeout=20)
        play.raise_for_status()
        return {"name": track["name"], "artist": ", ".join(item["name"] for item in track["artists"]), "uri": track["uri"], "device": device["name"]}
