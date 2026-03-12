"""
Source Insights and Smart Questions routes
AI-powered analysis of sources and question generation
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List
from datetime import datetime, timezone
import os
import json
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["insights"])

# Will be set by setup function
db = None
get_current_user = None


class SourceInsightsResponse(BaseModel):
    summary: str
    suggestedQuestions: List[str]
    generatedAt: str


class SaveInsightsRequest(BaseModel):
    summary: str
    suggestedQuestions: List[str]


class SmartQuestionsResponse(BaseModel):
    questions: List[str]
    sourceNames: List[str]
    generatedAt: str


def setup_insights_routes(database, auth_dependency):
    """Initialize routes with dependencies"""
    global db, get_current_user
    db = database
    get_current_user = auth_dependency


@router.post("/sources/{source_id}/analyze", response_model=SourceInsightsResponse)
async def analyze_source(source_id: str, current_user: dict = Depends(get_current_user)):
    """
    Analyze a source and generate insights (summary + suggested questions).
    Available to ALL users who can see the source.
    """
    source = await db.sources.find_one({"id": source_id}, {"_id": 0})
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    
    chunks = await db.source_chunks.find(
        {"sourceId": source_id},
        {"_id": 0}
    ).sort("chunkIndex", 1).to_list(50)
    
    if not chunks:
        raise HTTPException(status_code=400, detail="Source has no content to analyze")
    
    full_text = "\n\n".join([c.get("content") or c.get("text", "") for c in chunks])
    text_for_analysis = full_text[:8000]
    source_name = source.get("originalName") or source.get("url") or "Unknown"
    
    try:
        import anthropic
        CLAUDE_API_KEY = os.environ.get('CLAUDE_API_KEY', '')
        claude_client = anthropic.Anthropic(api_key=CLAUDE_API_KEY)
        
        analysis_prompt = f"""Analyze the following document and provide:
1. A brief summary (2-3 sentences) describing what this document contains
2. Exactly 5 specific questions that a user could ask about this document's content

IMPORTANT: Detect the language of the document and respond in THE SAME LANGUAGE as the document content. 
- If the document is in Armenian, respond in Armenian
- If the document is in Russian, respond in Russian  
- If the document is in English, respond in English

Document name: {source_name}
Document content:
{text_for_analysis}

Respond in JSON format:
{{
  "summary": "Your 2-3 sentence summary here (in document's language)",
  "questions": ["Question 1?", "Question 2?", "Question 3?", "Question 4?", "Question 5?"]
}}

