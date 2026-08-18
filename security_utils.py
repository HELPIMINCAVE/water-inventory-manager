import random, re, string

def generate_otp(length: int = 6) -> str:
    return "".join(random.choices(string.digits, k=length))

def has_repeating_sequence(text: str, max_repeat: int = 3) -> bool:
    pattern = r"(.)\1{2,}"
    return bool(re.search(pattern, text))

def validate_strict_password(password: str, username: str = "") -> tuple[bool, str]:
    if len(password) < 8:
        return False, "Password must be at least 8 characters long."

    if username and username.lower() in password.lower():
        return False, "Password cannot contain your username."

    if has_repeating_sequence(password, max_repeat=3):
        return (
            False,
            "Password cannot contain 3 or more consecutive repeating characters (e.g., '111' or '222').",
        )

    return True, ""