"""Synthetic Fieldnote support mail.

The corpus is generated so ResolveAI can train and run without private customer
data. Scenarios repeat across the train and holdout split; the Models page
says so next to the scores.
"""

import re

import numpy as np

from backend.app.domain import DEPARTMENTS, PRIORITIES, SENTIMENTS

N_TICKETS = 5600

PEOPLE = [
    ("Maya", "Chen"),
    ("Luis", "Ortega"),
    ("Priya", "Shah"),
    ("Jonah", "Adler"),
    ("Amina", "Diallo"),
    ("Chris", "Nguyen"),
    ("Helena", "Costa"),
    ("Omar", "Farouk"),
    ("Greta", "Lind"),
    ("Sam", "Okonkwo"),
    ("Noah", "Brooks"),
    ("Leila", "Haddad"),
    ("Evan", "Park"),
    ("Rosa", "Martinez"),
    ("Theo", "Berg"),
    ("Aisha", "Rahman"),
    ("Miles", "Carter"),
    ("Ines", "Duval"),
    ("Haruto", "Sato"),
    ("Claire", "Murphy"),
    ("Andre", "Silva"),
    ("Fatima", "Nasser"),
    ("Jonah", "Ellis"),
    ("Mei", "Laurent"),
    ("Oscar", "Ibrahim"),
    ("Nina", "Petrov"),
    ("Hugo", "Almeida"),
    ("Sara", "Weiss"),
    ("Felix", "Nowak"),
    ("Amara", "Mensah"),
]

PRODUCTS = ["Fieldnote App", "Fieldnote Sync", "Fieldnote Pen", "Fieldnote Book", "Capture Clip"]
PLANS = ["Free", "Studio", "Team", "Archive"]
CARRIERS = ["UPS", "FedEx", "USPS", "DHL"]
FEATURES = ["calendar embed", "citation export", "dark paper themes", "audio bookmarks", "heading outlines"]
AMOUNTS = ["12.00", "19.00", "29.00", "49.00", "79.00", "129.00", "240.00"]
ERRORS = ["FN-500", "FN-401", "FN-SYNC-12", "FN-BILL-03", "FN-DEV-9"]

SENTIMENT_OPENERS = {
    "negative": [
        "I'm frustrated that this is still happening.",
        "This has been a disappointing experience so far.",
        "I shouldn't have to write in about this. It's unacceptable.",
        "Honestly, I'm annoyed this wasn't caught earlier.",
    ],
    "neutral": [
        "Writing in with a straightforward question.",
        "Here are the details, as plainly as I can put them.",
        "I wanted to document what I'm seeing.",
        "Passing along the facts so you can take a look.",
    ],
    "positive": [
        "I like {product} overall, and I'm hoping you can help with one thing.",
        "Thanks in advance. The rest of {product} has been great.",
        "I appreciate the work that goes into {product}. I have one request.",
        "I'm happy with the {plan} plan and just need a hand with this.",
    ],
}

SENTIMENT_DETAILS = {
    "negative": [
        "I've already lost time to this and I'm out of patience.",
        "This is the third time I've had to chase it.",
        "None of the steps I tried changed anything.",
        "I'd like a real answer, not another delay.",
    ],
    "neutral": [
        "I can send a screenshot if you tell me which screen you need.",
        "Happy to add logs if that would help.",
        "I tried again this morning and got the same result.",
        "A teammate can confirm the same steps.",
    ],
    "positive": [
        "Aside from this, the app has been reliable for me.",
        "I like the notebook layout and want to keep using it.",
        "Thanks for making the rest of the workflow easy.",
        "I'm glad to stay on {plan} once this is cleared up.",
    ],
}

CLOSINGS = {
    "negative": [
        "Please don't send me a generic help-center link.",
        "I expect this to be resolved properly.",
        "Please reply on this thread when you have an update.",
    ],
    "neutral": [
        "Let me know if you need anything else from me.",
        "Thanks for taking a look.",
        "I can follow up with more detail.",
    ],
    "positive": [
        "Thanks for the help.",
        "Grateful for any guidance you can share.",
        "Thanks again.",
    ],
}

