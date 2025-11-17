#!/usr/bin/env python3
"""Trinity CLI - Command line interface for Trinity Intelligence Platform"""

import click
import httpx
import json

TRINITY_BASE_URL = "http://localhost:8002"  # RCA API
INVESTIGATION_URL = "http://localhost:8003"  # Investigation API

@click.group()
def cli():
    """Trinity Intelligence Platform CLI"""
    pass

@cli.command()
@click.argument('issue_description')
@click.option('--component', help='Affected component/service')
def rca(issue_description, component):
    """Perform root cause analysis"""

    response = httpx.post(
        f"{TRINITY_BASE_URL}/api/rca",
        json={"issue_description": issue_description, "component": component},
        timeout=30.0
    )

    if response.status_code == 200:
        data = response.json()

        click.echo(f"\n{'='*60}")
        click.echo("TRINITY RCA ANALYSIS")
        click.echo(f"{'='*60}\n")

        click.echo("Similar Issues Found:")
        for issue in data.get("similar_issues", []):
            click.echo(f"  • {issue['issue_id']}: {issue['title']}")
            click.echo(f"    Similarity: {issue['similarity']*100:.0f}%")
            click.echo(f"    Status: {issue['status']}\n")

        click.echo(f"Affected Services: {', '.join(data.get('affected_services', []))}")
        click.echo(f"\nEstimated Time: {data.get('estimated_time')}")
        click.echo(f"Confidence: {data.get('confidence')*100:.0f}%")

    else:
        click.echo(f"Error: {response.status_code}", err=True)

@cli.command()
@click.argument('task_description')
@click.option('--component', help='Component to analyze')
def investigate(task_description, component):
    """Investigation before starting work"""

    response = httpx.post(
        f"{INVESTIGATION_URL}/api/investigate",
        json={"task_description": task_description, "component": component},
        timeout=30.0
    )

    if response.status_code == 200:
        data = response.json()

        click.echo(f"\n{'='*60}")
        click.echo("TRINITY PRE-TASK INVESTIGATION")
        click.echo(f"{'='*60}\n")

        click.echo("Similar Past Work:")
        for work in data.get("similar_past_work", []):
            click.echo(f"  • {work}\n")

        click.echo(f"Affected Services: {', '.join(data.get('affected_services', []))}")

        click.echo("\nRecommendations:")
        for rec in data.get("recommended_approach", []):
            click.echo(f"  • {rec}")

        if data.get("warnings"):
            click.echo("\nWarnings:")
            for warn in data.get("warnings", []):
                click.echo(f"  ⚠ {warn}")

        click.echo(f"\nEstimated Effort: {data.get('estimated_effort')}")

    else:
        click.echo(f"Error: {response.status_code}", err=True)

@cli.command()
def health():
    """Check Trinity Platform health"""

    services = [
        ("RCA API", f"{TRINITY_BASE_URL}/health"),
        ("Investigation API", f"{INVESTIGATION_URL}/health")
    ]

    click.echo("\nTrinity Platform Health Check:\n")

    for name, url in services:
        try:
            response = httpx.get(url, timeout=5.0)
            if response.status_code == 200:
                click.echo(f"✅ {name}: Healthy")
            else:
                click.echo(f"❌ {name}: Unhealthy ({response.status_code})")
        except:
            click.echo(f"❌ {name}: Unreachable")

if __name__ == '__main__':
    cli()
