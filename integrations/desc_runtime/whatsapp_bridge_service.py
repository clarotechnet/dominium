from __future__ import annotations

import json
import os
import shutil
import subprocess
import threading
import time
from pathlib import Path
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


WHATSAPP_ALLOWED_GROUPS = {
    "natal": {
        "jid": "120363028547806621@g.us",
        "jids": [
            "120363028547806621@g.us",
            "120363423496684075@g.us",
        ],
        "automation_jids": [
            "120363028547806621@g.us",
            "120363423496684075@g.us",
        ],
        "label": "DESC NTL/PWM",
    },
    "fortaleza": {
        "jid": "120363397790697942@g.us",
        "label": "DESC FTZ",
    },
    "recife": {
        "jid": "120363425385335332@g.us",
        "label": "DESC JCR",
    },
    "mossoro": {
        "jid": "120363420013377509@g.us",
        "label": "DESC MRO",
    },
}


class WhatsAppBridgeError(RuntimeError):
    pass


class WhatsAppBridgeService:
    def __init__(
        self,
        root: Path,
        *,
        port: int | None = None,
        request: Callable[[str, str, dict | None], dict] | None = None,
    ) -> None:
        self.root = Path(root)
        self.connector_root = self.root / "whatsapp_connector"
        self.data_root = self.root / "config" / "whatsapp_bridge"
        self.log_path = self.root / "logs" / "whatsapp-bridge.log"
        self.port = int(port or os.environ.get("DOMINIUM_WHATSAPP_PORT", "8767"))
        self._request_override = request
        self._process: subprocess.Popen | None = None
        self._lock = threading.RLock()
        self._log_stream = None

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    def dependency_ready(self) -> bool:
        return (
            (self.connector_root / "server.mjs").is_file()
            and (self.connector_root / "node_modules").is_dir()
        )

    @staticmethod
    def node_executable() -> str:
        configured = str(os.environ.get("DOMINIUM_NODE", "")).strip()
        if configured and Path(configured).is_file():
            return configured
        discovered = shutil.which("node")
        if discovered:
            return discovered
        bundled = (
            Path(os.environ.get("USERPROFILE", ""))
            / ".cache"
            / "codex-runtimes"
            / "codex-primary-runtime"
            / "dependencies"
            / "node"
            / "bin"
            / "node.exe"
        )
        if bundled.is_file():
            return str(bundled)
        raise WhatsAppBridgeError(
            "Node.js nao localizado. Configure DOMINIUM_NODE com o executavel."
        )

    def start_process(self) -> dict:
        with self._lock:
            if self._process is not None and self._process.poll() is None:
                return self.status()
            existing = self.status()
            if existing.get("ok") is True:
                # A connector from the previous panel process may still own the
                # local port. Reuse it instead of spawning a duplicate.
                return existing
            if not self.dependency_ready():
                return {
                    "ok": False,
                    "state": "setup_required",
                    "connected": False,
                    "error": (
                        "Conector nao instalado. Execute npm.cmd install "
                        "na pasta whatsapp_connector."
                    ),
                }
            self.data_root.mkdir(parents=True, exist_ok=True)
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            self._log_stream = self.log_path.open("a", encoding="utf-8")
            environment = os.environ.copy()
            environment["DOMINIUM_WHATSAPP_PORT"] = str(self.port)
            environment["DOMINIUM_WHATSAPP_DATA"] = str(self.data_root)
            environment["DOMINIUM_WHATSAPP_ALLOWED_GROUPS"] = json.dumps(
                WHATSAPP_ALLOWED_GROUPS,
                ensure_ascii=True,
            )
            startupinfo = None
            creationflags = 0
            if os.name == "nt":
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                creationflags = subprocess.CREATE_NO_WINDOW
            self._process = subprocess.Popen(
                [self.node_executable(), "server.mjs"],
                cwd=self.connector_root,
                env=environment,
                stdin=subprocess.DEVNULL,
                stdout=self._log_stream,
                stderr=subprocess.STDOUT,
                startupinfo=startupinfo,
                creationflags=creationflags,
            )
        for _ in range(30):
            time.sleep(0.1)
            result = self.status()
            if result.get("state") != "offline":
                return result
        return self.status()

    def stop_process(self) -> None:
        with self._lock:
            process = self._process
            self._process = None
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
        if self._log_stream is not None:
            self._log_stream.close()
            self._log_stream = None

    def _request(self, method: str, path: str, payload: dict | None = None) -> dict:
        if self._request_override is not None:
            return self._request_override(method, path, payload)
        body = None
        headers = {}
        if payload is not None:
            body = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"
        request = Request(
            f"{self.base_url}{path}",
            data=body,
            headers=headers,
            method=method,
        )
        try:
            with urlopen(request, timeout=5.0) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            try:
                message = json.loads(detail).get("error", detail)
            except json.JSONDecodeError:
                message = detail
            raise WhatsAppBridgeError(str(message)) from exc
        except (URLError, TimeoutError, OSError) as exc:
            raise WhatsAppBridgeError(str(exc)) from exc

    def status(self) -> dict:
        if not self.dependency_ready():
            return {
                "ok": False,
                "state": "setup_required",
                "connected": False,
                "error": "Dependencias do conector WhatsApp nao instaladas.",
            }
        try:
            return self._request("GET", "/status")
        except WhatsAppBridgeError:
            return {
                "ok": False,
                "state": "offline",
                "connected": False,
                "error": "Conector WhatsApp local esta desligado.",
            }

    def connect(self) -> dict:
        status = self.start_process()
        if status.get("state") == "setup_required":
            return status
        return self._request("POST", "/start", {})

    def logout(self) -> dict:
        return self._request("POST", "/logout", {})

    def clear_messages(self, profile: str = "") -> dict:
        return self._request(
            "POST",
            "/clear-messages",
            {"profile": str(profile).strip().lower()},
        )

    def messages(self, limit: int = 200, profile: str = "") -> dict:
        safe_limit = max(1, min(500, int(limit)))
        normalized_profile = str(profile).strip().lower()
        try:
            result = self._request(
                "GET",
                f"/messages?limit={safe_limit}&profile={normalized_profile}",
            )
        except WhatsAppBridgeError as exc:
            # The inbox is polled every few seconds even while the connector is
            # intentionally logged out.  Treat that as an empty, unavailable
            # inbox instead of leaking the local connection error as HTTP 500.
            return {
                "ok": False,
                "state": "offline",
                "connected": False,
                "messages": [],
                "error": "Conector WhatsApp local esta desligado.",
                "detail": str(exc),
            }
        allowed = WHATSAPP_ALLOWED_GROUPS.get(normalized_profile)
        allowed_jids = {
            str(jid).strip()
            for jid in (
                (allowed or {}).get("jids")
                or [(allowed or {}).get("jid", "")]
            )
            if str(jid).strip()
        }
        raw_messages = result.get("messages", [])
        result["messages"] = [
            item
            for item in raw_messages
            if (
                (
                    not allowed
                    or str(item.get("chat_jid", "")) in allowed_jids
                )
                and any(
                    str(contract).isdigit()
                    and 7 <= len(str(contract)) <= 9
                    for contract in item.get("contracts", [])
                )
            )
        ]
        return result

    def automation_status(self, profile: str = "natal") -> dict:
        normalized = str(profile or "natal").strip().lower()
        try:
            return self._request("GET", f"/automation?profile={normalized}")
        except WhatsAppBridgeError as exc:
            return {
                "ok": False,
                "state": "offline",
                "connected": False,
                "enabled": False,
                "pilot_available": normalized in WHATSAPP_ALLOWED_GROUPS,
                "profile": normalized,
                "error": "Conector WhatsApp local esta desligado.",
                "detail": str(exc),
            }

    def set_automation(self, profile: str, enabled: bool) -> dict:
        return self._request(
            "POST",
            "/automation/toggle",
            {"profile": str(profile).strip().lower(), "enabled": enabled is True},
        )

    def claim_automation(self, profile: str = "natal") -> dict:
        return self._request(
            "POST",
            "/automation/claim",
            {"profile": str(profile or "natal").strip().lower()},
        )

    def update_automation(self, payload: dict) -> dict:
        return self._request("POST", "/automation/update", payload)

    def link_message(self, payload: dict) -> dict:
        return self._request("POST", "/link", payload)

    def record_toa_inspection(self, payload: dict) -> dict:
        return self._request("POST", "/toa-inspection", payload)

    def record_toa_retry_error(self, payload: dict) -> dict:
        return self._request("POST", "/toa-retry-error", payload)

    def react_confirmed(self, profile: str, record: dict) -> dict:
        if str(record.get("state", "")).lower() != "confirmed":
            return {"ok": True, "reacted": False, "reason": "not_confirmed"}
        num_os = str(record.get("num_os", "")).strip()
        contract = str(record.get("contract", "")).strip()
        if not num_os or not contract or not profile:
            return {"ok": True, "reacted": False, "reason": "identity_incomplete"}
        return self._request(
            "POST",
            "/react-confirmed",
            {
                "profile": str(profile),
                "contract": contract,
                "num_os": num_os,
            },
        )