PRIORITY_LINES = {
    "low": [
        "There's no rush on this. Whenever the queue gets to it is fine.",
        "Please treat this as low priority whenever you have spare time.",
        "I'm not waiting on this for any deadline.",
        "A reply sometime next week is perfectly fine.",
    ],
    "medium": [
        "I'd like a reply in the next couple of days if you can.",
        "This is a standard request and it can follow the normal queue.",
        "I can keep working in the meantime, so a normal turnaround is fine.",
        "Please take this in the regular rotation this week.",
    ],
    "high": [
        "This is blocking my work and I need it handled today.",
        "Please treat this as high priority. I can't finish the task until it's fixed.",
        "This has already failed more than once and it's getting in the way of my day.",
        "I need a fix today. This is high priority on my side.",
    ],
    "urgent": [
        "This is urgent. I am completely stopped and need a response today.",
        "Please treat this as an urgent outage. I can't wait until tomorrow.",
        "ASAP: this is stopping a live workshop and I need help now.",
        "Urgent request. My work is down until you step in.",
    ],
}

GENERIC_DETAILS = [
    "It started about {days} days ago.",
    "I already restarted the app and signed back in.",
    "This happens on both my laptop and my phone.",
    "I first noticed it after the last update.",
    "My connection is stable, so this does not look like a local network blip.",
    "The reference on my side is {order_id}.",
]

