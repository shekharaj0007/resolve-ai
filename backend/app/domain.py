"""Shared labels for routing, training, and the console."""

DEPARTMENTS = [
    {
        "slug": "billing",
        "name": "Billing",
        "queue_name": "Billing Queue",
        "description": "Invoices, subscriptions, payment methods, and disputed charges.",
    },
    {
        "slug": "technical",
        "name": "Technical Support",
        "queue_name": "Technical Support L2",
        "description": "Crashes, sync failures, search, and device pairing.",
    },
    {
        "slug": "account",
        "name": "Account Access",
        "queue_name": "Identity & Access",
        "description": "Login, password reset, two-factor authentication, SSO, and invites.",
    },
    {
        "slug": "shipping",
        "name": "Orders & Shipping",
        "queue_name": "Logistics Desk",
        "description": "Tracking, carriers, address changes, and damaged deliveries.",
    },
    {
        "slug": "returns",
        "name": "Returns & Refunds",
        "queue_name": "Returns Desk",
        "description": "RMAs, return labels, exchanges, and refund timing.",
    },
    {
        "slug": "product",
        "name": "Product Inquiry",
        "queue_name": "Product Specialists",
        "description": "Plan limits, compatibility, and how-to questions.",
    },
    {
        "slug": "trust",
        "name": "Trust & Safety",
        "queue_name": "Trust & Safety",
        "description": "Suspicious access, privacy requests, and phishing reports.",
    },
]

PRIORITIES = ("low", "medium", "high", "urgent")
SENTIMENTS = ("negative", "neutral", "positive")
STATUSES = ("open", "triaged", "in_progress", "pending_customer", "resolved")
AGENTS = ("Alex Rivera", "Priya Shah", "Jordan Lee", "Sam Okonkwo")
