import uuid


def generate_id(prefix: str = "") -> str:
    """Generate a clean, collision-free identifier with an optional prefix."""
    raw = uuid.uuid4().hex[:12]
    return f"{prefix}_{raw}" if prefix else raw
