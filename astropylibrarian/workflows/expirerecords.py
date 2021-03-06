# Licensed under a 3-clause BSD style license - see LICENSE.rst
"""Workflow for deleting old records."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from astropylibrarian.algolia.client import escape_facet_value

if TYPE_CHECKING:
    from typing import List

    from astropylibrarian.algolia.client import AlgoliaIndexType

__all__ = ["expire_old_records"]

logger = logging.getLogger(__name__)


async def expire_old_records(
    *, algolia_index: AlgoliaIndexType, root_url: str, index_epoch: str
) -> List[str]:
    """Expire records for a root_url that do not match the index_epoch."""
    filters = (
        f"root_url:{escape_facet_value(root_url)}"
        " AND NOT "
        f"root_url:{escape_facet_value(root_url)}"
    )
    search_settings = {
        "filters": filters,
        "attributesToRetrieve": ["root_url", "index_epoch"],
        "attributesToHighlight": [],
    }
    old_object_ids: List[str] = []
    async for r in algolia_index.browse_objects_async(search_settings):
        # Double check that we're deleting the right things.
        if r["root_url"] != root_url:
            logger.warning("root_url does not match: %s", r["baseUrl"])
            continue
        if r["surrogateKey"] == index_epoch:
            logger.warning(
                "index_epoch matches current epoch: %s", r["index_epoch"]
            )
            continue
        old_object_ids.append(r["objectID"])

    logger.info(
        "Collected %d old objectIDs for deletion, for %s",
        len(old_object_ids),
        root_url,
    )

    await algolia_index.delete_objects_async(old_object_ids)

    logger.info("Finished deleting expired objects for %s", root_url)

    return old_object_ids
