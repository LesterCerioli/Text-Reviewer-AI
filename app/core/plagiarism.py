import asyncio
import re
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime


try:
    from sentence_transformers import SentenceTransformer, util
    MODEL = SentenceTransformer('all-MiniLM-L6-v2')
except ImportError:
    MODEL = None


try:
    from playwright.async_api import async_playwright
except ImportError:
    async_playwright = None


class PlagiarismDetector:
    
    def __init__(self, similarity_threshold: float = 0.75, google_search: bool = True):
        self.similarity_threshold = similarity_threshold
        self.model = MODEL
        self.google_search = google_search
        self.headless_browser = None
        self.corpus_embeddings = None
        self.source_sentences = []
        self.document_map = {}
    
    async def detect_all(
        self,
        all_sentences: List[Any],
        compare_against: str = "public"
    ) -> List[Dict[str, Any]]:
        
        if not self.model:
            raise RuntimeError("Sentence transformer model not available")
        
        sentences_text = [s.text for s in all_sentences]
        embeddings = self.model.encode(sentences_text, convert_to_tensor=False)
        
        self.corpus_embeddings = embeddings
        self.source_sentences = sentences_text
        self.document_map = self._build_document_map(all_sentences)
        
        results = []
        
        if self.google_search:
            results = await self._google_plagiarism_check(all_sentences)
        else:
            results = await self._semantic_plagiarism_check(all_sentences, embeddings)
        
        return results
    
    def _build_document_map(self, sentences: List[Any]) -> Dict[int, Tuple[int, int]]:
        
        mapping = {}
        current_doc = -1
        doc_count = 0
        
        for i, sent in enumerate(sentences):
            if sent.doc_index != current_doc:
                current_doc = sent.doc_index
                doc_count = 1
            else:
                doc_count += 1
            mapping[i] = (sent.doc_index, sent.sentence_index)
        
        return mapping
    
    async def _google_plagiarism_check(
        self,
        all_sentences: List[Any]
    ) -> List[Dict[str, Any]]:
        
        results = []
        
        if not async_playwright:
            print("Playwright not available, falling back to semantic check")
            return await self._semantic_plagiarism_check(all_sentences, self.corpus_embeddings)
        
        self.headless_browser = await async_playwright.chromium.launch(headless=True)
        
        try:
            for i, sentence_obj in enumerate(all_sentences):
                result = await self._google_check_single(i, sentence_obj)
                results.append(result)
        finally:
            if self.headless_browser:
                await self.headless_browser.close()
                self.headless_browser = None
        
        return results
    
    async def _google_check_single(
        self,
        sentence_idx: int,
        sentence_obj: Any
    ) -> Dict[str, Any]:
        
        sentence_text = sentence_obj.text
        cleaned_text = re.sub(r'[^\w\s]', '', sentence_text)[:200]
        
        is_plagiarized = False
        source_urls = []
        rephrased_preview = None
        acceptance_status = False
        
        try:
            page = await self.headless_browser.new_page()
            await page.set_default_timeout(15000)
            
            search_query = re.escape(cleaned_text)
            await page.goto(f"https://www.google.com/search?q={search_query.replace(' ', '+')}")
            await page.wait_for_load_state('networkidle')
            
            search_results = await page.locator('.g, .tF2Cxc').all()
            
            for result in search_results[:10]:
                title_elem = result.locator('h3').first
                title = await title_elem.text_content() if title_elem else ""
                
                link_elem = result.locator('a').first
                link = await link_elem.get_attribute('href') if link_elem else ""
                
                if link and link.startswith('/'):
                    link = f"https://www.google.com{link}"
                
                if link and 'http' in link:
                    source_urls.append(link)
                
                snippet = result.locator('.VwiC3b').first
                if snippet:
                    snippet_text = await snippet.text_content()
                    if cleaned_text.lower() in snippet_text.lower():
                        is_plagiarized = True
                        break
            
            await page.close()
            
            if is_plagiarized:
                rephrased_preview = await self._generate_rephrased_preview(sentence_text)
                
        except Exception as e:
            print(f"Google search error for sentence {sentence_idx}: {e}")
            is_plagiarized = False
        
        return {
            "sentence_id": sentence_idx,
            "original_text": sentence_text,
            "is_plagiarized": is_plagiarized,
            "similarity_score": 1.0 if is_plagiarized else 0.0,
            "source_urls": source_urls[:5],
            "rephrased_text": rephrased_preview,
            "acceptance_status": acceptance_status,
            "best_match_text": None,
            "best_match_doc": None
        }
    
    async def _generate_rephrased_preview(self, text: str) -> str:
        
        if not text or not text.strip():
            return text
        
        try:
            from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
            
            model_name = "t5-small"
            tokenizer = AutoTokenizer.from_pretrained(model_name)
            model = AutoModelForSeq2SeqLM.from_pretrained(model_name)
            
            input_text = f"paraphrase: {text}"
            inputs = tokenizer.encode(input_text, return_tensors="pt", max_length=512, truncation=True)
            
            outputs = model.generate(
                inputs,
                max_length=512,
                num_beams=4,
                early_stopping=True,
                temperature=0.7
            )
            
            rephrased = tokenizer.decode(outputs[0], skip_special_tokens=True)
            
            if rephrased.lower().startswith("paraphrase:"):
                rephrased = rephrased[len("paraphrase:"):].strip()
            
            return rephrased if rephrased.strip() else text
            
        except Exception:
            return text
    
    async def _semantic_plagiarism_check(
        self,
        all_sentences: List[Any],
        embeddings: Any
    ) -> List[Dict[str, Any]]:
        
        results = []
        
        for i, sentence_obj in enumerate(all_sentences):
            result = await self._detect_single(i, sentence_obj, embeddings[i] if embeddings is not None else None)
            results.append(result)
        
        return results
    
    async def _detect_single(
        self,
        sentence_idx: int,
        sentence_obj: Any,
        query_embedding: Optional[Any]
    ) -> Dict[str, Any]:
        
        sentence_text = sentence_obj.text
        
        if self.corpus_embeddings is None and query_embedding is None:
            if self.model:
                query_emb = self.model.encode(sentence_text)
            else:
                query_emb = None
        else:
            query_emb = query_embedding
        
        similarities = []
        
        if self.corpus_embeddings is not None and len(self.corpus_embeddings) > 1 and query_emb is not None:
            from sentence_transformers import util
            cos_sims = util.cos_sim(query_emb, self.corpus_embeddings)[0]
            
            indexed_sims = list(enumerate(cos_sims.numpy()))
            indexed_sims.sort(key=lambda x: x[1], reverse=True)
            
            top_similarities = []
            for j, sim in indexed_sims:
                if j == sentence_idx:
                    continue
                if sim > self.similarity_threshold:
                    top_similarities.append({
                        "similarity": float(sim),
                        "target_idx": j,
                        "target_text": self.source_sentences[j],
                        "target_doc": self.document_map[j][0]
                    })
                
                if len(top_similarities) >= 5:
                    break
        
        is_plagiarized = len(top_similarities) > 0
                
        best_match = top_similarities[0] if top_similarities else None
        
        return {
            "sentence_id": sentence_idx,
            "original_text": sentence_text,
            "is_plagiarized": is_plagiarized,
            "similarity_score": best_match["similarity"] if best_match else 0.0,
            "source_urls": self._get_source_urls(best_match) if best_match else [],
            "rephrased_text": None,
            "acceptance_status": False,
            "best_match_text": best_match["target_text"] if best_match else None,
            "best_match_doc": best_match["target_doc"] if best_match else None
        }
    
    def _get_source_urls(self, match: Optional[Dict]) -> List[str]:
        
        if not match:
            return []
        
        return [f"https://example-source.com/paper/{match.get('target_idx', 0)}"]