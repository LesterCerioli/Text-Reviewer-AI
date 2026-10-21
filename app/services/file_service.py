import io
import re
from typing import List, Dict, Any, Optional
from pathlib import Path

# Try to import document libraries
try:
    from pypdf import PdfReader
except ImportError:
    PdfReader = None

try:
    from docx import Document as DocxDocument
except ImportError:
    DocxDocument = None


class ExtractedSentence:
        
    def __init__(self, text: str, doc_index: int, sentence_index: int):
        self.text = text.strip()
        self.doc_index = doc_index
        self.sentence_index = sentence_index
    
    def __repr__(self):
        return f"Sentence(doc_{self.doc_index})[{self.sentence_index}]: {self.text[:50]}..."


class FileIngestor:
        
    def __init__(self):
        self.nlp = None
        try:
            import spacy
            self.nlp = spacy.load("en_core_web_sm")
        except Exception:
            # Spacy model not available, will use basic sentence splitting
            pass
    
    def extract_text_from_pdf(self, file_path: str) -> str:
        
        if PdfReader is None:
            raise ImportError("pypdf not installed")
        
        reader = PdfReader(file_path)
        text_parts = []
        
        for page in reader.pages:
            try:
                text = page.extract_text()
                if text:
                    text_parts.append(text)
            except Exception:
                continue
        
        return "\n".join(text_parts)
    
    def extract_text_from_docx(self, file_path: str) -> str:
        
        if DocxDocument is None:
            raise ImportError("python-docx not installed")
        
        doc = DocxDocument(file_path)
        text_parts = []
        
        for paragraph in doc.paragraphs:
            if paragraph.text.strip():
                text_parts.append(paragraph.text.strip())
        
        return "\n".join(text_parts)
    
    def split_into_sentences(self, text: str, doc_index: int) -> List[ExtractedSentence]:
                
        if self.nlp is not None:
            doc = self.nlp(text)
            sentences = [
                ExtractedSentence(sent.text, doc_index, i)
                for i, sent in enumerate(doc.sents)
                if sent.text.strip()]
        else:
            
            sentences = self._simple_split(text, doc_index)
        
        return sentences
    
    def _simple_split(self, text: str, doc_index: int) -> List[ExtractedSentence]:
                
        text = re.sub(r'\n+', ' ', text)
                
        parts = re.split(r'(?<=[.!?])\s+', text)
        
        sentences = []
        sent_idx = 0
        for part in parts:
            part = part.strip()
            if part and len(part) > 10:  # Skip very short "sentences"
                sentences.append(ExtractedSentence(part, doc_index, sent_idx))
                sent_idx += 1
        
        return sentences
    
    async def ingest_file(self, file_path: str, doc_index: int) -> Dict[str, Any]:
                
        ext = Path(file_path).suffix.lower()
        
        if ext == ".pdf":
            text = self.extract_text_from_pdf(file_path)
        elif ext in [".docx", ".doc"]:
            text = self.extract_text_from_docx(file_path)
        else:
            raise ValueError(f"Unsupported file format: {ext}")
                
        sentences = self.split_into_sentences(text, doc_index)
        
        return {
            "filename": Path(file_path).name,
            "word_count": len(text.split()),
            "sentences": sentences,
            "raw_text": text,
            "doc_index": doc_index,
            "sentence_count": len(sentences)
        }
    
    async def ingest_all(self, file_paths: List[str]) -> List[Dict[str, Any]]:
        
        tasks = []
        for i, fpath in enumerate(file_paths):
            tasks.append(self.ingest_file(fpath, i))
        
        results = await asyncio.gather(*tasks, return_exceptions=False)
        return results