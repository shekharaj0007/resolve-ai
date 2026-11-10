import re

from pydantic import BaseModel, Field, field_validator

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class TicketCreate(BaseModel):
    subject: str = Field(min_length=3, max_length=240)
    body: str = Field(min_length=10, max_length=8000)
    customer_name: str = Field(min_length=2, max_length=120)
    customer_email: str = Field(min_length=5, max_length=180)

    @field_validator("subject", "body", "customer_name", "customer_email")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return value.strip()

    @field_validator("customer_email")
    @classmethod
    def check_email(cls, value: str) -> str:
        if not EMAIL_RE.match(value):
            raise ValueError("Enter a valid email address")
        return value


class ValidationIn(BaseModel):
    department: str
    priority: str
    sentiment: str
    agent: str = Field(min_length=2, max_length=120)

    @field_validator("department", "priority", "sentiment", "agent")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return value.strip()


class ReplyIn(BaseModel):
    body: str = Field(min_length=2, max_length=8000)
    agent: str = Field(min_length=2, max_length=120)
    used_suggestion: bool = False
    resolve: bool = False
    department: str | None = None
    priority: str | None = None
    sentiment: str | None = None

    @field_validator("body", "agent")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return value.strip()


class StatusIn(BaseModel):
    status: str

    @field_validator("status")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return value.strip()
