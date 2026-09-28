import typer

from . import __version__
from .commands import lol, tft, valorant


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"opgg-cli {__version__}")
        raise typer.Exit()


app = typer.Typer(
    name="opgg",
    help="Query OP.GG data for League of Legends, TFT and Valorant.",
    no_args_is_help=True,
    add_completion=False,
)

app.add_typer(lol.app, name="lol", help="League of Legends commands")
app.add_typer(tft.app, name="tft", help="Teamfight Tactics commands")
app.add_typer(valorant.app, name="valorant", help="Valorant commands")


@app.callback()
def main(
    version: bool = typer.Option(
        False,
        "--version",
        "-V",
        callback=_version_callback,
        is_eager=True,
        help="Show version and exit.",
    ),
) -> None:
    """Query OP.GG data for League of Legends, TFT and Valorant."""


if __name__ == "__main__":
    app()
