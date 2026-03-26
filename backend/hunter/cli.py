import logging

import typer

from hunter.pipeline.discover import run_discovery

app = typer.Typer(no_args_is_help=True)


@app.command()
def discover(
    topic: str = typer.Option(
        ...,
        "--topic",
        help="Topic key from keywords.yaml (e.g. football_equipment, smart_wearables).",
    ),
    max_queries: int | None = typer.Option(
        None,
        "--max-queries",
        help="Max YouTube search queries to run for this topic (default: min(6, configured)).",
    ),
    max_per_query: int = typer.Option(
        15,
        "--max-per-query",
        help="Max video results per search query (1–50).",
    ),
    max_videos: int = typer.Option(
        120,
        "--max-videos",
        help="Stop after collecting this many unique videos (quota guard).",
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Log HTTP retries and details."),
) -> None:
    """Run YouTube discovery for a topic and store ranked channels in SQLite."""
    if verbose:
        logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    try:
        summary = run_discovery(
            topic,
            max_queries=max_queries,
            max_results_per_query=max_per_query,
            max_total_videos=max_videos,
        )
    except ValueError as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(code=1) from e
    except Exception as e:
        typer.echo(f"Discovery failed: {e}", err=True)
        raise typer.Exit(code=2) from e

    typer.echo(
        f"Done: topic={summary['topic']} queries={summary['queries']} "
        f"videos={summary['videos']} channels={summary['channels']}",
    )


@app.command()
def version() -> None:
    """Print package version."""
    from hunter import __version__ as v

    typer.echo(v)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
