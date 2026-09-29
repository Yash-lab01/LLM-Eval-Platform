"""Report Service for generating executive HTML and PDF evaluation reports."""

import logging
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from backend.schemas.eval import EvalRunResult

logger = logging.getLogger(__name__)

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
_jinja_env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)), autoescape=True)


def render_html_report(run: EvalRunResult) -> str:
    """Render executive summary HTML report from Jinja2 template."""
    template = _jinja_env.get_template("eval_report.html")
    return template.render(run=run)


def generate_pdf_report(run: EvalRunResult) -> bytes | None:
    """Compile HTML evaluation report to PDF via WeasyPrint when system libraries are present."""
    html_content = render_html_report(run)
    try:
        import weasyprint  # type: ignore

        pdf_bytes = weasyprint.HTML(string=html_content).write_pdf()
        return pdf_bytes
    except Exception as exc:
        logger.debug(f"WeasyPrint PDF compilation unavailable ({exc}); fallback to HTML export")
        return None
