"""Maps a raw ARS/region name to one of the 7 map regions used by the frontend.

vagas.csv's "region" column holds the full legal name ("Administração
Regional de Saúde de Lisboa e Vale do Tejo, I.P."). The frontend map needs
a short, stable key to match clicks on the Portugal map (5 mainland ARS +
the 2 archipelagos) against filtered rows.
"""

from __future__ import annotations

import re

# canonical short key -> substring(s) that identify it in the raw region text.
REGION_KEYS: dict[str, list[str]] = {
    "norte": ["Norte"],
    "centro": ["Centro"],
    "lisboa-vale-tejo": ["Lisboa e Vale do Tejo"],
    "alentejo": ["Alentejo"],
    "algarve": ["Algarve"],
    "acores": ["Açores", "Acores", "RAA"],
    "madeira": ["Madeira", "RAM"],
}


def region_key(raw_region: str) -> str | None:
    if not raw_region:
        return None
    for key, patterns in REGION_KEYS.items():
        for pattern in patterns:
            if re.search(re.escape(pattern), raw_region, re.IGNORECASE):
                return key
    return None
