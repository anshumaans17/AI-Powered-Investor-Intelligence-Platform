import re

from sqlalchemy import text

from database.postgres_sql import get_engine


INR_CRORE_TO_USD = 10_000_000 / 83.4128
INR_CRORE_PATTERN = re.compile(
    r"(?:₹|INR\s*)?\s*([\d,]+(?:\.\d+)?)\s*crore(?:s)?",
    re.IGNORECASE,
)
USD_VALUE_PATTERN = re.compile(
    r"\$\s*([\d,]+(?:\.\d+)?)\s*(million|billion|m|bn)?\b",
    re.IGNORECASE,
)


def _format_financial_value(value):
    """Display financial values with a readable million or billion unit."""
    if not isinstance(value, str):
        return value

    crore_match = INR_CRORE_PATTERN.search(value)
    if crore_match:
        crore_value = float(crore_match.group(1).replace(",", ""))
        usd_value = crore_value * INR_CRORE_TO_USD
    else:
        usd_match = USD_VALUE_PATTERN.search(value)
        if not usd_match:
            return value

        amount = float(usd_match.group(1).replace(",", ""))
        unit = (usd_match.group(2) or "million").lower()
        if unit in ("billion", "bn"):
            usd_value = amount * 1_000_000_000
        elif unit in ("million", "m"):
            usd_value = amount * 1_000_000
        else:
            usd_value = amount

    if usd_value >= 1_000_000_000:
        return f"${usd_value / 1_000_000_000:.1f}B"
    if usd_value >= 1_000_000:
        return f"${usd_value / 1_000_000:.1f}M"
    return f"${usd_value:,.0f}"


def get_metrics():
    engine = get_engine()

    query = """
    SELECT *
    FROM (
        SELECT *,
               ROW_NUMBER() OVER (
                   PARTITION BY company, year
                   ORDER BY created_at DESC
               ) AS rn
        FROM financial_metrics
    ) t
    WHERE rn = 1
    ORDER BY company
    """

    with engine.connect() as connection:
        result = connection.execute(text(query))
        rows = [dict(row._mapping) for row in result]

    for row in rows:
        for field in (
            "revenue",
            "net_income",
            "operating_income",
            "cash_flow",
            "total_assets",
            "total_liabilities",
        ):
            row[field] = _format_financial_value(row[field])

    return rows