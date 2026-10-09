import logging
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

from app.runner import run_scrapers
from app.services.process_anthropic import process_anthropic_markdown
from app.services.process_youtube import process_youtube_transcripts
from app.services.process_digest import process_digests
from app.services.process_email import send_digest_email

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def _run_stage(results: dict, stage: str, operation, fallback):
    """Run a pipeline stage independently and retain failure details."""
    try:
        value = operation()
    except Exception as error:
        logger.exception("operation=pipeline.%s status=failed", stage)
        results["stage_status"][stage] = {
            "status": "failed",
            "error_type": type(error).__name__,
            "error": str(error),
        }
        results["errors"].append({
            "stage": stage, "error_type": type(error).__name__, "message": str(error),
        })
        return fallback

    results["stage_status"][stage] = {"status": "success"}
    return value


def _record_item_failures(results: dict, stage: str, value: dict, count_key: str = "failed") -> None:
    # A thrown exception is already recorded by _run_stage; do not downgrade it
    # to partial_failure or add a duplicate item-level error from its fallback.
    if results["stage_status"].get(stage, {}).get("status") == "failed":
        return

    failed_count = value.get(count_key, 0)
    if failed_count:
        results["stage_status"][stage] = {
            "status": "partial_failure",
            "failed_items": failed_count,
        }
        results["errors"].append({
            "stage": stage,
            "error_type": "ItemProcessingFailure",
            "message": f"{failed_count} item(s) failed during {stage}",
        })


def run_daily_pipeline(hours: int = 24, top_n: int = 10) -> dict:
    start_time = datetime.now()
    logger.info("=" * 60)
    logger.info("Starting Daily AI News Aggregator Pipeline")
    logger.info("=" * 60)

    results = {
        "start_time": start_time.isoformat(),
        "scraping": {},
        "processing": {},
        "digests": {},
        "email": {},
        "stage_status": {},
        "errors": [],
        "success": False,
        "status": "failed",
    }

    logger.info("[1/5] Scraping articles from sources...")
    scraping_results = _run_stage(results, "scraping", lambda: run_scrapers(hours=hours), {})
    results["scraping"] = {
        source: len(scraping_results.get(source, []))
        for source in ("youtube", "openai", "anthropic")
    }
    for source, detail in scraping_results.get("source_status", {}).items():
        source_status = detail.get("status", "unknown")
        results["stage_status"][f"scraping.{source}"] = {
            "status": source_status,
            "fetched": detail.get("fetched", 0),
            "persisted": detail.get("persisted", 0),
            "error_count": len(detail.get("errors", [])),
        }
        for item in detail.get("errors", []):
            results["errors"].append({
                "stage": f"scraping.{source}.{item.get('stage', 'unknown')}",
                "error_type": item.get("error_type", "Unknown"),
                "message": item.get("message", "Source failed"),
            })
    logger.info("Scraped counts: %s", results["scraping"])

    logger.info("[2/5] Processing Anthropic markdown...")
    anthropic_result = _run_stage(
        results, "anthropic_markdown", process_anthropic_markdown,
        {"total": 0, "processed": 0, "failed": 1},
    )
    results["processing"]["anthropic"] = anthropic_result
    _record_item_failures(results, "anthropic_markdown", anthropic_result)

    logger.info("[3/5] Processing YouTube transcripts...")
    youtube_result = _run_stage(
        results, "youtube_transcripts", process_youtube_transcripts,
        {"total": 0, "processed": 0, "unavailable": 0, "failed": 1},
    )
    results["processing"]["youtube"] = youtube_result
    _record_item_failures(results, "youtube_transcripts", youtube_result)

    logger.info("[4/5] Creating digests...")
    digest_result = _run_stage(
        results, "digests", process_digests,
        {"total": 0, "processed": 0, "failed": 1},
    )
    results["digests"] = digest_result
    _record_item_failures(results, "digests", digest_result)

    logger.info("[5/5] Generating and sending email digest...")
    email_result = _run_stage(
        results, "email", lambda: send_digest_email(hours=hours, top_n=top_n),
        {"success": False, "status": "failed", "error": "Email stage did not return a result"},
    )
    email_stage_threw = results["stage_status"].get("email", {}).get("status") == "failed"
    results["email"] = email_result
    results["stage_status"]["email"] = {
        "status": "success" if email_result.get("success") else "failed",
    }
    if not email_result.get("success") and not email_stage_threw:
        # A thrown exception is already captured by _run_stage. Only add this
        # error here when email delivery returned an unsuccessful result.
        results["errors"].append({
            "stage": "email",
            "error_type": email_result.get("error_type", "EmailDeliveryFailure"),
            "message": email_result.get("error", "Email delivery failed"),
        })

    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    results["end_time"] = end_time.isoformat()
    results["duration_seconds"] = duration
    results["success"] = bool(email_result.get("success")) and not results["errors"]
    results["status"] = (
        "success" if results["success"]
        else "partial_success" if email_result.get("success")
        else "failed"
    )

    logger.info("=" * 60)
    logger.info("Pipeline Summary")
    logger.info("=" * 60)
    logger.info("Status: %s", results["status"])
    logger.info("Duration: %.1f seconds", duration)
    logger.info("Scraped: %s", results["scraping"])
    logger.info("Processing: %s", results["processing"])
    logger.info("Digests: %s", results["digests"])
    logger.info("Email: %s", email_result.get("status", "failed"))
    logger.info("Error count: %d", len(results["errors"]))
    for error in results["errors"]:
        logger.error(
            "stage=%s error_type=%s message=%s",
            error["stage"], error["error_type"], error["message"],
        )
    logger.info("=" * 60)
    return results


if __name__ == "__main__":
    result = run_daily_pipeline(hours=24, top_n=10)
    raise SystemExit(0 if result["success"] else 1)
