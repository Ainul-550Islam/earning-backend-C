# api/wallet/notification_templates.py
"""
Extended notification templates — HTML email templates, SMS templates.
Used by WalletNotifier for rich formatted notifications.
"""

# ── HTML Email Templates ──────────────────────────────────

WALLET_CREDITED_HTML = """
<!DOCTYPE html>
<html>
<body style="font-family:Arial,sans-serif;background:#f5f5f5;padding:20px">
  <div style="max-width:600px;margin:auto;background:#fff;border-radius:10px;padding:30px">
    <h2 style="color:#2ecc71">💰 +{amount} BDT Received</h2>
    <p>Dear {username},</p>
    <p>Your wallet has been credited with <strong>{amount} BDT</strong>.</p>
    <table style="width:100%;border-collapse:collapse;margin:20px 0">
      <tr style="background:#f8f9fa">
        <td style="padding:10px"><strong>Amount</strong></td>
        <td style="padding:10px">+{amount} BDT</td>
      </tr>
      <tr>
        <td style="padding:10px"><strong>Balance After</strong></td>
        <td style="padding:10px">{balance_after} BDT</td>
      </tr>
      <tr style="background:#f8f9fa">
        <td style="padding:10px"><strong>Transaction Type</strong></td>
        <td style="padding:10px">{txn_type}</td>
      </tr>
      <tr>
        <td style="padding:10px"><strong>Description</strong></td>
        <td style="padding:10px">{description}</td>
      </tr>
    </table>
    <p style="color:#888;font-size:12px">Thank you for using our platform.</p>
  </div>
</body>
</html>
"""

WITHDRAWAL_COMPLETED_HTML = """
<!DOCTYPE html>
<html>
<body style="font-family:Arial,sans-serif;background:#f5f5f5;padding:20px">
  <div style="max-width:600px;margin:auto;background:#fff;border-radius:10px;padding:30px">
    <h2 style="color:#3498db">✅ Withdrawal Successful</h2>
    <p>Dear {username},</p>
    <p>Your withdrawal has been processed successfully.</p>
    <table style="width:100%;border-collapse:collapse;margin:20px 0">
      <tr style="background:#f8f9fa">
        <td style="padding:10px"><strong>Amount</strong></td>
        <td style="padding:10px">{amount} BDT</td>
      </tr>
      <tr>
        <td style="padding:10px"><strong>Gateway</strong></td>
        <td style="padding:10px">{gateway}</td>
      </tr>
      <tr style="background:#f8f9fa">
        <td style="padding:10px"><strong>Reference</strong></td>
        <td style="padding:10px">{gateway_ref}</td>
      </tr>
    </table>
  </div>
</body>
</html>
"""

KYC_APPROVED_HTML = """
<!DOCTYPE html>
<html>
<body style="font-family:Arial,sans-serif;background:#f5f5f5;padding:20px">
  <div style="max-width:600px;margin:auto;background:#fff;border-radius:10px;padding:30px">
    <h2 style="color:#2ecc71">✅ KYC Level {level} Approved!</h2>
    <p>Dear {username},</p>
    <p>Your KYC verification has been approved!</p>
    <ul>
      <li>KYC Level: <strong>{level}</strong></li>
      <li>New Daily Withdrawal Limit: <strong>{new_daily_limit} BDT</strong></li>
    </ul>
    <p>You can now withdraw up to {new_daily_limit} BDT per day.</p>
  </div>
</body>
</html>
"""

# SMS Templates (max 160 chars)
SMS_TEMPLATES = {
    "wallet_credited":     "Wallet +{amount}BDT. Bal:{balance_after}BDT",
    "withdrawal_done":     "Withdrawal {amount}BDT sent. Ref:{gateway_ref}",
    "withdrawal_failed":   "Withdrawal failed. {amount}BDT returned to wallet.",
    "kyc_approved":        "KYC L{level} approved! Daily limit:{new_daily_limit}BDT",
    "streak_bonus":        "Streak {days} days! +{bonus}BDT bonus added.",
    "level_upgrade":       "Level {new_level} unlocked! Payout:{new_payout_freq}",
    "fraud_locked":        "Account locked for review. Contact support urgently.",
    "bonus_expiring":      "{amount}BDT bonus expiring. Withdraw now!",
}