CASES = {
    "billing": [
        {
            "subject": "Duplicate charge of {amount} on {order_id}",
            "body": "I was charged {amount} twice for {product} on order {order_id}. The card ending {last4} shows two captures this morning.",
            "resolution": "I confirmed a duplicate capture of {amount} on order {order_id} and reversed the second charge to the card ending {last4}. A revised receipt is on the way.",
        },
        {
            "subject": "Still billed for {plan} after I cancelled",
            "body": "My {plan} subscription for {product} renewed, but I cancelled it {days} days ago. Please stop the invoice and confirm the card ending {last4} will not be billed again.",
            "resolution": "I cancelled the renewal on the {plan} plan for {product} and issued a credit for the invoice you disputed. The card ending {last4} will not be billed for that renewal.",
        },
        {
            "subject": "Invoice for {order_id} does not match {plan}",
            "body": "The invoice for order {order_id} lists {amount}, which is more than the {plan} price I agreed to for {product}. The sales tax also looks like the wrong state.",
            "resolution": "I corrected the tax jurisdiction on invoice {order_id} and resent the itemized receipt. The revised total replaces the {amount} charge.",
        },
        {
            "subject": "Payment for {product} failed with {error_code}",
            "body": "Checkout for {product} keeps failing with {error_code}. The payment method ending {last4} works everywhere else, and the {plan} renewal is now unpaid.",
            "resolution": "I stored the card ending {last4} again and retried the failed charge for {product}. {error_code} cleared after the new payment method was saved.",
        },
        {
            "subject": "Need the receipt for order {order_id}",
            "body": "I need a copy of the invoice for order {order_id} ({amount}) for an expense report. I can't find it in the billing tab for {product}.",
            "resolution": "I resent the itemized invoice for order {order_id} to this address. It covers the {amount} charge for {product}.",
        },
        {
            "subject": "Unrecognized {amount} subscription charge",
            "body": "There is a {amount} charge from Fieldnote that I don't recognize on the card ending {last4}. It might be tied to {product}, but I only remember the {plan} plan.",
            "resolution": "I matched the {amount} charge to the {plan} renewal for {product} and emailed the invoice. Tell me if that renewal was not yours and I will open a dispute.",
        },
    ],
    "technical": [
        {
            "subject": "{product} crashes with {error_code}",
            "body": "{product} closes a few seconds after I open a notebook. I get {error_code} and then the window is gone. This started {days} days ago.",
            "resolution": "I reproduced {error_code} on {product} from the build in your log and flagged it to engineering. A restart of the sync service keeps the window open while the fix is shipped.",
        },
        {
            "subject": "Sync stuck on {product} after the update",
            "body": "Sync has been stuck on uploading for my {plan} workspace in {product}. Edits on my phone never reach the desktop app. License reference {order_id}.",
            "resolution": "I reset the sync cursor on the {plan} workspace for {product}. The phone edits queued under {order_id} finished uploading after that reset.",
        },
        {
            "subject": "Search in {product} returns nothing",
            "body": "Search used to find handwritten pages in {product}. Now it returns an empty list even for titles I can see in the notebook. Error {error_code} shows in the log.",
            "resolution": "I rebuilt the search index for {product}. {error_code} was a stale index, and the handwritten titles are searchable again.",
        },
        {
            "subject": "Fieldnote Pen drops the connection to {product}",
            "body": "I paired the Fieldnote Pen with {product} and it drops every few minutes. The app shows {error_code}. I need pairing to stay up for class.",
            "resolution": "I cleared the pen pairing cache for {product} and had you pair it again. {error_code} stopped once the radio firmware finished updating.",
        },
        {
            "subject": "Shared notebook fails with {error_code}",
            "body": "Shared notebook links from {product} spin and then fail with {error_code}. Teammates on the {plan} plan can't open them either.",
            "resolution": "I repaired the share records on the {plan} workspace. {error_code} was a broken link token, and the notebooks in {product} open for your teammates now.",
        },
        {
            "subject": "Offline edits in {product} disappeared",
            "body": "I edited notes offline in {product}. When it came back online those pages were blank, and nothing is in recently deleted. Reference {order_id}.",
            "resolution": "I restored the offline pages for {product} from the local conflict copy tied to {order_id}. They are back in the notebook and marked as recovered.",
        },
    ],
    "account": [
        {
            "subject": "Locked out of my {product} login",
            "body": "I can't sign in to {product}. The password is accepted and then the account is locked. I still have access to this inbox.",
            "resolution": "I unlocked the login for {product} after confirming this inbox. You can sign in with the current password, and the lockout counter is reset.",
        },
        {
            "subject": "Password reset email never arrives",
            "body": "Password reset emails for my Fieldnote login never arrive. I checked spam. The address on the {product} account is the one I'm writing from. Reference {order_id}.",
            "resolution": "I confirmed the inbox on the account and issued a fresh reset link for {product}. The earlier messages for {order_id} were blocked by the mail provider and did not leave our side.",
        },
        {
            "subject": "2FA codes rejected for {product}",
            "body": "My authenticator won't accept the 2FA code for {product}. The backup codes are rejected too. Error {error_code} appears after the third try.",
            "resolution": "I reset two-factor authentication on {product} after verifying this inbox. {error_code} was a drifted authenticator clock. New backup codes are in the account settings.",
        },
        {
            "subject": "SSO loop on the {plan} workspace",
            "body": "We turned on SSO for the {plan} workspace and the {product} sign-in page loops back to the password form. The error is {error_code}.",
            "resolution": "I corrected the SSO reply URL for the {plan} workspace. {error_code} was a mismatched redirect, and {product} now completes the SSO sign-in.",
        },
        {
            "subject": "Change the email on my login",
            "body": "Please change the login email on my {product} account. I still have access on this address and can approve the change. The plan is {plan}.",
            "resolution": "I started the email change on the {product} account and sent the confirmation to the new address you replied with. The {plan} subscription stays on the same profile.",
        },
        {
            "subject": "Team invite to {product} says it expired",
            "body": "A teammate sent a {plan} invite for {product} and the link says it is expired. I need to be on that workspace. Reference {order_id}.",
            "resolution": "I issued a new {plan} invite for {product} tied to {order_id}. The previous link had expired, and the new one is valid for 7 days.",
        },
    ],
    "shipping": [
        {
            "subject": "Tracking {tracking} for {order_id} has not moved",
            "body": "Order {order_id} for {product} was handed to {carrier} and tracking {tracking} has not updated in {days} days.",
            "resolution": "I checked tracking {tracking} with {carrier}. The scan gap on order {order_id} cleared overnight, and the {product} is back in transit.",
        },
        {
            "subject": "{carrier} says {order_id} was delivered, but it was not",
            "body": "{carrier} shows order {order_id} as delivered. Nothing was at the door or the mailroom. Tracking {tracking} is the only scan I have for the {product}.",
            "resolution": "I opened a delivery dispute with {carrier} for tracking {tracking}. They did not have a doorstep photo, so I reshipped the {product} from order {order_id}.",
        },
        {
            "subject": "Wrong item shipped for order {order_id}",
            "body": "I received the wrong color of {product} for order {order_id}. The packing slip matches the box, not what I ordered.",
            "resolution": "I shipped the correct {product} for order {order_id} and emailed a return label for the color that arrived by mistake.",
        },
        {
            "subject": "Please change the address on {order_id}",
            "body": "Please update the shipping address on order {order_id} before {carrier} picks it up. Tracking is not assigned yet. The order is for {product}.",
            "resolution": "I updated the address on order {order_id} before the {carrier} pickup. The {product} will ship to the address in your last note.",
        },
        {
            "subject": "Split shipment is missing the {product}",
            "body": "Part of order {order_id} arrived, but the {product} from the split shipment is missing. {carrier} only shows tracking {tracking}.",
            "resolution": "The second package for order {order_id} was never tendered to {carrier}. I created a new shipment for the {product} and the replacement tracking will send today.",
        },
        {
            "subject": "Order {order_id} arrived damaged",
            "body": "The box for order {order_id} arrived crushed and the {product} inside is damaged. {carrier} tracking is {tracking}.",
            "resolution": "I marked order {order_id} as damaged in transit with {carrier} under tracking {tracking} and shipped a replacement {product}. You can discard the crushed unit.",
        },
    ],
    "returns": [
        {
            "subject": "No return label for order {order_id}",
            "body": "I started a return for order {order_id} ({product}) and never received the label. It has been {days} days.",
            "resolution": "I reissued the return label for order {order_id} and attached it to this thread. Drop the {product} with any {carrier} scan and the RMA will update.",
        },
        {
            "subject": "Refund of {amount} is still missing",
            "body": "The refund of {amount} for order {order_id} is still not back on the card ending {last4}. {carrier} scanned the return. Tracking {tracking}.",
            "resolution": "The warehouse scan for tracking {tracking} posted yesterday. I released the {amount} refund for order {order_id} back to the card ending {last4}.",
        },
        {
            "subject": "Exchange {product} from order {order_id}",
            "body": "I'd like to exchange the {product} from order {order_id} for a different color rather than a refund. The return tracking is {tracking}.",
            "resolution": "I converted order {order_id} from a refund to an exchange. Once tracking {tracking} is scanned at the warehouse, the replacement {product} will ship.",
        },
        {
            "subject": "What is the RMA status for {order_id}?",
            "body": "What is the status of the RMA for order {order_id}? I dropped the {product} off {days} days ago with {carrier}.",
            "resolution": "The RMA for order {order_id} was received from {carrier} and the {product} passed inspection. The refund is queued to the original payment method.",
        },
        {
            "subject": "Refund was only {amount} for order {order_id}",
            "body": "You received the {product} I sent back, but the refund was {amount}, which is less than the order total. The card ending {last4} shows the smaller credit.",
            "resolution": "I reviewed the credit for order {order_id}. The first refund of {amount} left out shipping you had already paid, and I sent the remainder to the card ending {last4}.",
        },
        {
            "subject": "Please cancel the return on {order_id}",
            "body": "Please cancel the return on order {order_id}. I want to keep the {product}. The label was created but {carrier} has not scanned tracking {tracking}.",
            "resolution": "I cancelled the return on order {order_id} before {carrier} scanned tracking {tracking}. The {product} stays with you and no refund will be issued.",
        },
    ],
    "product": [
        {
            "subject": "Does {product} work offline on {plan}?",
            "body": "Before I upgrade, does {product} let me edit notebooks offline and sync later? I'm comparing that with the {plan} plan.",
            "resolution": "Yes. {product} on the {plan} plan stores notebooks offline and syncs when you reconnect. I left the setting path in the help note on your account.",
        },
        {
            "subject": "What does {plan} include for {product}?",
            "body": "What's included in {plan} that isn't on the lower tier for {product}? I mostly care about handwriting search and PDF export.",
            "resolution": "Handwriting search and PDF export are both on the {plan} plan for {product}. I sent the current limit table so you can compare it with the tier below.",
        },
        {
            "subject": "Can {product} export Markdown?",
            "body": "Can {product} export a notebook to Markdown, or only PDF? I don't see the option on the {plan} plan. Order reference {order_id}.",
            "resolution": "Markdown export is available on {plan} inside the share menu of {product}, not the print dialog. I pointed your account {order_id} at the current menu path.",
        },
        {
            "subject": "Will the pen work with {product} on {plan}?",
            "body": "Does the Fieldnote Pen work with {product} on the {plan} plan, or only on higher tiers? Order {order_id} was just the app.",
            "resolution": "The Fieldnote Pen pairs with {product} on the {plan} plan. Order {order_id} does not need a higher tier for pairing, only for shared workspaces.",
        },
        {
            "subject": "How many notebooks are allowed on {plan}?",
            "body": "How many active notebooks does {plan} allow? I'm planning a rollout of {product} for a small team.",
            "resolution": "The {plan} plan allows unlimited active notebooks for {product}, with a seat cap rather than a notebook cap. I attached the seat count for a small team.",
        },
        {
            "subject": "Please consider adding {feature}",
            "body": "Would you consider adding {feature} to {product}? It would make the {plan} plan easier to adopt for our notes.",
            "resolution": "I logged {feature} for {product} against the {plan} plan and added your note to that request. It is not on the current release, and I subscribed this address to updates.",
        },
    ],
    "trust": [
        {
            "subject": "Suspicious login on {product}",
            "body": "There is a login to {product} from a city I've never visited. I don't recognize the device. Please secure the account. The card on file ends in {last4}.",
            "resolution": "I signed out every session on {product} except the one that answered the confirmation mail, and I turned on a fresh 2FA enrollment. The card ending {last4} was not changed.",
        },
        {
            "subject": "Please delete my {product} data",
            "body": "Please delete my account and the notebooks stored for {product}. I want confirmation that backups are included. Reference {order_id}.",
            "resolution": "I queued deletion for the {product} account on reference {order_id}, including backups. You'll get a confirmation on this address when the purge finishes.",
        },
        {
            "subject": "Phishing email pretending to be Fieldnote",
            "body": "I got an email telling me to reset my Fieldnote password from a domain that isn't yours. I did not click it. What should I check on {product}?",
            "resolution": "That message is not from us. I checked {product} and there is no password reset in progress. I sent the domains we actually mail from so you can filter the phishing copy.",
        },
        {
            "subject": "Lost device is still signed in to {product}",
            "body": "A device I lost is still signed in to {product}. Please sign it out everywhere and tell me if the notebooks were opened. The plan is {plan}.",
            "resolution": "I revoked the lost device on the {plan} workspace for {product}. The session list shows it opened the app but not individual notebooks after the time you gave me.",
        },
        {
            "subject": "Unknown person joined our {plan} workspace",
            "body": "Someone I don't know appeared as a member of our {plan} workspace in {product}. I didn't send an invite. Please remove them and check the share links.",
            "resolution": "I removed the unknown member from the {plan} workspace and expired public share links on {product}. No further invites are outstanding.",
        },
        {
            "subject": "A shared link from {product} may have leaked",
            "body": "A shared link to a notebook may have leaked. Please disable public links on my {product} account and confirm who opened them. Reference {order_id}.",
            "resolution": "I disabled public links on the {product} account for {order_id} and sent the open log. Only the addresses already on the notebook had viewed it.",
        },
    ],
}


