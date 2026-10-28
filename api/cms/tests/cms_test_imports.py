# cms/tests/cms_test_imports.py
"""Central import hub — all test files do: from api.cms.tests.cms_test_imports import *"""
from decimal import Decimal
from datetime import datetime, timedelta, date
from typing import Dict, List, Any, Optional, Tuple
from unittest.mock import patch, MagicMock, call
import unittest

# Lazy model imports — all wrapped so a missing sub-model never crashes the hub
try:
    from api.cms.models_new.profile_surveys import (
        SurveyTemplate, SurveyCompletion, SurveyCategory, SurveyQuestion, SurveyResponse
    )
    Survey = SurveyTemplate   # alias used in older tests
except ImportError:
    SurveyTemplate = SurveyCompletion = SurveyCategory = SurveyQuestion = SurveyResponse = Survey = None

try:
    from api.cms.models_new.survey_rewards import SurveyReward, RewardTransaction, RewardPool
    Transaction = RewardTransaction  # alias used in older tests
except ImportError:
    SurveyReward = RewardTransaction = RewardPool = Transaction = None

try:
    from api.cms.models_new.seo import SEOConfig, Redirect301
    SEOModel = SEOConfig   # alias used in older tests
except ImportError:
    SEOConfig = Redirect301 = SEOModel = None

try:
    from api.cms.models_new.user_profile import UserProfile, UserSegment
except ImportError:
    UserProfile = UserSegment = None

try:
    from api.cms.models_new.task_management import TaskSchedule, TaskExecution, TaskQueue, TaskLock
except ImportError:
    TaskSchedule = TaskExecution = TaskQueue = TaskLock = None

try:
    from api.cms.models_new.leaderboard import LeaderboardPeriod, LeaderboardEntry, EarningStreak, StreakMilestone
except ImportError:
    LeaderboardPeriod = LeaderboardEntry = EarningStreak = StreakMilestone = None

try:
    from api.cms.models_new.workflow import WorkflowState, WorkflowTransition, WorkflowRule
except ImportError:
    WorkflowState = WorkflowTransition = WorkflowRule = None

try:
    from api.cms.models_new.quiz import QuizTemplate, QuizAttempt, QuizQuestion as QuizQ, QuizAnswer, QuizResult
except ImportError:
    QuizTemplate = QuizAttempt = QuizQ = QuizAnswer = QuizResult = None

try:
    from api.cms.models_new.withdrawal import PayoutMethod
except ImportError:
    PayoutMethod = None

try:
    from api.cms.models_new.cpalead import (
        VirtualCurrency, UserVirtualBalance, VirtualTransaction,
        ConversionLog, ClickLog, ContentLocker, OfferWallConfig
    )
except ImportError:
    VirtualCurrency = UserVirtualBalance = VirtualTransaction = None
    ConversionLog = ClickLog = ContentLocker = OfferWallConfig = None

try:
    from api.cms.models_new.referral import ReferralCode, ReferralRelationship, ReferralEarning
except ImportError:
    ReferralCode = ReferralRelationship = ReferralEarning = None

try:
    from api.cms.models_new.smartlink import SmartLink, SmartLinkClick
except ImportError:
    SmartLink = SmartLinkClick = None

try:
    from api.cms.models_new.ab_testing import ABTest, ABTestVariant, ABTestParticipant, ABTestResult
except ImportError:
    ABTest = ABTestVariant = ABTestParticipant = ABTestResult = None
