"""
Excel/CSV Analyzer with Gemini AI
Analyzes tabular data using Gemini 2.5 Flash
"""
from fastapi import APIRouter, HTTPException, UploadFile, File, Depends, Form
from pydantic import BaseModel
from typing import Optional, List
import os
import uuid
import tempfile
import aiofiles
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()

router = APIRouter(prefix="/analyzer", tags=["analyzer"])

# Store active analysis sessions
analysis_sessions = {}

class AnalyzeRequest(BaseModel):
    session_id: str
    question: str

class AnalysisResponse(BaseModel):
    answer: str
    session_id: str

def setup_analyzer_routes(db, get_current_user):
    """Setup analyzer routes with dependencies"""
    
    EMERGENT_KEY = os.environ.get("EMERGENT_LLM_KEY")
    
    @router.post("/upload")
    async def upload_for_analysis(
        file: UploadFile = File(...),
        current_user: dict = Depends(get_current_user)
    ):
        """Upload Excel/CSV file for analysis"""
        
        # Validate file type
        allowed_types = [
            "text/csv",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "application/vnd.ms-excel"
        ]
        
        if file.content_type not in allowed_types:
            raise HTTPException(
                status_code=400, 
                detail="Only Excel (.xlsx) and CSV files are supported"
            )
        
        content = await file.read()
        
        # Limit file size (10MB)
        if len(content) > 10 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="File too large (max 10MB)")
        
        # Create session
        session_id = str(uuid.uuid4())
        
        # Save file temporarily
        ext = ".csv" if "csv" in file.content_type else ".xlsx"
        temp_path = f"/tmp/analyzer_{session_id}{ext}"
        
        async with aiofiles.open(temp_path, 'wb') as f:
            await f.write(content)
        
        # Parse file to get preview
        preview_data = []
        total_rows = 0
        columns = []
        
        try:
            if ext == ".csv":
                import csv
                from io import StringIO
                text = content.decode('utf-8', errors='ignore')
                reader = csv.reader(StringIO(text))
                rows = list(reader)
                if rows:
                    columns = rows[0]
                    total_rows = len(rows) - 1
                    preview_data = rows[:11]  # Header + 10 rows
            else:
                from openpyxl import load_workbook
                from io import BytesIO
                wb = load_workbook(BytesIO(content), data_only=True)
                sheet = wb.active
                rows = list(sheet.iter_rows(values_only=True))
                if rows:
                    columns = [str(c) if c else f"Col_{i}" for i, c in enumerate(rows[0])]
                    total_rows = len(rows) - 1
                    for row in rows[:11]:
                        preview_data.append([str(c) if c is not None else "" for c in row])
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Failed to parse file: {str(e)}")
        
        # Store session info
        mime_type = "text/csv" if ext == ".csv" else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        analysis_sessions[session_id] = {
            "file_path": temp_path,
            "file_name": file.filename,
            "mime_type": mime_type,
            "user_id": current_user["id"],
            "columns": columns,
            "total_rows": total_rows,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "messages": []
        }
        
        return {
            "session_id": session_id,
            "file_name": file.filename,
            "columns": columns,
            "total_rows": total_rows,
            "preview": preview_data
        }
    
    @router.post("/ask")
    async def ask_about_data(
        request: AnalyzeRequest,
        current_user: dict = Depends(get_current_user)
    ):
        """Ask a question about the uploaded data"""
        
        session = analysis_sessions.get(request.session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found. Please upload a file first.")
        
        if session["user_id"] != current_user["id"]:
            raise HTTPException(status_code=403, detail="Access denied")
        
        if not EMERGENT_KEY:
            raise HTTPException(status_code=500, detail="Gemini API key not configured")
        
        try:
            from emergentintegrations.llm.chat import LlmChat, UserMessage, FileContentWithMimeType
            
            # Create chat with Gemini
            chat = LlmChat(
                api_key=EMERGENT_KEY,
                session_id=f"analyzer_{request.session_id}",
                system_message=f"""You are a data analyst assistant. You are analyzing a file called "{session['file_name']}".
The file has {session['total_rows']} rows and columns: {', '.join(session['columns'])}.

When answering questions:
1. Be specific and reference actual data from the file
2. If asked to find something, provide the exact row numbers and values
3. For calculations, show your work
4. Format numbers nicely (use thousands separator for large numbers)
5. If data is not found, say so clearly
6. Respond in the same language as the question

Always provide accurate answers based on the actual file content."""
            ).with_model("gemini", "gemini-2.5-flash")
            
            # Attach file
            file_attachment = FileContentWithMimeType(
                file_path=session["file_path"],
                mime_type=session["mime_type"]
            )
            
            # Build message with context from previous messages
            context = ""
            if session["messages"]:
                context = "Previous conversation:\n"
                for msg in session["messages"][-4:]:  # Last 4 messages for context
                    context += f"Q: {msg['question']}\nA: {msg['answer']}\n\n"
            
            full_question = context + f"Question: {request.question}"
            
            user_message = UserMessage(
                text=full_question,
                file_contents=[file_attachment]
            )
            
            # Get response
            response = await chat.send_message(user_message)
            
            # Store in session history
            session["messages"].append({
                "question": request.question,
                "answer": response,
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
            
            return {
                "answer": response,
                "session_id": request.session_id
            }
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")
    
    @router.get("/session/{session_id}")
    async def get_session(
        session_id: str,
        current_user: dict = Depends(get_current_user)
    ):
        """Get session info and history"""
        session = analysis_sessions.get(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        if session["user_id"] != current_user["id"]:
            raise HTTPException(status_code=403, detail="Access denied")
        
        return {
            "session_id": session_id,
            "file_name": session["file_name"],
            "columns": session["columns"],
            "total_rows": session["total_rows"],
            "messages": session["messages"],
            "created_at": session["created_at"]
        }
    
    @router.delete("/session/{session_id}")
    async def delete_session(
        session_id: str,
        current_user: dict = Depends(get_current_user)
    ):
        """Delete analysis session"""
        session = analysis_sessions.get(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        if session["user_id"] != current_user["id"]:
            raise HTTPException(status_code=403, detail="Access denied")
        
        # Delete temp file
        try:
            import os
            if os.path.exists(session["file_path"]):
                os.remove(session["file_path"])
        except:
            pass
        
        del analysis_sessions[session_id]
        
        return {"message": "Session deleted"}
    
    return router
