"""Refresh the unmodified APK from Outline's documented official release URL."""
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import zipfile

import httpx

URL = "https://s3.amazonaws.com/outline-releases/client/android/stable/Outline-Client.apk"
DEST = Path(__file__).resolve().parents[1] / "exabyte_bot/assets/downloads"

if __name__ == "__main__":
    response = httpx.get(URL, follow_redirects=True, timeout=120)
    response.raise_for_status()
    content = response.content
    with zipfile.ZipFile(io.BytesIO(content)) as apk:
        if "AndroidManifest.xml" not in apk.namelist():
            raise ValueError("Download is not an Android package")
    DEST.mkdir(parents=True, exist_ok=True)
    (DEST / "Outline-Client.apk").write_bytes(content)
    manifest = {"source": URL, "downloaded_at": datetime.now(timezone.utc).isoformat(),
                "bytes": len(content), "sha256": hashlib.sha256(content).hexdigest()}
    (DEST / "manifest.json").write_text(json.dumps(manifest, indent=2)+"\n", encoding="utf-8")
    print(json.dumps(manifest))
