def ticket_text(subject: str, body: str) -> str:
    return f"{(subject or '').strip()}\n{(body or '').strip()}"
