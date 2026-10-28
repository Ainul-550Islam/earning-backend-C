# api/cms/choices.py
"""All choice constants for CMS models — single source of truth."""

# ── Content Status ────────────────────────────────────────────────
class ContentStatus:
    DRAFT     = 'draft'
    REVIEW    = 'review'
    APPROVED  = 'approved'
    PUBLISHED = 'published'
    ARCHIVED  = 'archived'
    SCHEDULED = 'scheduled'

    CHOICES = [
        (DRAFT,     'Draft'),
        (REVIEW,    'In Review'),
        (APPROVED,  'Approved'),
        (PUBLISHED, 'Published'),
        (ARCHIVED,  'Archived'),
        (SCHEDULED, 'Scheduled'),
    ]

# ── Visibility ────────────────────────────────────────────────────
class Visibility:
    PUBLIC   = 'public'
    MEMBERS  = 'members'
    PREMIUM  = 'premium'
    ADMIN    = 'admin'

    CHOICES = [
        (PUBLIC,  'Public'),
        (MEMBERS, 'Members Only'),
        (PREMIUM, 'Premium Members'),
        (ADMIN,   'Admin Only'),
    ]

# ── CPAlead / Offer Types ─────────────────────────────────────────
class OfferType:
    CPA      = 'cpa'
    CPI      = 'cpi'
    CPC      = 'cpc'
    SURVEY   = 'survey'
    QUIZ     = 'quiz'
    VIDEO    = 'video'
    EMAIL    = 'email_submit'
    ZIP      = 'zip_submit'
    MOBILE   = 'mobile_content'

    CHOICES = [
        (CPA,    'CPA Offer'),
        (CPI,    'CPI — App Install'),
        (CPC,    'CPC — Pay Per Click'),
        (SURVEY, 'Survey'),
        (QUIZ,   'Quiz / Personality'),
        (VIDEO,  'Video Offer'),
        (EMAIL,  'Email Submit'),
        (ZIP,    'ZIP Submit'),
        (MOBILE, 'Mobile Content'),
    ]

# ── Payment Methods ───────────────────────────────────────────────
class PaymentMethod:
    PAYPAL   = 'paypal'
    PAYONEER = 'payoneer'
    USDT     = 'usdt'
    BITCOIN  = 'bitcoin'
    WIRE     = 'wire'
    ACH      = 'ach'
    BANK     = 'bank'

    CHOICES = [
        (PAYPAL,   'PayPal'),
        (PAYONEER, 'Payoneer'),
        (USDT,     'USDT (TRC-20)'),
        (BITCOIN,  'Bitcoin'),
        (WIRE,     'Wire Transfer'),
        (ACH,      'ACH Direct'),
        (BANK,     'Bank Transfer'),
    ]

    MIN_USD = {
        PAYPAL:   1.00,
        PAYONEER: 1.00,
        USDT:     25.00,   # CPAlead Jul 2025
        BITCOIN:  10.00,
        WIRE:     100.00,
        ACH:      10.00,
        BANK:     50.00,
    }

# ── Withdrawal Status ─────────────────────────────────────────────
class WithdrawalStatus:
    PENDING    = 'pending'
    APPROVED   = 'approved'
    PROCESSING = 'processing'
    PAID       = 'paid'
    REJECTED   = 'rejected'
    CANCELLED  = 'cancelled'

    CHOICES = [
        (PENDING,    'Pending'),
        (APPROVED,   'Approved'),
        (PROCESSING, 'Processing'),
        (PAID,       'Paid'),
        (REJECTED,   'Rejected'),
        (CANCELLED,  'Cancelled'),
    ]

# ── Device Types ──────────────────────────────────────────────────
class DeviceType:
    DESKTOP = 'desktop'
    MOBILE  = 'mobile'
    TABLET  = 'tablet'

    CHOICES = [
        (DESKTOP, 'Desktop'),
        (MOBILE,  'Mobile'),
        (TABLET,  'Tablet'),
    ]

