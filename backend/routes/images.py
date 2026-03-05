"""Image generation routes"""
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import FileResponse
from typing import List
from datetime import datetime, timezone, timedelta
from pathlib import Path
import uuid
import aiofiles
import httpx

from models.schemas import ImageGenerateRequest, GeneratedImageResponse
from middleware.auth import get_current_user
from db.connection import get_db
from routes.projects import verify_project_ownership

router = APIRouter(prefix="/api", tags=["images"])

# Settings
ROOT_DIR = Path(__file__).parent.parent
IMAGES_DIR = ROOT_DIR / "generated_images"
IMAGES_DIR.mkdir(exist_ok=True)

IMAGE_RATE_LIMIT_PER_HOUR = 10
VALID_IMAGE_SIZES = ["1024x1024", "1024x1792", "1792x1024"]


async def check_image_rate_limit(user_id: str) -> bool:
    """Check if user has exceeded image generation rate limit"""
    db = get_db()
    one_hour_ago = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    
    count = await db.generated_images.count_documents({
        "userId": user_id,
        "createdAt": {"$gte": one_hour_ago}
    })
    
    return count < IMAGE_RATE_LIMIT_PER_HOUR


@router.post("/projects/{project_id}/generate-image", response_model=GeneratedImageResponse)
async def generate_image(
    project_id: str,
    request: ImageGenerateRequest,
    current_user: dict = Depends(get_current_user)
):
    """Generate an AI image using OpenAI's gpt-image-1 model"""
    db = get_db()
    await verify_project_ownership(project_id, current_user["id"])
    
    if not request.prompt or len(request.prompt.strip()) < 3:
        raise HTTPException(status_code=400, detail="Prompt must be at least 3 characters")
    
    if len(request.prompt) > 4000:
        raise HTTPException(status_code=400, detail="Prompt must be less than 4000 characters")
    
    size = request.size or "1024x1024"
    if size not in VALID_IMAGE_SIZES:
        raise HTTPException(status_code=400, detail=f"Invalid size. Valid options: {VALID_IMAGE_SIZES}")
    
    if not await check_image_rate_limit(current_user["id"]):
        raise HTTPException(
            status_code=429, 
            detail=f"Rate limit exceeded. Maximum {IMAGE_RATE_LIMIT_PER_HOUR} images per hour."
        )
    
    import os
    from openai import OpenAI
    
    OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY', '')
    openai_client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None
    
    if not openai_client:
        raise HTTPException(status_code=500, detail="OpenAI API key not configured")
    
    try:
        response = openai_client.images.generate(
            model="gpt-image-1",
            prompt=request.prompt,
            size=size,
            n=1
        )
        
        image_data = response.data[0]
        
        if hasattr(image_data, 'b64_json') and image_data.b64_json:
            import base64
            image_bytes = base64.b64decode(image_data.b64_json)
        elif hasattr(image_data, 'url') and image_data.url:
            async with httpx.AsyncClient(timeout=60.0, verify=False) as http_client:
                img_response = await http_client.get(image_data.url)
                image_bytes = img_response.content
        else:
            raise HTTPException(status_code=500, detail="No image data returned from OpenAI")
        
        image_id = str(uuid.uuid4())
        image_filename = f"{image_id}.png"
        image_path = IMAGES_DIR / image_filename
        
        async with aiofiles.open(image_path, 'wb') as f:
            await f.write(image_bytes)
        
        image_doc = {
            "id": image_id,
            "projectId": project_id,
            "userId": current_user["id"],
            "prompt": request.prompt,
            "imagePath": image_filename,
            "size": size,
            "createdAt": datetime.now(timezone.utc).isoformat()
        }
        await db.generated_images.insert_one(image_doc)
        
        return GeneratedImageResponse(
            id=image_id,
            projectId=project_id,
            prompt=request.prompt,
            imagePath=image_filename,
            imageUrl=f"/api/images/{image_id}",
            size=size,
            createdAt=image_doc["createdAt"]
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate image: {str(e)[:100]}")


@router.get("/images/{image_id}")
async def get_image(image_id: str, current_user: dict = Depends(get_current_user)):
    """Get a generated image by ID"""
    db = get_db()
    image = await db.generated_images.find_one({"id": image_id}, {"_id": 0})
    if not image:
        raise HTTPException(status_code=404, detail="Image not found")
    
    await verify_project_ownership(image["projectId"], current_user["id"])
    
    image_path = IMAGES_DIR / image["imagePath"]
    if not image_path.exists():
        raise HTTPException(status_code=404, detail="Image file not found")
    
    return FileResponse(
        path=image_path,
        media_type="image/png",
        filename=f"generated_{image_id}.png"
    )


@router.get("/projects/{project_id}/images", response_model=List[GeneratedImageResponse])
async def list_project_images(project_id: str, current_user: dict = Depends(get_current_user)):
    """List all generated images in a project"""
    db = get_db()
    await verify_project_ownership(project_id, current_user["id"])
    
    images = await db.generated_images.find(
        {"projectId": project_id},
        {"_id": 0}
    ).sort("createdAt", -1).to_list(100)
    
    return [
        GeneratedImageResponse(
            id=img["id"],
            projectId=img["projectId"],
            prompt=img["prompt"],
            imagePath=img["imagePath"],
            imageUrl=f"/api/images/{img['id']}",
            size=img.get("size", "1024x1024"),
            createdAt=img["createdAt"]
        )
        for img in images
    ]


@router.delete("/projects/{project_id}/images/{image_id}")
async def delete_image(project_id: str, image_id: str, current_user: dict = Depends(get_current_user)):
    """Delete a generated image"""
    db = get_db()
    await verify_project_ownership(project_id, current_user["id"])
    
    image = await db.generated_images.find_one({"id": image_id, "projectId": project_id})
    if not image:
        raise HTTPException(status_code=404, detail="Image not found")
    
    image_path = IMAGES_DIR / image["imagePath"]
    if image_path.exists():
        image_path.unlink()
    
    await db.generated_images.delete_one({"id": image_id})
    
    return {"message": "Image deleted successfully"}
