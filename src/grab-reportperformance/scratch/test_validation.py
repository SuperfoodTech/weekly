import re

def validate_credentials(username, password):
    """
    Smarter and stricter credential validation to catch common human errors.
    Returns (is_valid, error_message)
    """
    if not username or not password:
        return False, "Username or password is empty"
        
    u = str(username).strip().replace('\xa0', '')
    p = str(password).strip().replace('\xa0', '')
    
    if not u or not p:
        return False, "Username or password contains only whitespace"
        
    # Placeholders check
    placeholders = {'-', '--', 'null', 'none', 'n/a', 'na', 'sandi', 'password', 'username', 'pengguna'}
    if u.lower() in placeholders or p.lower() in placeholders:
        return False, f"Credential contains a placeholder value (user: '{u}', pwd: '{p}')"
        
    # Check if username and password are identical
    if u.lower() == p.lower():
        return False, f"Username and Password are identical (likely copy-paste error): '{u}'"
        
    # Check if password is too short
    if len(p) < 6:
        return False, f"Password is too short (less than 6 characters): '{p}'"
        
    # Check if password contains the username, or username contains the password
    if len(u) > 5 and u.lower() in p.lower():
        return False, f"Password contains the username (likely copy-paste or duplicate error): '{p}'"
    if len(p) > 8 and p.lower() in u.lower():
        return False, f"Password is a substring of the username (likely copy-paste or duplicate error): '{p}'"
        
    # Check if password looks like an email/username (usually contains @ or domain)
    email_pattern = r'[^@\s]+@[^@\s]+\.[^@\s]+'
    if re.search(email_pattern, p):
        return False, f"Password looks like an email address (likely copy-paste or swap error): '{p}'"
        
    # Domain specific rule: Superfood usernames end with 'superfood'
    if p.lower().endswith('superfood') and len(p) > 10:
        return False, f"Password looks like a Superfood merchant username (ends with 'superfood'): '{p}'"
        
    return True, ""

# Test cases
test_cases = [
    # Valid cases
    ("krispyporkexpresspermatabuanasuperfood", "Master@124", True),
    ("limsuperfood", "Master@123", True),
    ("superfoodinternship@gmail.com", "Master@123", True),
    
    # Invalid cases - placeholders
    ("-", "Master@123", False),
    ("limsuperfood", "-", False),
    ("limsuperfood", "None", False),
    
    # Invalid cases - identical
    ("krispyporkexpresspermatabuanasuperfood", "krispyporkexpresspermatabuanasuperfood", False),
    ("limsuperfood", "limsuperfood", False),
    
    # Invalid cases - copy paste username in password
    ("krispyporkexpresspermatabuanasuperfood", "krispyporkexpresspermatabuanasuperfood_extra", False),
    ("krispyporkexpresspermatabuanasuperfood", "krispyporkexpresspermatabuana", False),
    
    # Invalid cases - password is email
    ("krispyporkexpresspermatabuanasuperfood", "superfoodinternship@gmail.com", False),
    
    # Invalid cases - ends with superfood
    ("krispyporkexpresspermatabuanasuperfood", "anothermerchantnamessuperfood", False),
    
    # Invalid cases - short password
    ("limsuperfood", "123", False),
]

print("Running test cases:")
for i, (u, p, expected) in enumerate(test_cases):
    is_valid, msg = validate_credentials(u, p)
    status = "PASS" if is_valid == expected else "FAIL"
    print(f"Test {i+1}: user='{u}', pwd='{p}' -> valid={is_valid} ({msg if not is_valid else 'OK'}) -> {status}")
