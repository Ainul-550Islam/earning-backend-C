# Backward compat shim — real file is profile_surveys.py
from .profile_surveys import (
    SurveyCategory, SurveyTemplate, SurveyCompletion,
    SurveyQuestion, SurveyResponse, Survey,
)
__all__ = ['SurveyCategory','SurveyTemplate','SurveyCompletion',
           'SurveyQuestion','SurveyResponse','Survey']
