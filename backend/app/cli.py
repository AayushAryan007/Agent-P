"""Command-line entry points: `agentp api`, `agentp hash-token`."""

import argparse
import getpass
import secrets

import uvicorn


def main() -> None:
    parser = argparse.ArgumentParser(prog="agentp")
    sub = parser.add_subparsers(dest="command", required=True)

    api = sub.add_parser("api", help="Run the HTTP API")
    api.add_argument("--host", default="127.0.0.1")
    api.add_argument("--port", type=int, default=8000)
    api.add_argument("--reload", action="store_true")

    tok = sub.add_parser(
        "hash-token", help="Generate (or read) an admin token and print its ADMIN_TOKEN_HASH"
    )
    tok.add_argument("--prompt", action="store_true", help="Type your own token instead of generating one")

    args = parser.parse_args()
    if args.command == "api":
        uvicorn.run(
            "app.main:create_app",
            factory=True,
            host=args.host,
            port=args.port,
            reload=args.reload,
            proxy_headers=True,
            access_log=False,  # RequestContextMiddleware logs requests with correlation ids
        )
    elif args.command == "hash-token":
        from app.security.auth import hash_token

        token = getpass.getpass("Admin token: ") if args.prompt else secrets.token_urlsafe(32)
        if not args.prompt:
            print(f"Admin token (keep it secret, use it to sign in): {token}")
        # Single quotes: argon2 hashes contain '$', which dotenv/shell would otherwise expand.
        print(f"ADMIN_TOKEN_HASH='{hash_token(token)}'")
