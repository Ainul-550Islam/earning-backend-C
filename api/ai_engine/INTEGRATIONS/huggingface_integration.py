"""
api/ai_engine/INTEGRATIONS/huggingface_integration.py
======================================================
HuggingFace Transformers Integration।
Pre-trained models: BERT, GPT2, T5, RoBERTa।
NLP tasks: classification, NER, summarization, generation।
"""
import logging
from typing import Any, Dict, List, Optional
logger = logging.getLogger(__name__)

class HuggingFaceIntegration:
    """HuggingFace Transformers integration।"""

    def __init__(self, device: str = "auto"):
        self.device = self._get_device(device)
        self._pipelines: Dict[str, Any] = {}

    def _get_device(self, device: str) -> str:
        if device == "auto":
            try:
                import torch
                return "cuda" if torch.cuda.is_available() else "cpu"
            except ImportError:
                return "cpu"
        return device

    def get_pipeline(self, task: str, model: str = None) -> Any:
        cache_key = f"{task}:{model or 'default'}"
        if cache_key in self._pipelines:
            return self._pipelines[cache_key]
        try:
            from transformers import pipeline
            pipe = pipeline(task, model=model, device=0 if self.device == "cuda" else -1)
            self._pipelines[cache_key] = pipe
            logger.info(f"Pipeline loaded: {task} [{model or 'default'}]")
            return pipe
        except Exception as e:
            logger.error(f"Pipeline load error [{task}]: {e}")
            return None

    def classify_text(self, text: str, model: str = None) -> dict:
        pipe = self.get_pipeline("text-classification", model)
        if not pipe: return {"label": "unknown", "score": 0.0}
        result = pipe(text[:512])[0]
        return {"label": result["label"], "score": round(float(result["score"]), 4)}

    def sentiment_analysis(self, text: str) -> dict:
        return self.classify_text(
            text,
            model="nlptown/bert-base-multilingual-uncased-sentiment"
        )

    def named_entity_recognition(self, text: str) -> List[Dict]:
        pipe = self.get_pipeline("ner", "dbmdz/bert-large-cased-finetuned-conll03-english")
        if not pipe: return []
        results = pipe(text[:512])
        return [{"entity": r["entity"], "word": r["word"], "score": round(float(r["score"]), 4)}
                for r in results]

    def summarize(self, text: str, max_length: int = 150, min_length: int = 40) -> str:
        pipe = self.get_pipeline("summarization", "facebook/bart-large-cnn")
        if not pipe: return text[:200]
        result = pipe(text[:1024], max_length=max_length, min_length=min_length, do_sample=False)
        return result[0].get("summary_text", "")

    def generate_text(self, prompt: str, max_length: int = 200,
                       model: str = "gpt2") -> str:
        pipe = self.get_pipeline("text-generation", model)
        if not pipe: return ""
        result = pipe(prompt, max_length=max_length, num_return_sequences=1, truncation=True)
        return result[0].get("generated_text", "")

    def get_embeddings(self, texts: List[str],
                        model: str = "sentence-transformers/all-MiniLM-L6-v2") -> List[List[float]]:
        try:
            from sentence_transformers import SentenceTransformer
            st_model  = SentenceTransformer(model)
            embeddings = st_model.encode(texts)
            return [emb.tolist() for emb in embeddings]
        except ImportError:
            logger.warning("sentence-transformers not installed")
            return [[0.0] * 384] * len(texts)

    def question_answering(self, question: str, context: str) -> dict:
        pipe = self.get_pipeline("question-answering")
        if not pipe: return {"answer": "", "score": 0.0}
        result = pipe(question=question, context=context[:2000])
        return {"answer": result["answer"], "score": round(float(result["score"]), 4),
                "start": result["start"], "end": result["end"]}

    def translation(self, text: str, src_lang: str = "en",
                     tgt_lang: str = "bn") -> str:
        model_name = f"Helsinki-NLP/opus-mt-{src_lang}-{tgt_lang}"
        pipe = self.get_pipeline("translation", model_name)
        if not pipe: return text
        try:
            result = pipe(text[:512])
            return result[0].get("translation_text", text)
        except Exception as e:
            logger.error(f"Translation error: {e}")
            return text
