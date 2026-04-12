"""
api/ai_engine/CV_ENGINES/id_card_reader.py
===========================================
ID Card Reader — NID, Passport, Driver License।
KYC verification, user identity validation।
Bangladesh NID + international passport।
"""
import re, logging
from typing import Dict, Optional
logger = logging.getLogger(__name__)

class IDCardReader:
    """ID card OCR and validation engine।"""

    ID_PATTERNS = {
        "nid_bd":     r"\b\d{10}\b|\b\d{13}\b|\b\d{17}\b",
        "passport_bd": r"\b[A-Z]{1,2}\d{7}\b",
        "birth_cert": r"\b\d{17}\b",
        "driving":    r"\b[A-Z]{2}\d{7}\b",
    }

    def read(self, image_path: str = None, image_base64: str = None) -> dict:
        """ID card থেকে information extract করো।"""
        from .ocr_engine import OCREngine
        ocr    = OCREngine()
        result = ocr.extract_text(image_path=image_path, image_base64=image_base64)
        text   = result.get("text", "")
        if not text:
            return {"success": False, "error": "No text extracted"}

        return self._parse_id_fields(text, result)

    def _parse_id_fields(self, text: str, ocr_result: dict) -> dict:
        """Extracted text থেকে ID fields parse করো।"""
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        info  = {"raw_text": text, "success": True, "confidence": ocr_result.get("confidence", 0)}

        # Name detection
        name_pattern = r"(?:Name|নাম|নাম:|Name:)\s*:?\s*([A-Za-z\u0980-\u09FF\s]{3,50})"
        name_match   = re.search(name_pattern, text, re.IGNORECASE)
        if name_match:
            info["name"] = name_match.group(1).strip()

        # Date of birth
        dob_pattern  = r"(?:DOB|Date of Birth|জন্ম|জন্ম তারিখ)\s*:?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})"
        dob_match    = re.search(dob_pattern, text, re.IGNORECASE)
        if dob_match:
            info["date_of_birth"] = dob_match.group(1).strip()

        # ID numbers
        for id_type, pattern in self.ID_PATTERNS.items():
            match = re.search(pattern, text)
            if match:
                info["id_number"] = match.group()
                info["id_type"]   = id_type
                break

        # Gender
        if re.search(r"\b(male|পুরুষ)\b", text, re.IGNORECASE):
            info["gender"] = "male"
        elif re.search(r"\b(female|মহিলা|নারী)\b", text, re.IGNORECASE):
            info["gender"] = "female"

        return info

    def validate_nid(self, nid_number: str) -> dict:
        """Bangladesh NID validate করো।"""
        clean = re.sub(r"\D", "", nid_number)
        valid_lengths = [10, 13, 17]
        is_valid = len(clean) in valid_lengths
        return {
            "nid_number":   clean,
            "is_valid":     is_valid,
            "length":       len(clean),
            "format":       f"{len(clean)}-digit NID" if is_valid else "Invalid",
        }

    def verify_selfie_match(self, id_image: str, selfie_image: str) -> dict:
        """ID card photo ও selfie match করো।"""
        from .face_detector import FaceDetector
        detector = FaceDetector()
        id_faces = detector.detect(image_path=id_image)
        se_faces = detector.detect(image_path=selfie_image)
        if not id_faces.get("faces") or not se_faces.get("faces"):
            return {"match": False, "reason": "No face detected"}
        # Placeholder — production এ FaceNet use করো
        return {"match": True, "similarity": 0.85, "method": "placeholder",
                "note": "Production: implement FaceNet/DeepFace"}

    def extract_kyc_data(self, front_image: str, back_image: str = None) -> dict:
        """Complete KYC data extract করো।"""
        front_data = self.read(image_path=front_image)
        result     = {"front": front_data, "kyc_complete": False}
        if back_image:
            result["back"] = self.read(image_path=back_image)
        required = ["name", "id_number", "date_of_birth"]
        result["kyc_complete"] = all(front_data.get(f) for f in required)
        result["missing_fields"] = [f for f in required if not front_data.get(f)]
        return result
