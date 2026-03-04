import random
from datetime import datetime, timedelta


def get_application_status(customer_id: str) -> dict:
    """Mock function: returns a card application status for a customer."""
    statuses = [
        {"status": "approved", "message": "Your Atome Card application has been approved! Your card will be delivered within 5-7 business days."},
        {"status": "pending", "message": "Your application is currently under review. We will notify you within 2-3 business days."},
        {"status": "rejected", "message": "Unfortunately, your application was not approved at this time. You may reapply after 90 days."},
        {"status": "more_info_required", "message": "We need additional documents to process your application. Please check your email for details."},
    ]
    # Deterministic based on customer_id for consistent demo behavior
    index = sum(ord(c) for c in customer_id) % len(statuses)
    result = statuses[index].copy()
    result["customer_id"] = customer_id
    result["checked_at"] = datetime.utcnow().isoformat()
    return result


def get_transaction_status(transaction_id: str) -> dict:
    """Mock function: returns a card transaction status for a given transaction ID."""
    statuses = [
        {
            "status": "failed",
            "reason": "insufficient_funds",
            "message": "Transaction failed due to insufficient credit limit. Please make a payment to free up your credit.",
            "amount": "PHP 2,500.00",
        },
        {
            "status": "failed",
            "reason": "card_declined",
            "message": "Transaction was declined by the merchant. Please contact us if this was unexpected.",
            "amount": "PHP 1,200.00",
        },
        {
            "status": "failed",
            "reason": "card_blocked",
            "message": "Your card has been temporarily blocked due to suspicious activity. Please contact support.",
            "amount": "PHP 4,800.00",
        },
        {
            "status": "processing",
            "reason": None,
            "message": "Transaction is still being processed. Please wait 24 hours before reporting an issue.",
            "amount": "PHP 750.00",
        },
    ]
    index = sum(ord(c) for c in transaction_id) % len(statuses)
    result = statuses[index].copy()
    result["transaction_id"] = transaction_id
    result["checked_at"] = datetime.utcnow().isoformat()
    return result
