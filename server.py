#!/usr/bin/env python3
"""Japan Food Delivery MCP — Uber Eats JP via Apify actor.

Wraps the public Uber Eats scraper actor sourabhbgp~ubereats-scraper
(which supports Japan/JP locale) as an MCP tool so AI agents can query
Japanese restaurant and menu data.

Note: No dedicated Demae-can Apify actor exists; only Uber Eats JP is
supported in this first release.
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from typing import Any

from fastmcp import FastMCP

server = FastMCP("japan-food-delivery-mcp")

ACTOR_ID = "sourabhbgp~ubereats-scraper"
APIFY_API_BASE = "https://api.apify.com/v2"


def _token() -> str:
    return os.environ.get("APIFY_TOKEN", "").strip()


def _apify_call(endpoint: str, method: str = "GET", body: dict | None = None) -> dict[str, Any]:
    token = _token()
    if not token:
        return {"error": "APIFY_TOKEN not set in environment"}

    url = f"{APIFY_API_BASE}{endpoint}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }
    if body is not None:
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url, headers=headers, method=method)
    if body is not None:
        req.data = json.dumps(body).encode()

    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        return {"error": f"Apify HTTP {exc.code}: {exc.read().decode(errors='replace')[:500]}"}
    except Exception as exc:
        return {"error": str(exc)}


def _wait_for_run(run_id: str, timeout_secs: int = 180) -> tuple[str, dict[str, Any]]:
    """Poll until run completes, return (status, data)."""
    deadline = time.time() + timeout_secs
    while time.time() < deadline:
        resp = _apify_call(f"/actor-runs/{run_id}")
        data = (resp.get("data") or {})
        status = data.get("status", "")
        if status in ("SUCCEEDED", "FAILED", "ABORTED"):
            break
        time.sleep(3)
    return status, data


def _fetch_dataset(run_id: str, limit: int) -> dict[str, Any]:
    resp = _apify_call(f"/actor-runs/{run_id}/dataset/items?limit={limit}")
    if "error" in resp:
        return resp
    raw = resp.get("data", [])
    if isinstance(raw, list):
        items = raw
    elif isinstance(raw, dict):
        items = raw.get("items", [])
    else:
        items = []
    return {"runId": run_id, "count": len(items), "items": items[:limit]}


@server.tool()
async def search_restaurants(
    city: str = "Tokyo",
    cuisine: str | None = None,
    max_results: int = 20,
) -> dict[str, Any]:
    """Search restaurants on Uber Eats Japan.

    Args:
        city: City name in English or Japanese (e.g. "Tokyo", "東京", "Osaka").
        cuisine: Optional cuisine keyword (e.g. "sushi", "ramen").
        max_results: Max restaurants to return (default 20).

    Returns:
        List of restaurants with name, url, rating, price info, and menu items.
    """
    # Map common Japanese cities to Uber Eats slugs
    city_map = {
        "tokyo": "tokyo",
        "とうきょう": "tokyo",
        "osaka": "osaka",
        "おおさか": "osaka",
        "yokohama": "yokohama",
        "横浜": "yokohama",
        "nagoya": "nagoya",
        "名古屋": "nagoya",
        "sapporo": "sapporo",
        "さっぽろ": "sapporo",
        "fukuoka": "fukuoka",
        "ふくおか": "fukuoka",
        "kobe": "kobe",
        "こうべ": "kobe",
        "kyoto": "kyoto",
        "きょうと": "kyoto",
    }
    slug = city_map.get(city.lower(), city.lower())

    # Build URL for Japan Uber Eats
    base_url = f"https://www.ubereats.com/jp/{slug}/near-me"
    if cuisine:
        base_url = f"https://www.ubereats.com/jp/{slug}/{cuisine}/near-me"

    input_data = {
        "urls": [base_url],
        "country": "JP",
        "maxResults": max_results,
        "includeReviews": False,
    }

    run_result = _apify_call(f"/acts/{ACTOR_ID}/runs", method="POST", body={"input": input_data})
    if "error" in run_result:
        return run_result

    run_id = (run_result.get("data") or {}).get("id")
    if not run_id:
        return {"error": "Failed to start Apify run"}

    status, _ = _wait_for_run(run_id)
    if status != "SUCCEEDED":
        return {"error": f"Run ended with status: {status}"}

    return _fetch_dataset(run_id, limit=max_results)


@server.tool()
async def get_restaurant_menu(
    restaurant_url: str,
    max_items: int = 100,
) -> dict[str, Any]:
    """Get full menu for a specific Uber Eats Japan restaurant.

    Args:
        restaurant_url: Full Uber Eats restaurant URL (e.g. https://www.ubereats.com/jp/...).
        max_items: Max menu items to return.

    Returns:
        Restaurant info + menu categories with items (name, price, description, image).
    """
    input_data = {
        "urls": [restaurant_url],
        "country": "JP",
        "maxResults": max_items,
        "includeReviews": False,
    }

    run_result = _apify_call(f"/acts/{ACTOR_ID}/runs", method="POST", body={"input": input_data})
    if "error" in run_result:
        return run_result

    run_id = (run_result.get("data") or {}).get("id")
    if not run_id:
        return {"error": "Failed to start Apify run"}

    status, _ = _wait_for_run(run_id)
    if status != "SUCCEEDED":
        return {"error": f"Run ended with status: {status}"}

    result = _fetch_dataset(run_id, limit=max_items)
    items = result.get("items", [])
    if items:
        result["restaurant"] = items[0]
    return result


@server.tool()
async def get_japan_food_info() -> dict[str, Any]:
    """Get metadata about this MCP server and available data sources."""
    return {
        "server": "japan-food-delivery-mcp",
        "version": "0.1.0",
        "description": "Japan food delivery data via Uber Eats JP (Apify actor)",
        "platforms": ["ubereats-jp"],
        "note": "Demae-can support planned for v0.2 — no public Apify actor exists yet",
        "examples": {
            "search_restaurants": 'city="Tokyo", cuisine="sushi"',
            "get_restaurant_menu": "Use URL from search results",
        },
    }


if __name__ == "__main__":
    server.run()