# ── Notification Types ────────────────────────────────────────────
class NotificationType:
    REWARD    = 'reward'
    REFERRAL  = 'referral'
    STREAK    = 'streak'
    WITHDRAWAL= 'withdrawal'
    SYSTEM    = 'system'
    OFFER     = 'offer'
    WORKFLOW  = 'workflow'
    LEVEL_UP  = 'level_up'

    CHOICES = [
        (REWARD,    'Reward Earned'),
        (REFERRAL,  'Referral Bonus'),
        (STREAK,    'Streak Milestone'),
        (WITHDRAWAL,'Withdrawal Update'),
        (SYSTEM,    'System'),
        (OFFER,     'Offer Completed'),
        (WORKFLOW,  'Content Workflow'),
        (LEVEL_UP,  'Level Up'),
    ]

# ── Block Types ───────────────────────────────────────────────────
class BlockType:
    RICH_TEXT = 'rich_text'
    IMAGE     = 'image'
    VIDEO     = 'video'
    CTA       = 'cta'
    QUOTE     = 'quote'
    HTML      = 'html'
    CODE      = 'code'
    DIVIDER   = 'divider'
    GALLERY   = 'gallery'
    TABLE     = 'table'
    ACCORDION = 'accordion'
    OFFERWALL = 'offerwall'
    LOCKER    = 'locker'

    CHOICES = [
        (RICH_TEXT, 'Rich Text'),
        (IMAGE,     'Image'),
        (VIDEO,     'Video'),
        (CTA,       'Call to Action'),
        (QUOTE,     'Blockquote'),
        (HTML,      'Raw HTML'),
        (CODE,      'Code Block'),
        (DIVIDER,   'Divider'),
        (GALLERY,   'Image Gallery'),
        (TABLE,     'Table'),
        (ACCORDION, 'Accordion'),
        (OFFERWALL, 'Offerwall Block'),
        (LOCKER,    'Content Locker Block'),
    ]

# ── User Levels ───────────────────────────────────────────────────
class UserLevel:
    BEGINNER  = 1
    BRONZE    = 2
    SILVER    = 3
    GOLD      = 4
    PLATINUM  = 5
    DIAMOND   = 6
    ELITE     = 7

    CHOICES = [
        (BEGINNER, 'Beginner'),
        (BRONZE,   'Bronze'),
        (SILVER,   'Silver'),
        (GOLD,     'Gold'),
        (PLATINUM, 'Platinum'),
        (DIAMOND,  'Diamond'),
        (ELITE,    'Elite'),
    ]

    USD_THRESHOLDS = {
        ELITE:    1000,
        DIAMOND:  500,
        PLATINUM: 200,
        GOLD:     100,
        SILVER:   50,
        BRONZE:   10,
        BEGINNER: 0,
    }

# ── Locker Types ──────────────────────────────────────────────────
class LockerType:
    CONTENT  = 'content'
    LINK     = 'link'
    FILE     = 'file'
    PAGE     = 'page'
    BLOG     = 'blog'
    VIDEO    = 'video'
    DOWNLOAD = 'download'

    CHOICES = [
        (CONTENT,  'Content Block'),
        (LINK,     'Link Locker'),
        (FILE,     'File Locker'),
        (PAGE,     'CMS Page'),
        (BLOG,     'Blog Post'),
        (VIDEO,    'Video'),
        (DOWNLOAD, 'Download'),
    ]

# ── KYC Status ────────────────────────────────────────────────────
class KYCStatus:
    NOT_STARTED = 'not_started'
    SUBMITTED   = 'submitted'
    APPROVED    = 'approved'
    REJECTED    = 'rejected'

    CHOICES = [
        (NOT_STARTED, 'Not Started'),
        (SUBMITTED,   'Submitted'),
        (APPROVED,    'Approved'),
        (REJECTED,    'Rejected'),
    ]

# ── Rotation Modes (SmartLink) ────────────────────────────────────
class RotationMode:
    BEST_PAYOUT   = 'best_payout'
    GEO_OPTIMIZED = 'geo_optimized'
    DEVICE_MATCH  = 'device_match'
    ROUND_ROBIN   = 'round_robin'
    WEIGHTED      = 'weight'

    CHOICES = [
        (BEST_PAYOUT,   'Best Payout First'),
        (GEO_OPTIMIZED, 'GEO Optimized'),
        (DEVICE_MATCH,  'Device Match'),
        (ROUND_ROBIN,   'Round Robin'),
        (WEIGHTED,      'Weighted Random'),
    ]

