# api/support/choices.py
STATUS_OPEN='open'; STATUS_IN_PROGRESS='in_progress'; STATUS_WAITING_USER='waiting_user'
STATUS_RESOLVED='resolved'; STATUS_CLOSED='closed'; STATUS_SPAM='spam'
STATUS_CHOICES=[('open','Open'),('in_progress','In Progress'),('waiting_user','Waiting for User'),('resolved','Resolved'),('closed','Closed'),('spam','Spam')]
OPEN_STATUSES=[STATUS_OPEN,STATUS_IN_PROGRESS,STATUS_WAITING_USER]
CLOSED_STATUSES=[STATUS_RESOLVED,STATUS_CLOSED,STATUS_SPAM]
PRIORITY_LOW='low'; PRIORITY_MEDIUM='medium'; PRIORITY_HIGH='high'; PRIORITY_URGENT='urgent'
PRIORITY_CHOICES=[('low','Low'),('medium','Medium'),('high','High'),('urgent','Urgent')]
PRIORITY_ORDER={'low':1,'medium':2,'high':3,'urgent':4}
CATEGORY_PRIORITY_MAP={'fraud':'urgent','payment':'high','withdrawal':'high','kyc':'medium','coins':'medium','account':'medium','technical':'medium','referral':'low','offer':'low','other':'low'}
CATEGORY_CHOICES=[('payment','Payment Issue'),('coins','Coins Not Added'),('account','Account Problem'),('technical','Technical Issue'),('other','Other'),('withdrawal','Withdrawal Issue'),('fraud','Fraud/Security'),('kyc','KYC Verification'),('referral','Referral Issue'),('offer','Offer Issue')]
CHANNEL_CHOICES=[('web','Web Portal'),('email','Email'),('telegram','Telegram'),('whatsapp','WhatsApp'),('facebook','Facebook'),('chat','Live Chat'),('api','API')]
SLA_FIRST_RESPONSE_HOURS={'urgent':1,'high':4,'medium':8,'low':24}
SLA_RESOLUTION_HOURS={'urgent':4,'high':24,'medium':48,'low':72}
ROLE_CHOICES=[('agent','Agent'),('senior_agent','Senior Agent'),('supervisor','Supervisor'),('manager','Manager'),('account_manager','Account Manager')]
SUPERVISOR_ROLES=['supervisor','manager','account_manager']
DISPUTE_STATUS_CHOICES=[('pending','Pending'),('investigating','Investigating'),('approved','Approved'),('rejected','Rejected'),('needs_proof','Needs Proof')]