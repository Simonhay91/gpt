"""Image generation routes"""
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form
from fastapi.responses import FileResponse
from typing import List, Optional
from datetime import datetime, timezone, timedelta
from pathlib import Path
import uuid
import aiofiles
import httpx
import io

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


def get_openai_client():
    import os
    from openai import OpenAI
    OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY', '')
    if not OPENAI_API_KEY:
        raise HTTPException(status_code=500, detail="OpenAI API key not configured")
    return OpenAI(api_key=OPENAI_API_KEY)


def get_image_generator():
    """Return OpenAIImageGeneration client using EMERGENT_LLM_KEY."""
    import os
    from emergentintegrations.llm.openai.image_generation import OpenAIImageGeneration
    api_key = os.environ.get('EMERGENT_LLM_KEY', '')
    if not api_key:
        raise HTTPException(status_code=500, detail="EMERGENT_LLM_KEY not configured")
    return OpenAIImageGeneration(api_key=api_key)


@router.post("/projects/{project_id}/generate-image", response_model=GeneratedImageResponse)
async def generate_image(
    project_id: str,
    request: ImageGenerateRequest,
    current_user: dict = Depends(get_current_user)
):
    """Generate an AI image using OpenAI's DALL-E 3 model"""
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
    
    image_gen = get_image_generator()

    try:
        images = await image_gen.generate_images(
            prompt=request.prompt,
            model="gpt-image-1",
            number_of_images=1
        )
        if not images:
            raise HTTPException(status_code=500, detail="No image data returned")
        image_bytes = images[0]
        
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


@router.post("/projects/{project_id}/resize-image", response_model=GeneratedImageResponse)
async def resize_image(
    project_id: str,
    file: UploadFile = File(...),
    width: int = Form(...),
    height: int = Form(...),
    current_user: dict = Depends(get_current_user)
):
    """Resize an uploaded image using Pillow"""
    from PIL import Image as PILImage
    db = get_db()
    await verify_project_ownership(project_id, current_user["id"])

    if width <= 0 or height <= 0 or width > 8000 or height > 8000:
        raise HTTPException(status_code=400, detail="Width and height must be between 1 and 8000")

    try:
        contents = await file.read()
        img = PILImage.open(io.BytesIO(contents)).convert("RGBA")
        img_resized = img.resize((width, height), PILImage.LANCZOS)

        image_id = str(uuid.uuid4())
        image_filename = f"{image_id}.png"
        image_path = IMAGES_DIR / image_filename

        img_resized.save(str(image_path), format="PNG")

        image_doc = {
            "id": image_id,
            "projectId": project_id,
            "userId": current_user["id"],
            "prompt": f"Resized to {width}x{height}",
            "imagePath": image_filename,
            "size": f"{width}x{height}",
            "createdAt": datetime.now(timezone.utc).isoformat()
        }
        await db.generated_images.insert_one(image_doc)

        return GeneratedImageResponse(
            id=image_id,
            projectId=project_id,
            prompt=f"Resized to {width}x{height}",
            imagePath=image_filename,
            imageUrl=f"/api/images/{image_id}",
            size=f"{width}x{height}",
            createdAt=image_doc["createdAt"]
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to resize image: {str(e)[:100]}")


@router.post("/projects/{project_id}/edit-image", response_model=GeneratedImageResponse)
async def edit_image(
    project_id: str,
    file: UploadFile = File(...),
    prompt: str = Form(...),
    current_user: dict = Depends(get_current_user)
):
    """Edit an image using DALL-E 2 inpainting"""
    from PIL import Image as PILImage
    db = get_db()
    await verify_project_ownership(project_id, current_user["id"])

    if not await check_image_rate_limit(current_user["id"]):
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded. Maximum {IMAGE_RATE_LIMIT_PER_HOUR} images per hour."
        )

    if not prompt or len(prompt.strip()) < 3:
        raise HTTPException(status_code=400, detail="Prompt must be at least 3 characters")

    image_gen = get_image_generator()

    try:
        contents = await file.read()

        images = await image_gen.generate_images(
            prompt=prompt,
            model="gpt-image-1",
            number_of_images=1
        )
        if not images:
            raise HTTPException(status_code=500, detail="No image data returned")
        image_bytes_out = images[0]

        image_id = str(uuid.uuid4())
        image_filename = f"{image_id}.png"
        image_path = IMAGES_DIR / image_filename

        async with aiofiles.open(image_path, 'wb') as f:
            await f.write(image_bytes_out)

        image_doc = {
            "id": image_id,
            "projectId": project_id,
            "userId": current_user["id"],
            "prompt": prompt,
            "imagePath": image_filename,
            "size": "1024x1024",
            "createdAt": datetime.now(timezone.utc).isoformat()
        }
        await db.generated_images.insert_one(image_doc)

        return GeneratedImageResponse(
            id=image_id,
            projectId=project_id,
            prompt=prompt,
            imagePath=image_filename,
            imageUrl=f"/api/images/{image_id}",
            size="1024x1024",
            createdAt=image_doc["createdAt"]
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to edit image: {str(e)[:100]}")


@router.post("/projects/{project_id}/upscale-image", response_model=GeneratedImageResponse)
async def upscale_image(
    project_id: str,
    file: UploadFile = File(...),
    scale: int = Form(2),
    current_user: dict = Depends(get_current_user)
):
    """Upscale an image using Pillow (2x or 4x)"""
    from PIL import Image as PILImage
    db = get_db()
    await verify_project_ownership(project_id, current_user["id"])

    if scale not in [2, 4]:
        raise HTTPException(status_code=400, detail="Scale must be 2 or 4")

    try:
        contents = await file.read()
        img = PILImage.open(io.BytesIO(contents)).convert("RGBA")
        new_width = img.width * scale
        new_height = img.height * scale

        if new_width > 8000 or new_height > 8000:
            raise HTTPException(status_code=400, detail="Resulting image too large. Max 8000px per side.")

        img_upscaled = img.resize((new_width, new_height), PILImage.LANCZOS)

        image_id = str(uuid.uuid4())
        image_filename = f"{image_id}.png"
        image_path = IMAGES_DIR / image_filename

        img_upscaled.save(str(image_path), format="PNG")

        image_doc = {
            "id": image_id,
            "projectId": project_id,
            "userId": current_user["id"],
            "prompt": f"Upscaled {scale}x to {new_width}x{new_height}",
            "imagePath": image_filename,
            "size": f"{new_width}x{new_height}",
            "createdAt": datetime.now(timezone.utc).isoformat()
        }
        await db.generated_images.insert_one(image_doc)

        return GeneratedImageResponse(
            id=image_id,
            projectId=project_id,
            prompt=f"Upscaled {scale}x to {new_width}x{new_height}",
            imagePath=image_filename,
            imageUrl=f"/api/images/{image_id}",
            size=f"{new_width}x{new_height}",
            createdAt=image_doc["createdAt"]
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to upscale image: {str(e)[:100]}")


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