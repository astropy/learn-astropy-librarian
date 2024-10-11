# Licensed under a 3-clause BSD style license - see LICENSE.rst
"""Workflow for indexing a learn.astropy tutorial to Algolia."""

from __future__ import annotations

__all__ = [
    "index_tutorial_from_url",
    "index_tutorial_from_path",
    "index_tutorial",
]

import logging
from pathlib import Path
from typing import TYPE_CHECKING, List

from algoliasearch.http.exceptions import RequestException

from astropylibrarian.algolia.client import generate_index_epoch
from astropylibrarian.reducers.tutorial import get_tutorial_reducer
from astropylibrarian.resources import HtmlPage
from astropylibrarian.workflows.download import download_html
from astropylibrarian.workflows.expirerecords import expire_old_records

if TYPE_CHECKING:
    import aiohttp

    from astropylibrarian.client import AlgoliaIndexType

logger = logging.getLogger(__name__)


async def index_tutorial_from_url(
    *,
    url: str,
    http_client: aiohttp.ClientSession,
    algolia_index: AlgoliaIndexType,
    priority: int,
) -> List[str]:
    """Asynchronously save records for a tutorial located at a URL to Algolia
    (awaitable function).

    Parameters
    ----------
    url : `str`
        A URL for an HTML page.
    http_client : `aiohttp.ClientSession`
        An open aiohttp client.
    algolia_index
        Algolia index created by the
        `astropylibrarian.workflows.client.AlgoliaIndex` context manager.
    priority : int
        A priority level that elevates a tutorial in the UI's default sorting.

    Returns
    -------
    object_ids : `list` of `str`
        List of Algolia record object IDs that are saved by this indexing
        operation.

    Notes
    -----
    Operations performed by this workflow:

    1. Download the HTML page
       (`~astropylibrarian.workflows.download.download_html`)
    2. Reduce the tutorial
       (`~astropylibrarian.reducers.tutorial.ReducedTutorial`)
    3. Create records for each section
       (`~astropylibrarian.algolia.records.TutorialSectionRecord`)
    4. Save each record to Algolia (`index.save_objects
       <https://www.algolia.com/doc/api-reference/api-methods/save-objects/>`_)
    """
    tutorial_html = await download_html(url=url, http_client=http_client)
    logger.debug("Downloaded %s", url)

    return await index_tutorial(
        tutorial_html=tutorial_html,
        algolia_index=algolia_index,
        priority=priority,
    )


async def index_tutorial_from_path(
    *,
    path: Path,
    url: str,
    http_client: aiohttp.ClientSession,
    algolia_index: AlgoliaIndexType,
    priority: int,
) -> List[str]:
    """Asynchronously save records for a tutorial located at a local path to
    Algolia (awaitable function).

    Parameters
    ----------
    path : `pathlib.Path`
        The path of an HTML page.
    url : `str`
        The URL where the page is published.
    http_client : `aiohttp.ClientSession`
        An open aiohttp client.
    algolia_index
        Algolia index created by the
        `astropylibrarian.workflows.client.AlgoliaIndex` context manager.
    priority : int
        A priority level that elevates a tutorial in the UI's default sorting.

    Returns
    -------
    object_ids : `list` of `str`
        List of Algolia record object IDs that are saved by this indexing
        operation.

    Notes
    -----
    Operations performed by this workflow:

    1. Open the HTML page
    2. Reduce the tutorial
       (`~astropylibrarian.reducers.tutorial.ReducedTutorial`)
    3. Create records for each section
       (`~astropylibrarian.algolia.records.TutorialSectionRecord`)
    4. Save each record to Algolia (`index.save_objects
       <https://www.algolia.com/doc/api-reference/api-methods/save-objects/>`_)
    """
    tutorial_html = HtmlPage.from_path(path=path, url=url)
    return await index_tutorial(
        tutorial_html=tutorial_html,
        algolia_index=algolia_index,
        priority=priority,
    )


async def index_tutorial(
    *, tutorial_html: HtmlPage, algolia_index: AlgoliaIndexType, priority: int
) -> List[str]:
    """Index a tutorial given a pre-loaded HTML document.

    Parameters
    ----------
    tutorial_html : `astropylibrarian.resources.HtmlPage`
        An HTML page.
    algolia_index
        Algolia index created by the
        `astropylibrarian.workflows.client.AlgoliaIndex` context manager.
    priority : int
        A priority level that elevates a tutorial in the UI's default sorting.

    Returns
    -------
    object_ids : `list` of `str`
        List of Algolia record object IDs that are saved by this indexing
        operation.
    """
    TutorialReducer = get_tutorial_reducer(tutorial_html)
    tutorial = TutorialReducer(html_page=tutorial_html)

    index_epoch = generate_index_epoch()
    records = [
        r
        for r in tutorial.iter_algolia_objects(
            index_epoch=index_epoch, priority=priority
        )
    ]
    logger.info(
        "Indexing %d records for tutorial at %s",
        len(records),
        tutorial_html.url,
    )

    saved_object_ids: List[str] = []
    try:
        response = await algolia_index.save_objects_async(records)
    except RequestException as e:
        logger.error(
            "Error saving objects for tutorial %s:\n%s",
            tutorial_html.url,
            str(e),
        )
        return []
    for r in response.raw_responses:
        _oids = r.get("objectIDs", [])
        assert isinstance(_oids, list)
        saved_object_ids.extend(_oids)
    logger.info(
        "Finished saving %s records for tutorial at %s",
        len(saved_object_ids),
        tutorial_html.url,
    )

    if saved_object_ids:
        await expire_old_records(
            algolia_index=algolia_index,
            root_url=tutorial_html.url,
            index_epoch=index_epoch,
        )

    return saved_object_ids
