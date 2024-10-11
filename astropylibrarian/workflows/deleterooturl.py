# Licensed under a 3-clause BSD style license - see LICENSE.rst
"""Workflow for deleting all Algolia records associated with a root URL."""

import logging
from typing import Any, AsyncIterator

from algoliasearch.search.models.browse_params_object import BrowseParamsObject

from astropylibrarian.algolia.client import AlgoliaIndexType, escape_facet_value

logger = logging.getLogger(__name__)


async def delete_root_url(
    *, root_url: str, algolia_index: AlgoliaIndexType
) -> list[str]:
    """Delete all Algolia records associated with a ``root_url``."""
    object_ids: list[str] = []
    async for record in search_for_records(
        algolia_index=algolia_index, root_url=root_url
    ):
        if record["root_url"] != root_url:
            logger.warning(
                "Search failure, root url of %s is %s",
                record["objectID"],
                record["root_url"],
            )
            continue
        object_ids.append(record["objectID"])

    logger.debug("Found %d objects for deletion", len(object_ids))

    responses = await algolia_index.delete_objects_async(object_ids)
    logger.debug("Algolia response:\n%s", responses)

    logger.info("Deleted %d objects", len(object_ids))

    return object_ids


async def search_for_records(
    *, algolia_index: AlgoliaIndexType, root_url: str
) -> AsyncIterator[dict[str, Any]]:
    filters = f"root_url:{escape_facet_value(root_url)}"
    logger.debug("Filter:\n%s", filters)

    obj = BrowseParamsObject(
        filters=filters, attributes_to_retrieve=["root_url"], attributes_to_highlight=[]
    )
    async for result in algolia_index.browse_objects_async(obj):
        yield result
