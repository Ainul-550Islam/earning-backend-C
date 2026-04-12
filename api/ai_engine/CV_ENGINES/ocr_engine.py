"""
api/ai_engine/CV_ENGINES/ocr_engine.py
========================================
OCR Engine — image থেকে text extract করো।
KYC document reading, receipt scanning, ID card reading।
pytesseract + Google Vision API + AWS Textract support।
"""

import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class OCREngine:
    """
    Production OCR engine।
    Multiple backend support: pytesseract, Google Vision, AWS Textract।
    """

    def __init__(self, backend: str = "pytesseract"):
        self.backend = backend

    def extract_text(self, image_path: str = None, image_url: str = None,
                     language: str = "eng+ben") -> dict:
        """Image থেকে text extract করো।"""
        if not image_path and not image_url:
            return {"text": "", "confidence": 0.0, "error": "No image source provided"}

        if self.backend == "pytesseract":
            return self._tesseract_ocr(image_path, image_url, language)
        elif self.backend == "google_vision":
            return self._google_vision_ocr(image_path, image_url)
        elif self.backend == "aws_textract":
            return self._aws_textract_ocr(image_path, image_url)
        else:
            return self._tesseract_ocr(image_path, image_url, language)

    def _tesseract_ocr(self, image_path: str = None, image_url: str = None,
                        language: str = "eng+ben") -> dict:
        """pytesseract OCR।"""
        try:
            import pytesseract
            from PIL import Image
            import requests
            from io import BytesIO

            # Load image
            if image_url:
                response = requests.get(image_url, timeout=10)
                response.raise_for_status()
                img = Image.open(BytesIO(response.content))
            else:
                img = Image.open(image_path)

            # Preprocess for better OCR
            img = self._preprocess(img)

            # OCR extraction
            text = pytesseract.image_to_string(img, lang=language, config="--psm 6")
            data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)

            confidences = [int(c) for c in data["conf"] if str(c).isdigit() and int(c) > 0]
            avg_conf    = sum(confidences) / len(confidences) / 100 if confidences else 0.0

            # Word-level extraction
            words = [
                {"text": w, "confidence": int(c) / 100}
                for w, c in zip(data["text"], data["conf"])
                if str(c).isdigit() and int(c) > 50 and w.strip()
            ]

            return {
                "text":        text.strip(),
                "confidence":  round(avg_conf, 4),
                "word_count":  len(text.split()),
                "words":       words[:50],
                "backend":     "pytesseract",
                "language":    language,
            }

        except ImportError:
            logger.warning("pytesseract not installed. pip install pytesseract Pillow")
            return {"text": "", "confidence": 0.0, "method": "unavailable",
                    "error": "pytesseract not installed"}
        except Exception as e:
            logger.error(f"Tesseract OCR error: {e}")
            return {"text": "", "confidence": 0.0, "error": str(e)}

    def _preprocess(self, img):
        """Image preprocessing for better OCR accuracy।"""
        try:
            from PIL import ImageEnhance, ImageFilter
            # Convert to grayscale
            img = img.convert("L")
            # Enhance contrast
            enhancer = ImageEnhance.Contrast(img)
            img = enhancer.enhance(2.0)
            # Sharpen
            img = img.filter(ImageFilter.SHARPEN)
            return img
        except Exception:
            return img

    def _google_vision_ocr(self, image_path: str = None, image_url: str = None) -> dict:
        """Google Cloud Vision OCR।"""
        try:
            from google.cloud import vision
            client = vision.ImageAnnotatorClient()

            if image_url:
                image = vision.Image(source=vision.ImageSource(image_uri=image_url))
            else:
                with open(image_path, "rb") as f:
                    content = f.read()
                image = vision.Image(content=content)

            response = client.document_text_detection(image=image)
            text     = response.full_text_annotation.text
            conf     = response.full_text_annotation.pages[0].confidence if response.full_text_annotation.pages else 0.0

            return {
                "text":       text.strip(),
                "confidence": round(float(conf), 4),
                "backend":    "google_vision",
            }
        except ImportError:
            logger.warning("google-cloud-vision not installed")
            return self._tesseract_ocr(image_path, image_url)
        except Exception as e:
            logger.error(f"Google Vision OCR error: {e}")
            return {"text": "", "confidence": 0.0, "error": str(e)}

    def _aws_textract_ocr(self, image_path: str = None, image_url: str = None) -> dict:
        """AWS Textract OCR।"""
        try:
            import boto3
            client = boto3.client("textract")

            if image_path:
                with open(image_path, "rb") as f:
                    content = f.read()
                response = client.detect_document_text(Document={"Bytes": content})
            else:
                return self._tesseract_ocr(image_url=image_url)

            text = " ".join(
                b["Text"] for b in response["Blocks"]
                if b["BlockType"] == "LINE"
            )
            confidences = [b["Confidence"] for b in response["Blocks"] if "Confidence" in b]
            avg_conf    = sum(confidences) / len(confidences) / 100 if confidences else 0.0

            return {
                "text":       text.strip(),
                "confidence": round(avg_conf, 4),
                "backend":    "aws_textract",
            }
        except ImportError:
            return self._tesseract_ocr(image_path, image_url)
        except Exception as e:
            logger.error(f"AWS Textract error: {e}")
            return {"text": "", "confidence": 0.0, "error": str(e)}

    def extract_nid_data(self, image_path: str = None, image_url: str = None) -> dict:
        """Bangladesh NID থেকে structured data extract করো।"""
        import re
        ocr_result = self.extract_text(image_path, image_url, language="eng+ben")
        text       = ocr_result.get("text", "")

        data = {"raw_text": text}

        # NID number patterns
        nid_patterns = [r"\b\d{10}\b", r"\b\d{13}\b", r"\b\d{17}\b"]
        for pattern in nid_patterns:
            match = re.search(pattern, text)
            if match:
                data["nid_number"] = match.group()
                break

        # Date of birth
        dob_match = re.search(r"\b(\d{2}[/-]\d{2}[/-]\d{4}|\d{4}[/-]\d{2}[/-]\d{2})\b", text)
        if dob_match:
            data["date_of_birth"] = dob_match.group()

        # Name extraction (lines before/after known keywords)
        name_match = re.search(r"(?:Name|নাম)[:\s]+([A-Za-z\s]+|[\u0980-\u09FF\s]+)", text)
        if name_match:
            data["name"] = name_match.group(1).strip()

        data["extraction_confidence"] = ocr_result.get("confidence", 0.0)
        data["valid_nid_found"]       = "nid_number" in data

        return data

    def batch_extract(self, images: List[Dict]) -> List[Dict]:
        """Multiple images OCR করো।"""
        results = []
        for img in images:
            result = self.extract_text(
                image_path=img.get("path"),
                image_url=img.get("url"),
            )
            results.append({"source": img.get("id", ""), **result})
        return results

    def validate_document_quality(self, image_path: str = None,
                                   image_url: str = None) -> dict:
        """Document image quality check করো।"""
        from .image_quality_checker import ImageQualityChecker
        quality = ImageQualityChecker().check(image_path, image_url)

        is_suitable_for_ocr = (
            not quality.get("is_blurry", True) and
            quality.get("quality_score", 0) >= 0.50
        )

        return {
            **quality,
            "suitable_for_ocr": is_suitable_for_ocr,
            "recommendation":   "Good quality — proceed with OCR" if is_suitable_for_ocr
                                else "Poor quality — ask user to retake photo",
        }
