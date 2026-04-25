"""
MCP Server — exposes job bot tools so Claude can orchestrate the full workflow
"""
import json
import asyncio
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import types

from scrapers import scrape_all
from agent import process_jobs
from tracker import upsert_jobs, get_review_queue, update_status, get_all_applications
from config import REVIEW_MIN_SCORE

app = Server("job-bot")


@app.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="scrape_jobs",
            description="Scrape new job listings from Indeed, LinkedIn, and Remotive",
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        types.Tool(
            name="score_and_queue",
            description="Score scraped jobs with Claude and save qualified ones to Supabase review queue",
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        types.Tool(
            name="get_review_queue",
            description="Get all jobs in the review queue sorted by score",
            inputSchema={
                "type": "object",
                "properties": {
                    "min_score": {"type": "integer", "description": "Minimum score filter (default 7)"}
                },
                "required": [],
            },
        ),
        types.Tool(
            name="update_job_status",
            description="Update the status of a job application",
            inputSchema={
                "type": "object",
                "properties": {
                    "job_id": {"type": "string"},
                    "status": {
                        "type": "string",
                        "enum": ["new", "reviewing", "applied", "interview", "rejected", "skipped"],
                    },
                },
                "required": ["job_id", "status"],
            },
        ),
        types.Tool(
            name="get_all_applications",
            description="Get all tracked job applications with their current status",
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        types.Tool(
            name="run_full_pipeline",
            description="Run the complete pipeline: scrape → score → save to queue",
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:

    if name == "scrape_jobs":
        jobs = scrape_all()
        return [types.TextContent(
            type="text",
            text=json.dumps({"count": len(jobs), "jobs": jobs[:5]})  # preview first 5
        )]

    elif name == "score_and_queue":
        jobs = scrape_all()
        qualified = process_jobs(jobs)
        upsert_jobs(qualified)
        return [types.TextContent(
            type="text",
            text=json.dumps({"queued": len(qualified),
                             "top_jobs": [{"title": j["title"], "company": j.get("company",""),
                                           "score": j["score"]} for j in qualified[:10]]})
        )]

    elif name == "get_review_queue":
        min_score = arguments.get("min_score", REVIEW_MIN_SCORE)
        queue = get_review_queue(min_score)
        return [types.TextContent(type="text", text=json.dumps(queue))]

    elif name == "update_job_status":
        update_status(arguments["job_id"], arguments["status"])
        return [types.TextContent(type="text", text=f"Updated {arguments['job_id']} → {arguments['status']}")]

    elif name == "get_all_applications":
        apps = get_all_applications()
        return [types.TextContent(type="text", text=json.dumps(apps))]

    elif name == "run_full_pipeline":
        jobs = scrape_all()
        qualified = process_jobs(jobs)
        upsert_jobs(qualified)
        summary = {
            "total_scraped": len(jobs),
            "qualified": len(qualified),
            "top_10": [{"title": j["title"], "company": j.get("company",""),
                        "score": j["score"], "reason": j.get("score_reason","")}
                       for j in sorted(qualified, key=lambda x: x["score"], reverse=True)[:10]]
        }
        return [types.TextContent(type="text", text=json.dumps(summary, indent=2))]

    return [types.TextContent(type="text", text="Unknown tool")]


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
