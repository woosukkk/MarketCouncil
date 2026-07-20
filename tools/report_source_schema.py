REPORT_SOURCE_SCHEMA = {
    "type": "object",
    "properties": {
        "period": {"type": "string"},
        "summary": {"type": "string"},
        "reports": {
            "type": "array",
            "maxItems": 8,
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "source_type": {
                        "type": "string",
                        "enum": [
                            "official_report",
                            "broker_report",
                            "industry_report",
                            "research_report",
                        ],
                    },
                    "source": {"type": "string"},
                    "published_date": {"type": "string"},
                    "url": {"type": "string"},
                    "direct_pdf_url": {"type": "string"},
                    "language": {
                        "type": "string",
                        "enum": ["ko", "en", "other"],
                    },
                    "is_primary_source": {"type": "boolean"},
                    "credibility_score": {
                        "type": "number",
                        "minimum": 0.0,
                        "maximum": 1.0,
                    },
                },
                "required": [
                    "title",
                    "source_type",
                    "source",
                    "published_date",
                    "url",
                    "direct_pdf_url",
                    "language",
                    "is_primary_source",
                    "credibility_score",
                ],
                "additionalProperties": False,
            },
        },
    },
    "required": ["period", "summary", "reports"],
    "additionalProperties": False,
}
