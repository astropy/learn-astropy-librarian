# Licensed under a 3-clause BSD style license - see LICENSE.rst
"""High-level interface to the Algolia Search client and a mock-client for
dry-run operations.
"""

import logging
import uuid
from copy import deepcopy
from types import TracebackType
from typing import Any, AsyncIterator, Iterator, Type, Union

from algoliasearch.search.client import SearchClient
from algoliasearch.search.models.batch_response import BatchResponse
from algoliasearch.search.models.browse_params_object import BrowseParamsObject
from algoliasearch.search.models.browse_response import BrowseResponse
from algoliasearch.search.models.deleted_at_response import DeletedAtResponse

AlgoliaIndexType = Union["AlgoliaIndex", "MockAlgoliaIndex"]
"""Type annotation alias supporting the return types of the `AlgoliaIndex` and
`MockAlgoliaIndex` context managers.
"""


class BaseAlgoliaIndex:
    """Base class for an Algolia index client.

    Parameters
    ----------
    key : str
        The Algolia API key.
    app_id : str
        The Algolia application ID.
    name : str
        Name of the Algolia index.
    """

    def __init__(self, *, key: str, app_id: str, name: str):
        self._key = key
        self._app_id = app_id
        self._index_name = name
        self._logger = logging.getLogger(__name__)

    @property
    def name(self) -> str:
        """The index's name."""
        return self._index_name

    @property
    def app_id(self) -> str:
        """The Algolia application ID."""
        return self._app_id


class AlgoliaIndex(BaseAlgoliaIndex):
    """An Algolia index client.

    This client wraps both the ``algoliasearch`` package's ``SearchClient``
    and ``index`` classes.

    Parameters
    ----------
    key : str
        The Algolia API key.
    appid : str
        The Algolia application ID.
    name : str
        Name of the Algolia index.
    """

    async def __aenter__(self) -> SearchClient:
        self._logger.debug("Opening algolia client")
        self.algolia_client = SearchClient(self.app_id, self._key)
        return self.algolia_client

    async def __aexit__(
        self,
        exc_type: Type[BaseException] | None,
        exc: Exception | None,
        tb: TracebackType | None,
    ) -> None:
        self._logger.debug("Closing algolia client")
        await self.algolia_client.close()
        self._logger.debug("Finished closing algolia client")

    async def browse_objects_async(
        self, browse_params: BrowseParamsObject
    ) -> BrowseResponse:
        return await self.algolia_client.browse_objects(
            index_name=self.name, aggregator=None, browse_params=browse_params
        )

    async def save_objects_async(
        self, objects: list[dict[str, Any]]
    ) -> list[BatchResponse]:
        return self.algolia_client.save_objects(self.name, objects)

    async def delete_objects_async(self, objectids: list[str]) -> list[BatchResponse]:
        return self.algolia_client.delete_objects(self.name, objectids)


class MockAlgoliaIndex(BaseAlgoliaIndex):
    """A mock Algolia index client.

    Use this client as a drop-in replaceemnt to `AlgoliaIndex` in situations
    where you do not want to make real network requests to Algolia, such as in
    testing or in dry-run applications.

    Parameters
    ----------
    key : str
        The Algolia API key.
    appid : str
        The Algolia application ID.
    index : str
        Name of the Algolia index.
    """

    async def __aenter__(self) -> "MockAlgoliaIndex":
        self._logger.debug("Creating mock Algolia index")
        self._saved_objects: list[dict] = []
        return self

    async def __aexit__(
        self,
        exc_type: Type[BaseException] | None,
        exc: Exception | None,
        tb: TracebackType | None,
    ) -> None:
        self._logger.debug("Closing MockAlgoliaIndex")

    async def save_objects_async(
        self,
        objects: list[dict] | Iterator[dict],
        request_options: dict[str, Any] | None = None,
    ) -> "MockMultiResponse":
        """Mock implementation of save_objects_async."""
        for obj in objects:
            self._saved_objects.append(deepcopy(obj))
        return MockMultiResponse()

    async def browse_objects_async(
        self, search_settings: dict[str, Any]
    ) -> AsyncIterator[dict[str, Any]]:
        self._logger.debug("Got search settings %s", search_settings)
        # FIXME need to flesh out this mock:
        # - provide a way to seed data
        # - use attributesToRetrieve to inform what attributes are sent back
        for _ in range(5):
            yield {}

    async def delete_objects_async(
        self, objectids: list[str]
    ) -> list[DeletedAtResponse]:
        return [DeletedAtResponse(task_id=0, deleted_at="") for _ in objectids]


class MockMultiResponse:
    """Mock of an algolia resonse."""


def escape_facet_value(value: str) -> str:
    """Escape and quote a facet value for an Algolia search."""
    value = value.replace('"', r"\"").replace("'", r"\'")
    value = f'"{value}"'
    return value


def generate_index_epoch() -> str:
    """Generate a new value for index_epoch key (a hexadecimal string
    representation of a UUID4 unique identifier.
    """
    return str(uuid.uuid4())