# ── Survey & Profile Choices ─────────────────────────────────────
class SurveyStatus:
    DRAFT      = 'draft'
    ACTIVE      = 'active'
    PAUSED      = 'paused'
    COMPLETED   = 'completed'
    ARCHIVED    = 'archived'

    CHOICES = [
        (DRAFT,     'Draft'),
        (ACTIVE,     'Active'),
        (PAUSED,     'Paused'),
        (COMPLETED,  'Completed'),
        (ARCHIVED,   'Archived'),
    ]

class SurveyCompletionStatus:
    PENDING    = 'pending'
    IN_PROGRESS = 'in_progress'
    COMPLETED   = 'completed'
    APPROVED    = 'approved'
    REJECTED    = 'rejected'
    EXPIRED     = 'expired'

    CHOICES = [
        (PENDING,     'Pending'),
        (IN_PROGRESS,  'In Progress'),
        (COMPLETED,    'Completed'),
        (APPROVED,     'Approved'),
        (REJECTED,     'Rejected'),
        (EXPIRED,      'Expired'),
    ]

class QuestionType:
    TEXT          = 'text'
    MULTIPLE_CHOICE = 'multiple_choice'
    MULTIPLE_SELECT = 'multiple_select'
    NUMBER         = 'number'
    EMAIL          = 'email'
    URL            = 'url'
    DATE           = 'date'
    RATING         = 'rating'
    FILE_UPLOAD    = 'file_upload'

    CHOICES = [
        (TEXT,           'Short Text'),
        (MULTIPLE_CHOICE, 'Multiple Choice'),
        (MULTIPLE_SELECT, 'Multiple Select'),
        (NUMBER,          'Number'),
        (EMAIL,           'Email'),
        (URL,             'URL'),
        (DATE,            'Date'),
        (RATING,          'Rating'),
        (FILE_UPLOAD,     'File Upload'),
    ]

class Gender:
    MALE      = 'male'
    FEMALE    = 'female'
    OTHER     = 'other'
    PREFER_NOT_SAY = 'prefer_not_say'

    CHOICES = [
        (MALE,            'Male'),
        (FEMALE,          'Female'),
        (OTHER,           'Other'),
        (PREFER_NOT_SAY,  'Prefer not to say'),
    ]

class EducationLevel:
    HIGH_SCHOOL      = 'high_school'
    SOME_COLLEGE     = 'some_college'
    ASSOCIATE        = 'associate'
    BACHELOR         = 'bachelor'
    MASTER           = 'master'
    PHD              = 'phd'
    PROFESSIONAL      = 'professional'
    OTHER            = 'other'

    CHOICES = [
        (HIGH_SCHOOL,     'High School'),
        (SOME_COLLEGE,    'Some College'),
        (ASSOCIATE,       'Associate Degree'),
        (BACHELOR,        'Bachelor\'s Degree'),
        (MASTER,          'Master\'s Degree'),
        (PHD,             'PhD'),
        (PROFESSIONAL,     'Professional Degree'),
        (OTHER,           'Other'),
    ]

class IncomeLevel:
    LOW        = 'low'
    MEDIUM     = 'medium'
    HIGH       = 'high'
    VERY_HIGH  = 'very_high'
    PREFER_NOT_SAY = 'prefer_not_say'

    CHOICES = [
        (LOW,             'Low'),
        (MEDIUM,          'Medium'),
        (HIGH,            'High'),
        (VERY_HIGH,        'Very High'),
        (PREFER_NOT_SAY,   'Prefer not to say'),
    ]

class SurveyFrequency:
    DAILY     = 'daily'
    WEEKLY    = 'weekly'
    MONTHLY   = 'monthly'
    OCCASIONAL = 'occasional'
    NEVER      = 'never'

    CHOICES = [
        (DAILY,      'Daily'),
        (WEEKLY,     'Weekly'),
        (MONTHLY,    'Monthly'),
        (OCCASIONAL, 'Occasional'),
        (NEVER,      'Never'),
    ]

