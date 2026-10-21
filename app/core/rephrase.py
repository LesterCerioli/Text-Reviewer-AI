import asyncio
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class Rephraser:
        
    def __init__(self, use_openai: bool = False, model_name: str = "t5-small"):
        self.use_openai = use_openai
        self.model_name = model_name
        self.openai_client = None
        self.local_model = None
                
        if use_openai:
            try:
                import openai
                self.openai_client = openai.OpenAI()
            except ImportError:
                logger.warning("OpenAI not available, will use local model")
        
        
        if not use_openai:
            try:
                from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
                self.local_model_name = model_name or "t5-small"
                tokenizer = AutoTokenizer.from_pretrained(self.local_model_name)
                model = AutoModelForSeq2SeqLM.from_pretrained(self.local_model_name)
                self.local_model = {"model": model, "tokenizer": tokenizer}
                logger.info(f"Loaded local model: {self.local_model_name}")
            except Exception as e:
                logger.error(f"Failed to load local model: {e}")
    
    async def rephrase(self, text: str) -> str:
        
        if not text or not text.strip():
            return text
        
        
        if self.use_openai and self.openai_client:
            try:
                result = await self._rephrase_with_openai(text)
                if result and len(result.strip()) > 0:
                    return result
            except Exception as e:
                logger.warning(f"OpenAI rephrasing failed: {e}")
        
        
        if self.local_model:
            try:
                result = await self._rephrase_with_local(text)
                if result and len(result.strip()) > 0:
                    return result
            except Exception as e:
                logger.warning(f"Local model rephrasing failed: {e}")
        
        
        return text
    
    async def _rephrase_with_openai(self, text: str) -> Optional[str]:
        
        import openai
        
        response = self.openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a helpful assistant that rephrases text while preserving the original meaning and intent. Return only the rephrased text, no explanations."},
                {"role": "user", "content": f"Rephrase the following sentence for a plagiarism checker. Preserve the exact meaning and intent but use different wording:\n\n{text}"}
            ],
            temperature=0.7,
            max_tokens=100
        )
        
        rephrased = response.choices[0].message.content
        return rephrased.strip() if rephrased else None
    
    async def _rephrase_with_local(self, text: str) -> Optional[str]:
        
        if not self.local_model:
            return None
        
        model_info = self.local_model
        tokenizer = model_info["tokenizer"]
        model = model_info["model"]
        
        
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
        
        return rephrased if rephrased.strip() else None