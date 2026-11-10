"""Reply drafts from department policy and similar tickets, with an optional LLM."""

import json
import logging
import re
import urllib.error
import urllib.request

from backend.app.config import settings

logger = logging.getLogger(__name__)

POLICIES = {
    "billing": "Duplicate or disputed charges are checked against the ledger first. A reversal goes back to the original payment method only after the extra capture is confirmed.",
    "technical": "Crashes and sync failures are reproduced from the error code before they are escalated. We don't promise a ship date from the ticket alone.",
    "account": "Sign-in changes happen only after the inbox on the account is confirmed. That includes password resets, 2FA resets, and SSO changes.",
    "shipping": "Tracking exceptions are confirmed with the carrier before a replacement ships. A delivered scan without a photo can be disputed.",
    "returns": "Refunds go back to the original payment method after the warehouse scan. An exchange stays open until the replacement has tracking.",
    "product": "Plan questions are answered from the current limits. The subscription is not changed unless you ask for that in the reply.",
    "trust": "Suspicious access is contained by signing out other sessions first. Deletion and privacy requests are confirmed back to the address on the account.",
}

SIGN_OFF = {
    "billing": "Fieldnote Billing",
    "technical": "Fieldnote Support",
    "account": "Fieldnote Support",
    "shipping": "Fieldnote Logistics",
    "returns": "Fieldnote Returns",
    "product": "Fieldnote Support",
    "trust": "Fieldnote Trust & Safety",
}

ORDER_RE = re.compile(r"\bFN-\d{4,6}\b")
AMOUNT_RE = re.compile(r"\$\d+(?:\.\d{2})?")
ERROR_RE = re.compile(r"\bFN-(?:[A-Z]+-)?\d+\b")
TRACKING_RE = re.compile(r"\b(?:1Z\d+|9400\d+|DHL\d+|FX\d+)\b")
LAST4_RE = re.compile(r"\bending\s+(\d{4})\b", re.IGNORECASE)
PLAN_RE = re.compile(r"\b(Free|Studio|Team|Archive)\b")
PRODUCT_RE = re.compile(r"\b(Fieldnote App|Fieldnote Sync|Fieldnote Pen|Fieldnote Book|Capture Clip)\b")

SYSTEM = (
    "You draft support replies for a human agent at Fieldnote to review before sending. "
    "Write plain sentences, under 170 words. Do not invent refunds, tracking scans, password resets, "
    "or account changes that are not supported by the ticket, the policy, or a similar case. "
    "If you mention a similar case, describe it as precedent the agent still needs to confirm, "
    "not as something already done for this customer. Sign off as Fieldnote Support."
)


def _first(pattern, text: str, group: int = 0) -> str:
    match = pattern.search(text)
    return match.group(group) if match else ""


def _extract(subject: str, body: str) -> dict:
    text = f"{subject}\n{body}"
    return {
        "order_id": _first(ORDER_RE, text),
        "amount": _first(AMOUNT_RE, text),
        "error_code": _first(ERROR_RE, text),
        "tracking": _first(TRACKING_RE, text),
        "last4": _first(LAST4_RE, text, 1),
        "plan": _first(PLAN_RE, text),
        "product": _first(PRODUCT_RE, text),
    }


def _first_name(customer_name: str) -> str:
    parts = (customer_name or "").split()
    return parts[0] if parts else "there"


def _ack(slug: str, slots: dict) -> str:
    product = slots["product"] or "your Fieldnote account"
    order_id = slots["order_id"]
    amount = slots["amount"]
    if slug == "billing" and amount and order_id:
        return f"Thanks for contacting billing about the {amount} charge on order {order_id}."
    if slug == "billing" and order_id:
        return f"Thanks for contacting billing about order {order_id}."
    if slug == "billing":
        return "Thanks for contacting billing. I have the charge details from your note."
    if slug == "technical":
        code = f" ({slots['error_code']})" if slots["error_code"] else ""
        return f"Thanks for the report on {product}{code}."
    if slug == "account":
        return f"Thanks for writing in about access to {product}."
    if slug == "shipping" and order_id:
        return f"Thanks for the update on order {order_id}."
    if slug == "shipping":
        return f"Thanks for the shipping note about {product}."
    if slug == "returns" and order_id:
        return f"Thanks for the return note on order {order_id}."
    if slug == "returns":
        return f"Thanks for writing in about the {product} return."
    if slug == "product":
        plan = f" on the {slots['plan']} plan" if slots["plan"] else ""
        return f"Happy to answer the question about {product}{plan}."
    if slug == "trust":
        return f"Thanks for flagging this on {product}. I'm treating it as an account-security note."
    return "Thanks for writing in."