# ── Reward Management Choices ───────────────────────────────────
class RewardType:
    FIXED       = 'fixed'
    TIERED      = 'tiered'
    PERFORMANCE = 'performance'
    BONUS       = 'bonus'

    CHOICES = [
        (FIXED,       'Fixed Amount'),
        (TIERED,      'Tiered (with bonus)'),
        (PERFORMANCE, 'Performance-based'),
        (BONUS,       'Bonus Only'),
    ]

class RewardStatus:
    ACTIVE    = 'active'
    INACTIVE  = 'inactive'
    EXPIRED   = 'expired'
    SUSPENDED = 'suspended'

    CHOICES = [
        (ACTIVE,     'Active'),
        (INACTIVE,   'Inactive'),
        (EXPIRED,    'Expired'),
        (SUSPENDED,  'Suspended'),
    ]

class TransactionType:
    EARNED     = 'earned'
    BONUS      = 'bonus'
    PENALTY    = 'penalty'
    REFUND     = 'refund'
    ADJUSTMENT = 'adjustment'

    CHOICES = [
        (EARNED,     'Earned'),
        (BONUS,      'Bonus'),
        (PENALTY,    'Penalty'),
        (REFUND,     'Refund'),
        (ADJUSTMENT, 'Adjustment'),
    ]

class TransactionStatus:
    PENDING   = 'pending'
    APPROVED  = 'approved'
    PAID      = 'paid'
    REJECTED  = 'rejected'
    CANCELLED = 'cancelled'

    CHOICES = [
        (PENDING,   'Pending'),
        (APPROVED,  'Approved'),
        (PAID,      'Paid'),
        (REJECTED,  'Rejected'),
        (CANCELLED, 'Cancelled'),
    ]

class PoolStatus:
    ACTIVE    = 'active'
    INACTIVE  = 'inactive'
    DRAINED   = 'drained'
    SUSPENDED = 'suspended'

    CHOICES = [
        (ACTIVE,     'Active'),
        (INACTIVE,   'Inactive'),
        (DRAINED,    'Drained'),
        (SUSPENDED,  'Suspended'),
    ]

# ── Task Management Choices ─────────────────────────────────────
class TaskFrequency:
    ONCE      = 'once'
    MINUTELY  = 'minutely'
    HOURLY    = 'hourly'
    DAILY     = 'daily'
    WEEKLY    = 'weekly'
    MONTHLY   = 'monthly'
    CUSTOM    = 'custom'

    CHOICES = [
        (ONCE,     'Once'),
        (MINUTELY, 'Minutely'),
        (HOURLY,   'Hourly'),
        (DAILY,    'Daily'),
        (WEEKLY,   'Weekly'),
        (MONTHLY,  'Monthly'),
        (CUSTOM,   'Custom (Cron)'),
    ]

class TaskStatus:
    PENDING   = 'pending'
    RUNNING   = 'running'
    SUCCESS   = 'success'
    FAILURE   = 'failure'
    TIMEOUT   = 'timeout'
    CANCELLED = 'cancelled'
    RETRY     = 'retry'

    CHOICES = [
        (PENDING,   'Pending'),
        (RUNNING,   'Running'),
        (SUCCESS,   'Success'),
        (FAILURE,   'Failure'),
        (TIMEOUT,   'Timeout'),
        (CANCELLED, 'Cancelled'),
        (RETRY,     'Retry'),
    ]

class TaskPriority:
    LOW      = 'low'
    NORMAL   = 'normal'
    HIGH     = 'high'
    CRITICAL = 'critical'

    CHOICES = [
        (LOW,      'Low'),
        (NORMAL,   'Normal'),
        (HIGH,     'High'),
        (CRITICAL, 'Critical'),
    ]

class QueueStatus:
    QUEUED     = 'queued'
    PROCESSING = 'processing'
    COMPLETED  = 'completed'
    FAILED     = 'failed'
    CANCELLED  = 'cancelled'

    CHOICES = [
        (QUEUED,     'Queued'),
        (PROCESSING, 'Processing'),
        (COMPLETED,  'Completed'),
        (FAILED,     'Failed'),
        (CANCELLED,  'Cancelled'),
    ]