Important: Respond ONLY with valid JSON, no additional text. Questions and summary must be in the SAME LANGUAGE as the document."""

        response = claude_client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            messages=[{"role": "user", "content": analysis_prompt}]
        )
        
        result_text = response.content[0].text.strip()
        if result_text.startswith("```"):
            result_text = result_text.split("```")[1]
            if result_text.startswith("json"):
                result_text = result_text[4:]
        result_text = result_text.strip()
        
        result = json.loads(result_text)
        
        return SourceInsightsResponse(
            summary=result.get("summary", "Unable to generate summary"),
            suggestedQuestions=result.get("questions", [])[:5],
            generatedAt=datetime.now(timezone.utc).isoformat()
        )
        
    except Exception as e:
        logger.error(f"Source analysis error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)[:100]}")


@router.post("/sources/{source_id}/save-insights")
async def save_source_insights(
    source_id: str, 
    data: SaveInsightsRequest,
    current_user: dict = Depends(get_current_user)
):
    """Save generated insights to a source"""
    source = await db.sources.find_one({"id": source_id}, {"_id": 0})
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    
    await db.sources.update_one(
        {"id": source_id},
        {"$set": {
            "insights": {
                "summary": data.summary,
                "suggestedQuestions": data.suggestedQuestions,
                "savedAt": datetime.now(timezone.utc).isoformat(),
                "savedBy": current_user["id"]
            }
        }}
    )
    
    return {"message": "Insights saved successfully"}


@router.get("/sources/{source_id}/insights")
async def get_source_insights(source_id: str, current_user: dict = Depends(lambda: get_current_user)):
    """Get saved insights for a source"""
    source = await db.sources.find_one({"id": source_id}, {"_id": 0, "insights": 1})
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    
    insights = source.get("insights")
    if not insights:
        return {"hasInsights": False}
    
    return {
        "hasInsights": True,
        "summary": insights.get("summary"),
        "suggestedQuestions": insights.get("suggestedQuestions", []),
        "savedAt": insights.get("savedAt")
    }


@router.post("/chats/{chat_id}/smart-questions", response_model=SmartQuestionsResponse)
async def generate_smart_questions(chat_id: str, current_user: dict = Depends(lambda: get_current_user)):
    """
    Generate smart question suggestions based on active sources in the chat.
    """
    chat = await db.chats.find_one({"id": chat_id}, {"_id": 0})
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    
    project_id = chat.get("projectId")
    source_mode = chat.get("sourceMode", "all")
    
    active_source_ids = []
    user_department_ids = current_user.get("departments", [])
    
    # Personal sources
    personal_sources = await db.sources.find({
        "level": "personal",
        "ownerId": current_user["id"],
        "status": {"$in": ["active", None]}
    }, {"_id": 0, "id": 1}).to_list(100)
    active_source_ids.extend([s["id"] for s in personal_sources])
    
    # Project sources
    if project_id:
        project_sources = await db.sources.find({
            "projectId": project_id,
            "level": {"$in": ["project", None]},
            "status": {"$in": ["active", None]}
        }, {"_id": 0, "id": 1}).to_list(100)
        active_source_ids.extend([s["id"] for s in project_sources])
    
    # Department and global sources only if mode is 'all'
    if source_mode == 'all':
        if user_department_ids:
            dept_sources = await db.sources.find({
                "departmentId": {"$in": user_department_ids},
                "level": "department",
                "status": "active"
            }, {"_id": 0, "id": 1}).to_list(100)
            active_source_ids.extend([s["id"] for s in dept_sources])
        
        global_sources = await db.sources.find({
            "$or": [
                {"projectId": "__global__"},
                {"level": "global", "status": "active"}
            ]
        }, {"_id": 0, "id": 1}).to_list(100)
        active_source_ids.extend([s["id"] for s in global_sources])
    
    if not active_source_ids:
        raise HTTPException(status_code=400, detail="No active sources available")
    
    sources = await db.sources.find(
        {"id": {"$in": active_source_ids}},
        {"_id": 0, "id": 1, "originalName": 1, "url": 1}
    ).to_list(100)
    
    source_names = [s.get("originalName") or s.get("url") or "Unknown" for s in sources]
    
    sample_content = []
    for source in sources[:5]:
        chunks = await db.source_chunks.find(
            {"sourceId": source["id"]},
            {"_id": 0}
        ).sort("chunkIndex", 1).to_list(3)
        
        source_name = source.get("originalName") or source.get("url") or "Unknown"
        for chunk in chunks:
            text = chunk.get("content") or chunk.get("text", "")
            sample_content.append(f"[{source_name}]: {text[:500]}")
    
    combined_content = "\n\n".join(sample_content)[:6000]
    
    try:
        import anthropic
        CLAUDE_API_KEY = os.environ.get('CLAUDE_API_KEY', '')
        claude_client = anthropic.Anthropic(api_key=CLAUDE_API_KEY)
        
        prompt = f"""Based on the following document excerpts, generate exactly 5 specific, useful questions that a user might want to ask about this content.

IMPORTANT: Detect the language of the content and generate questions in THE SAME LANGUAGE.
- If content is in Armenian, questions must be in Armenian
- If content is in Russian, questions must be in Russian
- If content is in English, questions must be in English

Available sources: {', '.join(source_names[:10])}

Content excerpts:
{combined_content}

Generate 5 practical questions that:
- Are specific to the actual content shown
- Would be useful for someone working with these documents
- Cover different aspects of the content
- Are in the SAME LANGUAGE as the content

Respond with ONLY a JSON array of 5 questions:
["Question 1?", "Question 2?", "Question 3?", "Question 4?", "Question 5?"]"""

        response = claude_client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=512,
            messages=[{"role": "user", "content": prompt}]
        )
        
        result_text = response.content[0].text.strip()
        if result_text.startswith("```"):
            result_text = result_text.split("```")[1]
            if result_text.startswith("json"):
                result_text = result_text[4:]
        result_text = result_text.strip()
        
        questions = json.loads(result_text)
        
        return SmartQuestionsResponse(
            questions=questions[:5],
            sourceNames=source_names[:5],
            generatedAt=datetime.now(timezone.utc).isoformat()
        )
        
    except Exception as e:
        logger.error(f"Smart questions error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to generate questions: {str(e)[:100]}")