def _action(slug: str, slots: dict) -> str:
    product = slots["product"] or "Fieldnote"
    if slug == "billing":
        if slots["amount"] and slots["order_id"]:
            card = f" on the card ending {slots['last4']}" if slots["last4"] else ""
            return f"I'm matching {slots['amount']} on {slots['order_id']}{card} against the ledger before anything is reversed."
        return "I'm pulling the latest invoices and the card on the account before changing anything."
    if slug == "technical":
        if slots["error_code"]:
            return f"I'm looking up {slots['error_code']} on {product} and I'll try to reproduce what you described before escalating it."
        return f"I'm checking the sync and crash notes for {product} before escalating."
    if slug == "account":
        return f"I'll confirm this inbox is the one on the {product} account before any reset or email change."
    if slug == "shipping":
        if slots["tracking"]:
            return f"I'm checking tracking {slots['tracking']} with the carrier before a replacement is created."
        if slots["order_id"]:
            return f"I'm checking whether order {slots['order_id']} has left the warehouse yet."
        return "I'm checking the shipment status before promising a replacement."
    if slug == "returns":
        if slots["amount"] and slots["order_id"]:
            return f"I'm checking the warehouse scan for order {slots['order_id']} before releasing the {slots['amount']} refund."
        if slots["order_id"]:
            return f"I'm checking the RMA on order {slots['order_id']} and whether a label is still open."
        return "I'm checking the return scan before a refund or exchange moves forward."
    if slug == "product":
        plan = slots["plan"] or "current"
        return f"I'll answer from the {plan} plan limits for {product} and leave the subscription as it is unless you ask to change it."
    if slug == "trust":
        return f"The first step is to sign other sessions out of {product}. I won't delete data or change the card from this draft alone."
    return "I'm reviewing the note and will follow the queue policy."


def _precedent(similar: list[dict]) -> str:
    for item in similar:
        resolution = (item.get("resolution") or "").strip()
        if not resolution:
            continue
        return (
            f"On a similar ticket (#{item['id']}, {item['subject']}), the outcome was: {resolution} "
            "I'll confirm that fit on this account before treating it as done."
        )
    return ""


def compose_playbook(ticket: dict, similar: list[dict]) -> str:
    slug = ticket["department_slug"]
    slots = _extract(ticket.get("subject") or "", ticket.get("body") or "")
    paragraphs = [
        f"Hi {_first_name(ticket.get('customer_name') or '')},",
        _ack(slug, slots),
        _action(slug, slots),
        POLICIES.get(slug, ""),
    ]
    precedent = _precedent(similar)
    if precedent:
        paragraphs.append(precedent)
    paragraphs.append("Reply here if any of that doesn't match what you're seeing.")
    paragraphs.append(SIGN_OFF.get(slug, "Fieldnote Support"))
    return "\n\n".join(paragraph for paragraph in paragraphs if paragraph)


def _prompt(ticket: dict, similar: list[dict]) -> str:
    lines = [
        f"Department: {ticket.get('department_name')}",
        f"Priority: {ticket.get('priority')}",
        f"Sentiment: {ticket.get('sentiment')}",
        f"Customer: {ticket.get('customer_name')}",
        f"Subject: {ticket.get('subject')}",
        "Ticket:",
        ticket.get("body") or "",
        f"Policy: {POLICIES.get(ticket.get('department_slug'), '')}",
        "Similar resolved tickets:",
    ]
    if not similar:
        lines.append("None.")
    for item in similar[:3]:
        lines.append(f"- #{item['id']} {item['subject']} (similarity {item['score']:.2f})")
        if item.get("resolution"):
            lines.append(f"  Outcome: {item['resolution']}")
    lines.append("Draft the reply.")
    return "\n".join(lines)


def _call_llm(ticket: dict, similar: list[dict]) -> str:
    payload = {
        "model": settings.openai_model,
        "temperature": 0.3,
        "max_tokens": 400,
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": _prompt(ticket, similar)},
        ],
    }
    request = urllib.request.Request(
        f"{settings.openai_base_url}/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {settings.openai_api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        data = json.loads(response.read().decode("utf-8"))
    return (data["choices"][0]["message"]["content"] or "").strip()


def draft(ticket: dict, similar: list[dict]) -> tuple[str, str]:
    playbook = compose_playbook(ticket, similar)
    if not settings.openai_api_key:
        return playbook, "playbook"
    try:
        text = _call_llm(ticket, similar)
    except (urllib.error.URLError, TimeoutError, KeyError, json.JSONDecodeError, IndexError) as exc:
        logger.warning("LLM draft failed (%s). Using the playbook draft.", exc.__class__.__name__)
        return playbook, "playbook"
    if not text:
        return playbook, "playbook"
    return text, "llm"
