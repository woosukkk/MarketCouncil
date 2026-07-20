SOURCE_COLLECTION_SCHEMA = {
    "type": "object",
    "properties": {
        "period": {"type": "string"},
        "summary": {"type": "string"},
        "coverage": {
            "type": "object",
            "properties": {
                "official": {"type": "integer", "minimum": 0},
                "news": {"type": "integer", "minimum": 0},
                "report": {"type": "integer", "minimum": 0},
                "blog": {"type": "integer", "minimum": 0},
                "youtube": {"type": "integer", "minimum": 0},
                "missing_types": {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "enum": [
                            "official",
                            "news",
                            "report",
                            "blog",
                            "youtube",
                        ],
                    },
                },
            },
            "required": [
                "official",
                "news",
                "report",
                "blog",
                "youtube",
                "missing_types",
            ],
            "additionalProperties": False,
        },
        "articles": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "source_type": {
                        "type": "string",
                        "enum": [
                            "official",
                            "news",
                            "report",
                            "blog",
                            "youtube",
                        ],
                    },
                    "sentiment": {
                        "type": "string",
                        "enum": ["positive", "negative", "neutral"],
                    },
                    "reason": {"type": "string"},
                    "source": {"type": "string"},
                    "published_date": {"type": "string"},
                    "url": {"type": "string"},
                    "language": {
                        "type": "string",
                        "enum": ["ko", "en", "other"],
                    },
                    "event_key": {"type": "string"},
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
                    "sentiment",
                    "reason",
                    "source",
                    "published_date",
                    "url",
                    "language",
                    "event_key",
                    "is_primary_source",
                    "credibility_score",
                ],
                "additionalProperties": False,
            },
        },
    },
    "required": ["period", "summary", "coverage", "articles"],
    "additionalProperties": False,
}
