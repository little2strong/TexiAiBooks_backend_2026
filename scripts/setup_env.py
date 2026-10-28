"""Create local development secrets once, without printing or overwriting them."""

from pathlib import Path
import base64
import json
import secrets


def main() -> None:
    path = Path(__file__).resolve().parents[1] / ".env"
    content = (
        "POSTGRES_DB=taxiaibooks\n"
        "POSTGRES_USER=taxi_user\n"
        f"POSTGRES_PASSWORD={secrets.token_urlsafe(32)}\n"
        "POSTGRES_HOST=127.0.0.1\n"
        "POSTGRES_PORT=5433\n"
        f"JWT_SECRET_KEY={secrets.token_urlsafe(48)}\n"
        f"IDENTIFIER_ENCRYPTION_KEYS={json.dumps([base64.urlsafe_b64encode(secrets.token_bytes(32)).decode()])}\n"
        f"PHONE_IDENTITY_HMAC_KEY={secrets.token_urlsafe(48)}\n"
        "ACCESS_TOKEN_EXPIRE_MINUTES=15\n"
    )
    try:
        with path.open("x", encoding="utf-8") as file:
            file.write(content)
    except FileExistsError:
        print("Existing .env preserved.")
    else:
        print("Created .env with random development credentials (values hidden).")


if __name__ == "__main__":
    main()

