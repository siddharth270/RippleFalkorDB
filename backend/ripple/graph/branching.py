"""Isolated GRAPH.COPY snapshots; never a physics simulator."""

import time
from contextlib import contextmanager
from uuid import uuid4

from falkordb import Graph
from redis.exceptions import ResponseError


@contextmanager
def snapshot(source: Graph):
    name = f"{source.name}__branch__{uuid4().hex}"
    for attempt in range(6):
        try:
            copied = source.copy(name)
            break
        except ResponseError as error:
            if "could not fork" not in str(error) or attempt == 5:
                raise
            # Redis permits only one module fork at a time. Brief bounded retry
            # handles another process copying a graph; never substitute a fake copy.
            time.sleep(0.05 * 2**attempt)
    try:
        yield copied
    finally:
        copied.delete()
