# Copyright 2021 joakimnyman
# See LICENSE file for licensing details.

import unittest

from ops.testing import Harness
from charm import SubCephMonCharm


class TestCharm(unittest.TestCase):
    def test_config_changed(self):
        harness = Harness(SubCephMonCharm)
        self.addCleanup(harness.cleanup)
        harness.begin()
        self.assertEqual(harness.charm._stored.rados_gw, {'hostname': '', 'port': ''})
        harness.update_config()
        self.assertEqual(harness.charm._stored.rados_gw, {'hostname': '', 'port': ''})
