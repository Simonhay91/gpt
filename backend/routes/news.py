"""
Hacker News API integration
Fetches top tech news from Hacker News (Y Combinator)
"""
from fastapi import APIRouter
import httpx
import asyncio
from datetime import datetime, timezone
from typing import List, Optional

router = APIRouter(prefix="/news", tags=["news"])

HN_API_BASE = "https://hacker-news.firebaseio.com/v0"

async def fetch_story(client: httpx.AsyncClient, story_id: int) -> Optional[dict]:
    """Fetch a single story from HN API"""
    try:
        response = await client.get(f"{HN_API_BASE}/item/{story_id}.json", timeout=5.0)
        if response.status_code == 200:
            data = response.json()
            if data and data.get("type") == "story" and not data.get("deleted"):
                return {
                    "id": data.get("id"),
                    "title": data.get("title", ""),
                    "url": data.get("url", ""),
                    "score": data.get("score", 0),
                    "author": data.get("by", ""),
                    "commentsCount": data.get("descendants", 0),
                    "time": data.get("time", 0),
                    "hnUrl": f"https://news.ycombinator.com/item?id={data.get('id')}"
                }
    except Exception:
        pass
    return None

@router.get("/top")
async def get_top_news(limit: int = 20):
    """
    Get top tech news from Hacker News
    
    - **limit**: Number of stories to return (default: 20, max: 50)
    """
    limit = min(limit, 50)  # Cap at 50
    
    async with httpx.AsyncClient() as client:
        # Get top story IDs
        try:
            response = await client.get(f"{HN_API_BASE}/topstories.json", timeout=10.0)
            story_ids = response.json()[:limit * 2]  # Fetch extra in case some fail
        except Exception as e:
            return {"stories": [], "error": f"Failed to fetch stories: {str(e)}"}
        
        # Fetch stories in parallel
        tasks = [fetch_story(client, sid) for sid in story_ids]
        results = await asyncio.gather(*tasks)
        
        # Filter out None results and limit
        stories = [s for s in results if s is not None][:limit]
        
        return {
            "stories": stories,
            "fetchedAt": datetime.now(timezone.utc).isoformat(),
            "source": "Hacker News"
        }

@router.get("/best")
async def get_best_news(limit: int = 20):
    """Get best stories from Hacker News"""
    limit = min(limit, 50)
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{HN_API_BASE}/beststories.json", timeout=10.0)
            story_ids = response.json()[:limit * 2]
        except Exception as e:
            return {"stories": [], "error": f"Failed to fetch stories: {str(e)}"}
        
        tasks = [fetch_story(client, sid) for sid in story_ids]
        results = await asyncio.gather(*tasks)
        stories = [s for s in results if s is not None][:limit]
        
        return {
            "stories": stories,
            "fetchedAt": datetime.now(timezone.utc).isoformat(),
            "source": "Hacker News - Best"
        }

@router.get("/new")
async def get_new_news(limit: int = 20):
    """Get newest stories from Hacker News"""
    limit = min(limit, 50)
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{HN_API_BASE}/newstories.json", timeout=10.0)
            story_ids = response.json()[:limit * 2]
        except Exception as e:
            return {"stories": [], "error": f"Failed to fetch stories: {str(e)}"}
        
        tasks = [fetch_story(client, sid) for sid in story_ids]
        results = await asyncio.gather(*tasks)
        stories = [s for s in results if s is not None][:limit]
        
        return {
            "stories": stories,
            "fetchedAt": datetime.now(timezone.utc).isoformat(),
            "source": "Hacker News - New"
        }
