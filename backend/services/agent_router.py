"""Agent router — selects the best agent for a given message"""
import logging
import os
import anthropic

logger = logging.getLogger(__name__)


async def route_to_agent(
    message: str,
    has_excel_source: bool = False,
    has_rag_context: bool = False,
    use_web_search: bool = False,
) -> str:
    """
    Returns agent type: 'excel' | 'research' | 'rag' | 'general'
    Falls back to 'general' on any error.
    """
    try:
        # Fast rule-based routing first (no API call needed)
        msg_lower = message.lower()

        excel_keywords = ["excel", "csv", "таблиц", "spreadsheet", "формул",
                          "столбц", "строк", "данны", "график", "chart",
                          "աղյուսակ", "ֆայլ"]
        research_keywords = ["найди", "поищи", "последние новости", "актуальн",
                              "search", "find", "latest", "news", "գтир", "փнтрир"]

        if has_excel_source and any(k in msg_lower for k in excel_keywords):
            return "excel"

        if use_web_search and any(k in msg_lower for k in research_keywords):
            return "research"

        if has_rag_context:
            return "rag"

        if use_web_search:
            return "research"

        if has_excel_source:
            return "excel"

        # Claude-based routing for ambiguous cases
        CLAUDE_API_KEY = os.environ.get('CLAUDE_API_KEY', '')
        if not CLAUDE_API_KEY:
            return "general"

        client = anthropic.AsyncAnthropic(api_key=CLAUDE_API_KEY)
        response = await client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=10,
            system="""Classify the user message into exactly one category. Reply with only the category word.
Categories:
- excel (spreadsheets, data analysis, CSV, tables, formulas)
- research (web search, current news, find information online)
- rag (questions about uploaded documents, knowledge base)
- general (everything else)""",
            messages=[{"role": "user", "content": message[:500]}]
        )

        agent_type = response.content[0].text.strip().lower()
        if agent_type not in ("excel", "research", "rag", "general"):
            return "general"
        return agent_type

    except Exception as e:
        logger.error(f"Agent router error: {e}")
        return "general"
