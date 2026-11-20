"""Restore one existing subscription to an enabled secondary 3X-UI panel.

Run from the repository root with ``python -m scripts.repair_panel_key``.
The default is a read-only check; pass --apply to create a missing client.
"""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from exabyte_bot.db import Database
from exabyte_bot.packages import get_plan
from exabyte_bot.xui import ClientSpec, XUIClient, client_method_for


async def repair(db_path: Path, email: str, panel_id: int, apply: bool) -> None:
    db = Database(db_path)
    await db.connect()
    client: XUIClient | None = None
    try:
        sub = await db.fetchone("SELECT * FROM subscriptions WHERE xui_email=?", (email,))
        panel = await db.fetchone("SELECT * FROM panels WHERE id=? AND enabled=1", (panel_id,))
        if sub is None or panel is None:
            raise SystemExit("Subscription or enabled panel was not found in this bot database")
        if not sub["multi_server"] and int(sub["panel_id"] or 0) != panel_id:
            raise SystemExit("This key is assigned to another panel; no change made")
        client = XUIClient(panel["base_url"], panel["username"], panel["password"],
                           verify_tls=bool(panel["verify_tls"]))
        inbound = await client.get_inbound(int(panel["inbound_id"]))
        if any(existing.get("email") == email for existing in inbound.clients):
            print(f"Key already exists on panel {panel_id}; no change made")
            return
        if not apply:
            print(f"Key is missing from panel {panel_id}; rerun with --apply to restore it")
            return
        plan = get_plan(sub["plan_id"]) if sub["plan_id"] else None
        spec = ClientSpec(
            email=email,
            password=sub["password"],
            method=client_method_for(panel["method"]),
            total_bytes=int(sub["quota_bytes"]),
            expiry_ms=int(sub["expiry_ms"]),
            limit_ip=plan.devices if plan else 1,
            enable=bool(sub["enabled"]),
            tg_id=int(sub["user_id"]),
            sub_id=sub["sub_id"],
            comment=sub["plan_id"] or "",
        )
        await client.add_client(int(panel["inbound_id"]), spec)
        inbound = await client.get_inbound(int(panel["inbound_id"]))
        if not any(existing.get("email") == email for existing in inbound.clients):
            raise SystemExit("Panel accepted the request but the key could not be verified")
        print(f"Restored and verified key on panel {panel_id}")
    finally:
        if client is not None:
            await client.aclose()
        await db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, required=True, help="The intended bot's SQLite database")
    parser.add_argument("--email", required=True, help="Exact key email from the bot database")
    parser.add_argument("--panel-id", type=int, required=True)
    parser.add_argument("--apply", action="store_true", help="Create the missing panel client")
    args = parser.parse_args()
    asyncio.run(repair(args.db, args.email, args.panel_id, args.apply))


if __name__ == "__main__":
    main()