def _choice(rng, items):
    return items[int(rng.integers(0, len(items)))]


def _tracking(rng, carrier: str) -> str:
    number = int(rng.integers(10**8, 10**9))
    if carrier == "UPS":
        return f"1Z{number}"
    if carrier == "USPS":
        return f"9400{number}"
    if carrier == "DHL":
        return f"DHL{number}"
    return f"FX{number}"


def _sample_slots() -> dict:
    return {
        "product": "Fieldnote App",
        "order_id": "FN-10001",
        "amount": "$49.00",
        "error_code": "FN-500",
        "plan": "Studio",
        "carrier": "UPS",
        "tracking": "1Z100",
        "last4": "4242",
        "days": "4",
        "feature": "calendar embed",
    }


def _assert_templates() -> None:
    slots = _sample_slots()
    expected = {item["slug"] for item in DEPARTMENTS}
    if set(CASES) != expected:
        raise RuntimeError(f"Case departments do not match the routing list: {set(CASES) ^ expected}")
    if set(SENTIMENT_OPENERS) != set(SENTIMENTS) or set(SENTIMENT_DETAILS) != set(SENTIMENTS):
        raise RuntimeError("Sentiment templates are missing a class.")
    if set(PRIORITY_LINES) != set(PRIORITIES) or set(CLOSINGS) != set(SENTIMENTS):
        raise RuntimeError("Priority or closing templates are missing a class.")
    for cases in CASES.values():
        if len(cases) < 4:
            raise RuntimeError("Each department needs several distinct cases.")
        for case in cases:
            case["subject"].format(**slots)
            case["body"].format(**slots)
            case["resolution"].format(**slots)
    for group in (SENTIMENT_OPENERS, SENTIMENT_DETAILS, CLOSINGS, PRIORITY_LINES):
        for templates in group.values():
            for template in templates:
                template.format(**slots)
    for template in GENERIC_DETAILS:
        template.format(**slots)


