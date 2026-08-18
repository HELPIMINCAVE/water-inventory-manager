import random
import re
import string


def generate_otp() -> str:
    return "".join(random.choices(string.digits, k=6))

def has_repeating_sequence(text: str, max_repeat: int = 3) -> bool:
    pattern = rf"(.)\1{{{max_repeat - 1},}}"
    return bool(re.search(pattern, text))

def validate_strict_password(
    password: str, username: str = ""
) -> tuple[bool, str]:
    if not password or not password.strip():
        return False, "Password cannot be blank."

    if username and password.strip().lower() == username.strip().lower():
        return False, "Password cannot be the same as the username."
    
    if len(password) < 8:
        return False, "Password must be at least 8 characters long."
    
    if username and username.lower() in password.lower():
        return False, "Password cannot contain your username."
        
    if has_repeating_sequence(password, max_repeat=3):
        return (
            False,
            "Password cannot contain 3 or more repeating consecutive characters"
            " (e.g., '111' or '222').",
        )
    
    if not re.search(r"[A-Z]", password):
        return False, "Password must contain at least one uppercase letter."

    if not re.search(r"\d", password):
        return False, "Password must contain at least one digit."

    if not re.search(r"[!@#$%^&*()_+\-=\[\]{};':\"\\|,.<>/?]", password):
        return False, "Password must contain at least one special character."

    for i in range(len(password) - 1):
        if password[i] == password[i + 1]:
            return (
                False,
                "Password cannot contain repeating consecutive characters"
                f" (e.g., '{password[i]*2}').",
            )

    lowered = password.lower()
    for i in range(len(lowered) - 2):
        c1, c2, c3 = ord(lowered[i]), ord(lowered[i + 1]), ord(lowered[i + 2])
        if c2 == c1 + 1 and c3 == c2 + 1:
            return (
                False,
                "Password cannot contain ordered sequences (e.g., '123',"
                " 'abc').",
            )
        if c2 == c1 - 1 and c3 == c2 - 1:
            return (
                False,
                "Password cannot contain reverse-ordered sequences (e.g.,"
                " '321', 'cba').",
            )

    return True, "Password meets all security criteria."