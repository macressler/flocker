# Copyright ClusterHQ Inc.  See LICENSE file for details.

"""
Tests for ``flocker.node.agents.loopback``.
"""
from functools import partial
from uuid import uuid4

from ..loopback import (
    LOOPBACK_ALLOCATION_UNIT,
    LOOPBACK_MINIMUM_ALLOCATABLE_SIZE
)
from ..testtools import (
    loopbackblockdeviceapi_for_test,
    make_iblockdeviceapi_tests,
)


class LoopbackBlockDeviceAPITests(
        make_iblockdeviceapi_tests(
            blockdevice_api_factory=partial(
                loopbackblockdeviceapi_for_test,
                allocation_unit=LOOPBACK_ALLOCATION_UNIT
            ),
            minimum_allocatable_size=LOOPBACK_MINIMUM_ALLOCATABLE_SIZE,
            device_allocation_unit=None,
            unknown_blockdevice_id_factory=lambda test: unicode(uuid4()),
        )
):
    """
    Interface adherence Tests for ``LoopbackBlockDeviceAPI``.
    """
