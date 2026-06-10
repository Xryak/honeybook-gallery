from __future__ import annotations

import httpx
import typer

app = typer.Typer(add_completion=False, help="Honeybook backend CLI.")

DEFAULT_BASE_URL = "http://localhost:8000"


@app.callback()
def _root() -> None:
    """Force Typer into multi-command mode so `send-otp` is parsed as a subcommand."""


@app.command("send-otp")
def send_otp(
    gallery_id: str = typer.Argument(..., help="Gallery ID, e.g. g_001."),
    base_url: str = typer.Option(
        DEFAULT_BASE_URL, "--base-url", help="Backend base URL."
    ),
) -> None:
    """Trigger an OTP for GALLERY_ID; code is logged to the backend stdout."""
    url = f"{base_url.rstrip('/')}/api/galleries/{gallery_id}/otp"
    try:
        resp = httpx.post(url, timeout=5.0)
    except httpx.ConnectError:
        typer.echo(
            f"Could not connect to backend at {base_url}. Is `uvicorn app.main:app` running?",
            err=True,
        )
        raise typer.Exit(code=1) from None
    except httpx.HTTPError as e:
        typer.echo(f"HTTP error talking to {url}: {e}", err=True)
        raise typer.Exit(code=1) from None

    if resp.status_code == 200:
        typer.echo(
            f"OK — backend generated an OTP for {gallery_id}. "
            f"Read the code from the backend terminal."
        )
        typer.echo(resp.text)
        return

    if resp.status_code == 404:
        typer.echo(f"Gallery {gallery_id} not found.", err=True)
    else:
        typer.echo(
            f"Unexpected status {resp.status_code} from {url}: {resp.text}",
            err=True,
        )
    raise typer.Exit(code=1)


@app.command("reseed")
def reseed() -> None:
    """Idempotently (re)create galleries + seed photos in-process.

    Safe to run repeatedly: it never wipes favorites and only generates photo
    files that are missing. Runs directly against the DB — the server does not
    need to be up.
    """
    from .db import SessionLocal
    from .seed import init_db_and_seed

    with SessionLocal() as db:
        init_db_and_seed(db)
    typer.echo("Seed complete (galleries + photos ensured; favorites untouched).")


def main() -> None:  # pragma: no cover - thin console_scripts entrypoint
    app()


if __name__ == "__main__":  # pragma: no cover
    main()
