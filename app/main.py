import asyncio
import re
import os
import uuid
import datetime
import io
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.core.plagiarism import PlagiarismDetector
from app.core.rephrase import Rephraser
from app.services.file_service import FileIngestor
from app.services.s3_service import (
    get_s3_client,
    get_bucket_name,
    upload_fileobj,
    download_file,
    delete_file,
    generate_user_key,
)
from app.models import (UploadResponse, BatchStatus, SentenceResult,
                         PlagiarismBatch)

app = FastAPI(
    title="Plagiarism Checker Pro",
    version="1.0.0",
    description="Web-based plagiarism checker with AI-powered rephrasing"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

plagiarism_detector = PlagiarismDetector()
rephraser = Rephraser(use_openai=False)  # Use local T5 model
file_ingestor = FileIngestor()

S3_BUCKET = get_bucket_name()
s3_client = get_s3_client()


class BatchUploadRequest(BaseModel):
    
    documents: List[UploadFile]
    compare_against: Optional[str] = "public"
    user_id: Optional[str] = None


def uploaded_filename(original: str) -> str:
    
    safe = re.sub(r'[^\w\d_\.-]', '_', original)
    return f"plag_{safe}"


@app.get("/")
async def root():
    """Serve the frontend interface."""
    html_path = os.path.join("templates", "index.html")
    if os.path.exists(html_path):
        return FileResponse(html_path)
    return {
        "message": "Plagiarism Checker API is running",
        "docs": "/docs"
    }


@app.post("/api/upload", response_model=UploadResponse)
async def upload_files(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
    compare_against: str = "public",
    user_id: str = ""
):
    """Handle document upload and initiate processing."""
    if len(files) < 3 or len(files) > 5:
        raise HTTPException(
            status_code=400,
            detail="Please upload 3 to 5 documents in a single batch."
        )
    
    # Use provided user_id or generate one
    if not user_id:
        user_id = f"user_{uuid.uuid4().hex[:8]}"
    
    task_id = str(asyncio.get_event_loop().time())
    background_tasks.add_task(
        process_batch, files, compare_against, task_id, user_id
    )
    
    return UploadResponse(
        task_id=task_id,
        status="processing",
        message="Batch upload received. Processing started in background."
    )


async def process_batch(files: List[UploadFile], compare_against: str, task_id: str, user_id: str):
    """Process a batch of uploaded documents."""
    temp_files = []
    s3_keys = []
    try:
        
        for uploaded_file in files:
            tmp_path = f"/tmp/{uploaded_filename(uploaded_file.filename)}"
            content = await uploaded_file.read()
            with open(tmp_path, "wb") as f:
                f.write(content)
            temp_files.append(tmp_path)
                        
            s3_key = generate_user_key(user_id, uploaded_file.filename)
            upload_fileobj(
                open(tmp_path, "rb"),
                s3_key,
                content_type="application/octet-stream"
            )
            s3_keys.append(s3_key)
        
        
        documents = await file_ingestor.ingest_all(temp_files)
                
        all_sentences = []
        doc_sentence_map = {}  # maps global index -> (doc_idx, sent_idx)
        
        for doc_idx, doc in enumerate(documents):
            sentences = doc["sentences"]
            for sent_idx, sentence in enumerate(sentences):
                all_sentences.append(sentence)
                doc_sentence_map[len(all_sentences) - 1] = (doc_idx, sent_idx)
        
        
        results = await plagiarism_detector.detect_all(
            all_sentences, compare_against=compare_against
        )
                
        rephare_tasks = []
        for i, sentence_result in enumerate(results):
            original_sentence = sentence_result["original_text"]
            
            rephrased = await rephraser.rephrase(original_sentence)
            sentence_result["rephrased_text"] = rephrased
            sentence_result["acceptance_status"] = False
        
        
        batch = PlagiarismBatch(
            task_id=task_id,
            documents=len(documents),
            total_sentences=len(all_sentences),
            results=results
        )
                
        app.state.batch_results = batch.dict()
                
        results_key = generate_user_key(user_id, f"results_{task_id}.json")
        results_bytes = batch.dict().__str__().encode("utf-8")
        upload_fileobj(
            io.BytesIO(results_bytes),
            results_key,
            content_type="application/json"
        )
                
        app.state.export_key = results_key
        
        return batch
        
    finally:
        
        for tmp_path in temp_files:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)


