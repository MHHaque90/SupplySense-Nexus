"""Synthetic organization generator."""

from backend.app.core.data_labels import DataSourceLabel
from backend.app.data.config import GenerationConfig
from backend.app.data.generators.base import stream_rng

_SYNTHETIC_ORGS: list[tuple[str, str]] = [
    ("Nexus Retail Group", "Retail"),
    ("Nexus Components", "Manufacturing"),
    ("Nexus Distribution", "Wholesale"),
]


def generate_organizations(config: GenerationConfig) -> list[dict[str, str]]:
    """Generate clearly synthetic tenant organizations.

    Organization ``i`` always receives the same synthetic name for a
    given configuration, independent of the random seed.
    """
    rng = stream_rng(config.seed, "organizations")
    industry_pool = [industry for _, industry in _SYNTHETIC_ORGS]
    records: list[dict[str, str]] = []
    for index in range(max(1, config.organization_count)):
        if index < len(_SYNTHETIC_ORGS):
            name, industry = _SYNTHETIC_ORGS[index]
        else:
            name = f"Nexus Subsidiary {index + 1:02d}"
            industry = rng.choice(industry_pool)
        records.append(
            {
                "name": name,
                "industry": industry,
                "data_source_label": DataSourceLabel.SYNTHETIC.value,
            }
        )
    return records
