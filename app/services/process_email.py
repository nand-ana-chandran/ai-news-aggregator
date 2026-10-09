import logging
from dotenv import load_dotenv

load_dotenv()

from app.agent.email_agent import EmailAgent, RankedArticleDetail, EmailDigestResponse
from app.agent.curator_agent import CuratorAgent
from app.profiles.user_profile import USER_PROFILE
from app.database.repository import Repository
from app.services.email import send_email, digest_to_html

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def generate_email_digest(hours: int = 24, top_n: int = 10) -> EmailDigestResponse:
    curator = CuratorAgent(USER_PROFILE)
    email_agent = EmailAgent(USER_PROFILE)
    repo = Repository()

    digests = repo.get_recent_digests(hours=hours)
    total = len(digests)

    if total == 0:
        logger.warning("operation=email.generate_digest status=no_content hours=%d", hours)
        raise ValueError(f"No digests available from the last {hours} hours")

    logger.info("operation=email.rank_digests status=started count=%d", total)
    ranked_articles = curator.rank_digests(digests)

    if not ranked_articles:
        logger.error("operation=email.rank_digests status=failed count=%d", total)
        raise ValueError("Failed to rank articles")

    article_details = [
        RankedArticleDetail(
            digest_id=article.digest_id,
            rank=article.rank,
            relevance_score=article.relevance_score,
            reasoning=article.reasoning,
            title=next((digest["title"] for digest in digests if digest["id"] == article.digest_id), ""),
            summary=next((digest["summary"] for digest in digests if digest["id"] == article.digest_id), ""),
            url=next((digest["url"] for digest in digests if digest["id"] == article.digest_id), ""),
            article_type=next((digest["article_type"] for digest in digests if digest["id"] == article.digest_id), ""),
        )
        for article in ranked_articles
    ]

    email_digest = email_agent.create_email_digest_response(
        ranked_articles=article_details,
        total_ranked=len(ranked_articles),
        limit=top_n,
    )
    logger.info(
        "operation=email.generate_digest status=success ranked=%d selected=%d",
        len(ranked_articles), len(email_digest.articles),
    )
    return email_digest


def send_digest_email(hours: int = 24, top_n: int = 10) -> dict:
    """Return an explicit delivery outcome; do not retry SMTP send automatically.

    Retrying an SMTP send after an ambiguous disconnect can send duplicate emails.
    """
    try:
        result = generate_email_digest(hours=hours, top_n=top_n)
        markdown_content = result.to_markdown()
        html_content = digest_to_html(result)
        date_label = (
            result.introduction.greeting.split("for ")[-1]
            if "for " in result.introduction.greeting
            else "Today"
        )
        subject = f"Daily AI News Digest - {date_label}"

        send_email(subject=subject, body_text=markdown_content, body_html=html_content)
        logger.info(
            "operation=email.delivery status=success articles_count=%d",
            len(result.articles),
        )
        return {
            "success": True,
            "status": "sent",
            "subject": subject,
            "articles_count": len(result.articles),
            "error": None,
            "error_type": None,
        }
    except Exception as error:
        # Include SMTP, configuration, database and generation errors in the result.
        # Keep the pipeline alive so its final summary always records delivery status.
        logger.exception(
            "operation=email.delivery status=failed error_type=%s",
            type(error).__name__,
        )
        return {
            "success": False,
            "status": "failed",
            "error": str(error),
            "error_type": type(error).__name__,
        }


if __name__ == "__main__":
    result = send_digest_email(hours=24, top_n=10)
    print(result)