def _tidy(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _mix(rng, count: int, choices, probs) -> list:
    counts = [int(round(count * prob)) for prob in probs]
    while sum(counts) > count:
        counts[counts.index(max(counts))] -= 1
    while sum(counts) < count:
        counts[0] += 1
    values = []
    for choice, size in zip(choices, counts):
        values.extend([choice] * size)
    rng.shuffle(values)
    return values


def _slots(rng) -> dict:
    first, last = _choice(rng, PEOPLE)
    carrier = _choice(rng, CARRIERS)
    return {
        "product": _choice(rng, PRODUCTS),
        "order_id": f"FN-{int(rng.integers(10000, 100000))}",
        "amount": f"${_choice(rng, AMOUNTS)}",
        "error_code": _choice(rng, ERRORS),
        "plan": _choice(rng, PLANS),
        "carrier": carrier,
        "tracking": _tracking(rng, carrier),
        "last4": f"{int(rng.integers(0, 10000)):04d}",
        "days": str(int(rng.integers(2, 16))),
        "feature": _choice(rng, FEATURES),
        "customer_name": f"{first} {last}",
        "email": f"{first}.{last}@fieldnote.example".lower().replace(" ", ""),
    }


def generate(n: int = N_TICKETS, seed: int = 42) -> list[dict]:
    _assert_templates()
    rng = np.random.default_rng(seed)
    slugs = [item["slug"] for item in DEPARTMENTS]
    departments = [slugs[index % len(slugs)] for index in range(n)]
    rng.shuffle(departments)
    priorities = _mix(rng, n, PRIORITIES, (0.18, 0.42, 0.25, 0.15))
    sentiments = _mix(rng, n, SENTIMENTS, (0.46, 0.34, 0.20))
    rows = []
    for index in range(n):
        slots = _slots(rng)
        case = _choice(rng, CASES[departments[index]])
        subject = _tidy(case["subject"].format(**slots))
        parts = [case["body"].format(**slots)]
        # A few tickets are mostly another queue's wording. The label stays
        # with the original scenario so department classification is not perfect.
        roll = float(rng.random())
        if roll < 0.06:
            other_slug = _choice(rng, [slug for slug in slugs if slug != departments[index]])
            parts = [_choice(rng, CASES[other_slug])["body"].format(**slots)]
            subject = f"Help with order {slots['order_id']}"
        elif roll < 0.16:
            other_slug = _choice(rng, [slug for slug in slugs if slug != departments[index]])
            parts.append(_choice(rng, CASES[other_slug])["body"].format(**slots))
        if rng.random() < 0.55:
            parts.append(_choice(rng, GENERIC_DETAILS).format(**slots))
        # Some tickets omit the explicit tone or urgency line.
        if rng.random() > 0.1:
            parts.insert(0, _choice(rng, SENTIMENT_OPENERS[sentiments[index]]).format(**slots))
            parts.append(_choice(rng, SENTIMENT_DETAILS[sentiments[index]]).format(**slots))
            parts.append(_choice(rng, CLOSINGS[sentiments[index]]).format(**slots))
        if rng.random() > 0.18:
            parts.append(_choice(rng, PRIORITY_LINES[priorities[index]]).format(**slots))
        rows.append(
            {
                "subject": subject,
                "body": _tidy(" ".join(parts)),
                "department": departments[index],
                "priority": priorities[index],
                "sentiment": sentiments[index],
                "customer_name": slots["customer_name"],
                "customer_email": slots["email"],
                "resolution": _tidy(case["resolution"].format(**slots)),
            }
        )
    return rows
