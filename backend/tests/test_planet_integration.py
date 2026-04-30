"""
Test script for PlanetWorkspace API integration + matching pipeline.
Run from backend/ directory:
    python -m pytest tests/test_planet_integration.py -v -s

Or directly:
    python tests/test_planet_integration.py
"""
import asyncio
import os
import sys
from pathlib import Path

# Load .env before anything else
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

import httpx

PARTNER_KEY = os.environ.get("PLANET_PARTNER_KEY", "")
BASE_URL = os.environ.get("PLANET_API_URL", "https://api-prod.planetworkspace.com")
HEADERS = {"x-partner-key": PARTNER_KEY}

BACKEND_URL = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001")


# ── 1. Direct external API tests ─────────────────────────────────────────────

async def test_external_categories():
    print("\n── 1. GET /web/category ──")
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.get(f"{BASE_URL}/web/category", headers=HEADERS)
    print(f"   Status: {r.status_code}")
    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text[:200]}"
    data = r.json()
    assert isinstance(data, list) and len(data) > 0, "Expected non-empty list"
    print(f"   Root categories: {len(data)}")
    for cat in data[:3]:
        print(f"     [{cat['id']}] {cat['name']} — {len(cat.get('children', []))} children")
    return data


async def test_external_brands():
    print("\n── 2. GET /web/brand ──")
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.get(f"{BASE_URL}/web/brand", headers=HEADERS)
    print(f"   Status: {r.status_code}")
    assert r.status_code == 200
    data = r.json()
    print(f"   Brands: {len(data)}")
    for b in data[:3]:
        print(f"     [{b['id']}] {b['name']}")
    return data


async def test_external_products():
    print("\n── 3. POST /web/product/explore ──")
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.post(
            f"{BASE_URL}/web/product/explore",
            headers={**HEADERS, "Content-Type": "application/json"},
            json={"page": 1, "limit": 5},
        )
    print(f"   Status: {r.status_code}")
    assert r.status_code == 200, f"Expected 200: {r.text[:200]}"
    data = r.json()
    items = data.get("products") or data.get("items") or (data if isinstance(data, list) else [])
    total = data.get("total", len(items)) if isinstance(data, dict) else len(items)
    total_pages = data.get("totalPages", 1) if isinstance(data, dict) else 1
    print(f"   Total products: {total}, Pages: {total_pages}")
    print(f"   First {len(items)} products:")
    for p in items:
        print(f"     [{p.get('id')}] {p.get('name')} | model={p.get('model')} | crm={p.get('crmCode')} | brand={p.get('brandName')}")
    return items


async def test_external_category_attrs(categories):
    print("\n── 4. GET /web/category/{slug}/attributes ──")
    # Find a leaf category with a slug to test
    leaf = None
    for root in categories:
        for child in root.get("children", []):
            if child.get("slug"):
                leaf = child
                break
        if leaf:
            break

    if not leaf:
        print("   No leaf category found, skipping")
        return

    slug = leaf["slug"]
    print(f"   Testing slug: {slug}")
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.get(f"{BASE_URL}/web/category/{slug}/attributes", headers=HEADERS)
    print(f"   Status: {r.status_code}")
    if r.status_code == 200:
        attrs = r.json()
        print(f"   Attributes: {len(attrs)}")
        for a in attrs[:3]:
            vals = a.get("selectionValues", [])[:4]
            print(f"     [{a['id']}] {a['name']} ({a['type']}) — values: {vals}")
    else:
        print(f"   404/error (expected for some slugs)")


# ── 2. Normalizer test ────────────────────────────────────────────────────────

def test_normalizer(raw_products):
    print("\n── 5. Normalizer test ──")
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from services.planet_api import _normalize
    for p in raw_products[:3]:
        n = _normalize(p)
        print(f"   {n['title_en'][:40]:<40} | article={n['article_number']} | crm={n['crm_code']} | vendor={n['vendor']}")
        # Verify all pipeline-expected fields exist
        for field in ("title_en", "article_number", "crm_code", "vendor", "product_model", "datasheet_url", "aliases", "embedding"):
            assert field in n, f"Missing field: {field}"
    print("   All pipeline fields present ✓")


# ── 3. Backend proxy tests (requires backend running) ─────────────────────────

async def test_backend_login():
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.post(f"{BACKEND_URL}/api/auth/login", json={
            "email": "admin@ai.planetworkspace.com",
            "password": "Admin@123456",
        })
    if r.status_code == 200:
        return r.json().get("token")
    return None


async def test_backend_proxy(token: str):
    print("\n── 6. Backend proxy /api/planet/categories ──")
    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.get(f"{BACKEND_URL}/api/planet/categories", headers=headers)
    print(f"   Status: {r.status_code}")
    if r.status_code == 200:
        data = r.json()
        print(f"   Root categories via proxy: {len(data)} ✓")
    else:
        print(f"   Error: {r.text[:200]}")

    print("\n── 7. Backend proxy POST /api/planet/products ──")
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.post(
            f"{BACKEND_URL}/api/planet/products",
            headers={**headers, "Content-Type": "application/json"},
            json={"page": 1, "limit": 3},
        )
    print(f"   Status: {r.status_code}")
    if r.status_code == 200:
        data = r.json()
        items = data.get("products", [])
        print(f"   Products via proxy: {len(items)} items, total={data.get('total')} ✓")
    else:
        print(f"   Error: {r.text[:200]}")


# ── Main ──────────────────────────────────────────────────────────────────────

async def main():
    print("=" * 60)
    print("PlanetWorkspace Integration Test")
    print(f"Partner key: {PARTNER_KEY[:8]}...{PARTNER_KEY[-4:] if len(PARTNER_KEY) > 12 else '(not set)'}")
    print("=" * 60)

    if not PARTNER_KEY:
        print("❌ PLANET_PARTNER_KEY not set in .env")
        return

    errors = []

    try:
        categories = await test_external_categories()
        print("   ✓ Categories OK")
    except Exception as e:
        print(f"   ✗ {e}")
        errors.append("categories")
        categories = []

    try:
        await test_external_brands()
        print("   ✓ Brands OK")
    except Exception as e:
        print(f"   ✗ {e}")
        errors.append("brands")

    try:
        raw_products = await test_external_products()
        print("   ✓ Products OK")
    except Exception as e:
        print(f"   ✗ {e}")
        errors.append("products")
        raw_products = []

    if categories:
        try:
            await test_external_category_attrs(categories)
            print("   ✓ Attributes OK")
        except Exception as e:
            print(f"   ✗ {e}")

    if raw_products:
        try:
            test_normalizer(raw_products)
        except Exception as e:
            print(f"   ✗ Normalizer: {e}")
            errors.append("normalizer")

    # Backend proxy (only if running)
    print(f"\n── Backend at {BACKEND_URL} ──")
    token = await test_backend_login()
    if token:
        print(f"   Login ✓  token={token[:20]}...")
        await test_backend_proxy(token)
    else:
        print("   Backend not running or login failed — skipping proxy tests")

    print("\n" + "=" * 60)
    if errors:
        print(f"❌ Failed: {', '.join(errors)}")
    else:
        print("✅ All external API tests passed")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
