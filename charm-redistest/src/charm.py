#!/usr/bin/env python3
# Copyright 2020 Erik Lönroth
# See LICENSE file for licensing details.

import logging

from ops.charm import CharmBase
from ops.main import main
from ops.framework import StoredState

from interface_redis import RedisClient

logger = logging.getLogger(__name__)


class RedistestCharm(CharmBase):
    _stored = StoredState()

    def __init__(self, *args):
        super().__init__(*args)
        self.framework.observe(self.on.config_changed, self._on_config_changed)
        self.framework.observe(self.on.fortune_action, self._on_fortune_action)

        self._stored.set_default(redis_info=dict())
        self._redis = RedisClient(self, "redis")
        self.framework.observe(self._redis.on.redis_available, self._on_redis_available)

        self._stored.set_default(things=[])

    def _on_config_changed(self, event):
        current = self.config["thing"]
        if current not in self._stored.things:
            logger.debug("found a new thing: %r", current)
            self._stored.things.append(current)

    def _on_redis_available(self, event):
        logger.debug("REDIS: {}".format( self._stored.redis_info['redis_hostname']))
        # logger.debug("REDIS: {}".format("Hello"))
        
            
    def _on_fortune_action(self, event):
        fail = event.params["fail"]
        if fail:
            event.fail(fail)
        else:
            logger.debug("REDIS: {}".format( self._stored.redis_info['redis_hostname']))
            event.set_results({"fortune": "A bug in the code is worth two in the documentation."})

    def set_redis_info(self, info: dict):
        self._stored.redis_info = info

            
if __name__ == "__main__":
    main(RedistestCharm)
