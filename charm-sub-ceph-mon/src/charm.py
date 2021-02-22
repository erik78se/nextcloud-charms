#!/usr/bin/env python3
# Copyright 2021 joakimnyman
# See LICENSE file for licensing details.

"""Charm the service."""

import logging
import subprocess as sp
import json

from ops.charm import CharmBase
from ops.main import main
from ops.framework import StoredState

logger = logging.getLogger(__name__)


class SubCephMonCharm(CharmBase):
    """Charm the service."""

    _stored = StoredState()

    def __init__(self, *args):
        super().__init__(*args)
        self.framework.observe(self.on.config_changed, self._on_config_changed)
        self.framework.observe(self.on.ceph_relation_changed, self._on_ceph_relation_changed)
        self.framework.observe(self.on.rados_gw_relation_changed, self._on_rados_gw_relation_changed)
        self._stored.set_default(rados_gw={'hostname': '', 'port': ''})

    def _on_config_changed(self, _):
        pass

    def _on_ceph_relation_changed(self, event):
        if self.model.unit.is_leader():
            if not (self._stored.rados_gw['hostname'] and self._stored.rados_gw['port']):
                event.defer()
                return
            # Create user
            self.framework.breakpoint('ceph')
            cmd = 'sudo radosgw-admin user create --uid=nextcloud --display-name=\"nextcloud\"'
            user_info = sp.run(cmd.split(' '), stdout=sp.PIPE, universal_newlines=True).stdout
            if not user_info:
                event.defer()
                return
            user_info = json.loads(user_info)
            event.relation.data[self.app]['ceph_user'] = json.dumps(user_info)
            # Create bucket
            sp.run(["sudo", "apt", "install", "-y", 'awscli'], check=True)

            # configure aws with creds from created user
            aws_env_vars = {'AWS_ACCESS_KEY_ID': user_info['keys'][0]['access_key'],
                            'AWS_SECRET_ACCESS_KEY': user_info['keys'][0]['secret_key'],
                            'AWS_DEFAULT_REGION': 'eu-north-1'}
            rados_gw_hostname = self._stored.rados_gw['hostname']
            rados_gw_port = self._stored.rados_gw['port']
            cmd = "aws --endpoint-url=http://{}:{} s3api create-bucket --bucket nextcloud".format(rados_gw_hostname, rados_gw_port)
            sp.run(cmd.split(' '), check=True, env=aws_env_vars)
            event.relation.data[self.app]['rados_gw_hostname'] = rados_gw_hostname
            event.relation.data[self.app]['rados_gw_port'] = rados_gw_port

    def _on_rados_gw_relation_changed(self, event):
        if self.model.unit.is_leader():
            self.framework.breakpoint('rados')
            self._stored.rados_gw['hostname'] = event.relation.data[event.unit].get('hostname')
            self._stored.rados_gw['port'] = event.relation.data[event.unit].get('port')


if __name__ == "__main__":
    main(SubCephMonCharm)