@app.get("/api/batch/{task_id}", response_model=BatchStatus)
async def get_batch_status(task_id: str):
    """Retrieve batch processing status and results."""
    
    if hasattr(app.state, 'batch_results') and app.state.batch_results:
        results_data = app.state.batch_results
        
        from app.models import SentenceResult
        results = results_data.get("results", [])
        converted_results = []
        for r in results:
            converted_results.append(SentenceResult(
                sentence_id=r.get("sentence_id", 0),
                original_text=r.get("original_text", ""),
                is_plagiarized=r.get("is_plagiarized", False),
                similarity_score=r.get("similarity_score", 0.0),
                source_urls=r.get("source_urls", []),
                rephrased_text=r.get("rephrased_text"),
                acceptance_status=r.get("acceptance_status", False)
            ))
        
        return BatchStatus(
            task_id=task_id,
            status="completed",
            progress=100,
            message="Batch processing complete"
        )
    
    
    return BatchStatus(
        task_id=task_id,
        status="processing",
        progress=0,
        message="Batch queued for processing"
    )


@app.post("/api/accept-reject/{sentence_idx}")
async def accept_reject(
    sentence_idx: int,
    accepted: bool
):
    """Accept or reject a rephrased sentence."""
    if not hasattr(app.state, 'batch_results'):
        raise HTTPException(status_code=404, detail="No batch in progress")
    
    results = app.state.batch_results.get("results", [])
    if sentence_idx < len(results):
        results[sentence_idx]["acceptance_status"] = accepted
        app.state.batch_results["results"] = results
    
    return {"status": "updated", "sentence_idx": sentence_idx, "accepted": accepted}


@app.get("/api/export/{task_id}")
async def export_document(task_id: str):
    """Export the fully updated document as DOCX and store in S3."""
    
    try:
        from docx import Document
        from docx.shared import Pt, RGBColor, Inches
        from docx.enum.text import WD_PARAGRAPH_ALIGNMENT
        
        if not hasattr(app.state, 'batch_results'):
            raise HTTPException(status_code=404, detail="No batch results found")
        
        results = app.state.batch_results.get("results", [])
        doc = Document()
                
        style = doc.styles['Normal']
        font = style.font
        font.name = 'Calibri'
        font.size = Pt(11)
                
        for result in results:
            text = result.get("original_text", "")
            is_plagiarized = result.get("is_plagiarized", False)
            accepted = result.get("acceptance_status", False)
            
            if text.strip():
                paragraph = doc.add_paragraph()
                
                if is_plagiarized:
                    # Add plagiarized sentence with highlight
                    run = paragraph.add_run(text)
                    run.font.highlight_color = RGBColor(255, 255, 0)  # Yellow highlight
                    run.font.color = RGBColor(180, 0, 0)  # Red text
                    if not accepted:
                        run.bold = True
                else:
                    # Original non-plagiarized sentence
                    run = paragraph.add_run(text)
                    run.font.color = RGBColor(30, 41, 59)
                
                
                rephrased = result.get("rephrased_text")
                if rephrased and accepted:
                    paragraph = doc.add_paragraph()
                    run = paragraph.add_run(f"[Rephrased]: {rephrased}")
                    run.font.color = RGBColor(0, 128, 0)
                    run.italic = True
                
        export_path = f"/tmp/plagiarism_export_{task_id}.docx"
        doc.save(export_path)
                
        user_id = getattr(app.state, 'user_id', 'default')
        s3_key = generate_user_key(user_id, f"export_{task_id}.docx")
        with open(export_path, "rb") as f:
            upload_fileobj(f, s3_key, content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
        
        
        if os.path.exists(export_path):
            os.remove(export_path)
        
        
        s3_url = f"s3://{S3_BUCKET}/{s3_key}"
        return {
            "download_url": s3_url,
            "filename": f"plagiarism_checked_{task_id}.docx",
            "s3_key": s3_key
        }
        
    except ImportError:
        raise HTTPException(
            status_code=500, 
            detail="python-docx not available for export"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")


@app.get("/api/file/{s3_key:path}")
async def download_file_endpoint(s3_key: str):
    """Download a file from S3 by key."""
    try:
        file_data = download_file(s3_key)
        import io
        from fastapi.responses import StreamingResponse
        
        return StreamingResponse(
            io.BytesIO(file_data),
            media_type="application/octet-stream",
            headers={"Content-Disposition": f"attachment; filename={s3_key.split('/')[-1]}"}
        )
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"File not found: {str(e)}")


@app.post("/api/batch/{task_id}/accept-reject/{sentence_idx}")
async def accept_reject_sentence(
    task_id: str,
    sentence_idx: int,
    accepted: bool
):
    """Accept or reject a rephrased sentence with task ID."""
    if not hasattr(app.state, 'batch_results'):
        raise HTTPException(status_code=404, detail="No batch in progress")
    
    results = app.state.batch_results.get("results", [])
    if sentence_idx < len(results):
        results[sentence_idx]["acceptance_status"] = accepted
        app.state.batch_results["results"] = results
    
    return {"status": "updated", "sentence_idx": sentence_idx, "accepted": accepted}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)