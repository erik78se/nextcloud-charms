#!/usr/bin/env python3
# Copyright 2020 Erik Lönroth
# See LICENSE file for licensing details.

import logging
import subprocess
import sys
import os
import socket
from pathlib import Path
from jinja2 import Environment, FileSystemLoader
import json

from ops.charm import CharmBase
from ops.main import main
from ops.framework import StoredState
from ops.lib import use
from io import BytesIO


from ops.model import (
    ActiveStatus,
    BlockedStatus,
    MaintenanceStatus,
    WaitingStatus
)



from utils import open_port, occ_add_trusted_domain
from interface_http import HttpProvider
import interface_redis

logger = logging.getLogger(__name__)

# POSTGRESQL interface documentation
# https://github.com/canonical/ops-lib-pgsql
pgsql = use("pgsql", 1, "postgresql-charmers@lists.launchpad.net")

NEXTCLOUD_CONFIG_PHP = '/var/www/nextcloud/config/config.php'


class NextcloudCharm(CharmBase):
    _stored = StoredState()

    def __init__(self, *args):
        super().__init__(*args)
        self.db = pgsql.PostgreSQLClient(self, 'db')  # 'db' relation in metadata.yaml

        # The website provider takes care of incoming relations on the http interface.
        self.website = HttpProvider(self, 'website', socket.getfqdn(), 80)

        self._stored.set_default(data_dir='/var/www/nextcloud/data/',
                                 nextcloud_fetched=False,
                                 nextcloud_initialized=False,
                                 database_available=False,
                                 apache_configured=False,
                                 php_configured=False)

        self._stored.set_default(db_conn_str=None, db_uri=None, db_ro_uris=[])

        event_bindings = {
            self.on.install: self._on_install,
            self.on.config_changed: self._on_config_changed,
            self.on.start: self._on_start,
            self.db.on.database_relation_joined: self._on_database_relation_joined,
            self.db.on.master_changed: self._on_master_changed,
            self.on.update_status: self._on_update_status
        }

        ### REDIS

        self._stored.set_default(redis_info=dict())

        self._redis = interface_redis.RedisClient(self, "redis")

        self.framework.observe(self._redis.on.redis_available, self._on_redis_available)

        for event, handler in event_bindings.items():
            self.framework.observe(event, handler)

        action_bindings = {
            self.on.add_trusted_domain_action: self._on_add_trusted_domain_action,
            self.on.add_missing_indices_action: self._on_add_missing_indices_action,
            self.on.convert_filecache_bigint_action: self._on_convert_filecache_bigint_action,
            self.on.maintenance_action: self._on_maintenance_action
        }

        for action, handler in action_bindings.items():
            self.framework.observe(action, handler)

        ### CLUSTER RELATION
        self.framework.observe(self.on.cluster_relation_changed, self._on_cluster_relation_changed)

        self.framework.observe(self.on.cluster_relation_joined, self._on_cluster_relation_joined)
        
        self.framework.observe(self.on.cluster_relation_departed, self._on_cluster_relation_departed)

    def _on_install(self, event):
        # self._handle_storage()

        self._install_deps()

        if not self._stored.nextcloud_fetched:
            # Fetch nextcloud to /var/www/
            self._fetch_nextcloud()

    def _on_config_changed(self, event):
        """
        Any configuration change trigger a complete reconfigure of
        the php and apache and also a restart of apache.
        :param event:
        :return:
        """
        self._config_apache2()

        self._config_php()

        # self._config_website()

        subprocess.check_call(['systemctl', 'restart', 'apache2.service'])

        self._on_update_status(event)

    def _on_database_relation_joined(self, event: pgsql.DatabaseRelationJoinedEvent):
        if self.model.unit.is_leader():
            # Provide requirements to the PostgreSQL server.
            event.database = 'nextcloud'  # Request database named mydbname
            event.extensions = ['citext']  # Request the citext extension installed
        elif event.database != 'nextcloud':
            # Leader has not yet set requirements. Defer, incase this unit
            # becomes leader and needs to perform that operation.
            event.defer()
            return

    def _on_cluster_relation_joined(self, event):
        logging.debug("!!!!!!!!cluster relation joined!!!!!!!!")
        self.framework.breakpoint('joined')
        logging.debug("Welcome {} to the cluster, data: {}".format(event.unit.name, event.relation.data[event.unit]))

    def _on_cluster_relation_changed(self, event):
        logging.debug("!!!!!!!!cluster relation changed!!!!!!!!")
        self.framework.breakpoint('changed')
    
    def _on_cluster_relation_departed(self, event):
        logging.debug("!!!!!!!!cluster relation departed!!!!!!!!")
        self.framework.breakpoint('departed')
        logging.debug("Unit {} left the cluster :(".format(event.unit.name))

    def _on_master_changed(self, event: pgsql.MasterChangedEvent):
        if event.database != 'nextcloud':
            # Leader has not yet set requirements. Wait until next event,
            # or risk connecting to an incorrect database.
            return

        # The connection to the primary database has been created,
        # changed or removed. More specific events are available, but
        # most charms will find it easier to just handle the Changed
        # events. event.master is None if the master database is not
        # available, or a pgsql.ConnectionString instance.

        logger.debug("=== Database master_changed event ===")

        self._stored.db_conn_str = None if event.master is None else event.master.conn_str
        self._stored.db_uri = None if event.master is None else event.master.uri
        self._stored.dbname = None if event.master is None else event.master.dbname
        self._stored.dbuser = None if event.master is None else event.master.user
        self._stored.dbpass = None if event.master is None else event.master.password
        self._stored.dbhost = None if event.master is None else event.master.host
        self._stored.dbport = None if event.master is None else event.master.port
        self._stored.dbtype = None if event.master is None else 'pgsql'

        if event.master and event.database == 'nextcloud':

            self._stored.database_available = True

            if not self._stored.nextcloud_initialized:

                self._set_directory_permissions()

                self._init_nextcloud()

                self._add_initial_trusted_domain()

                installed = self.get_nextcloud_status()['installed']

                if installed:

                    logger.debug("===== Nextcloud install_status: {}====".format(installed))

                    self._stored.nextcloud_initialized = True

    def _on_start(self, event):

        if not self._stored.nextcloud_initialized:

            event.defer()

            return

        try:

            subprocess.check_call(['systemctl', 'restart', 'apache2.service'])

            self._on_update_status(event)

            open_port('80')

        except subprocess.CalledProcessError as e:

            print(e)

            sys.exit(-1)

    # ACTIONS

    def _on_add_trusted_domain_action(self, event):
        pass

    def _on_add_missing_indices_action(self, event):
        pass

    def _on_add_missing_indices_action(self, event):
        pass

    def _on_convert_filecache_bigint_action(self, event):
        pass

    def _on_maintenance_action(self, event):
        """
        Action to take the site in or out of maintenance mode.
        :param event:
        :return:
        """
        try:
            hostname = subprocess.check_output(
                "hostname",
                shell=True
            )

            event.set_results({"maintenence": hostname})

        except subprocess.CalledProcessError as e:
            print(e)
            sys.exit(-1)

    def _install_deps(self):
        """
        Install dependencies for running nextcloud.
        """
        self.unit.status = MaintenanceStatus("Begin installing dependencies...")

        try:
            packages = ['apache2',
                        'libapache2-mod-php7.2',
                        'php7.2-gd',
                        'php7.2-json',
                        'php7.2-mysql',
                        'php7.2-pgsql',
                        'php7.2-curl',
                        'php7.2-mbstring',
                        'php7.2-intl',
                        'php-imagick',
                        'php7.2-zip',
                        'php7.2-xml',
                        'php-apcu',
                        'php-redis',
                        'php-smbclient']

            command = ["apt", "install", "-y"]

            command.extend(packages)

            subprocess.run(command, check=True)

            self.unit.status = MaintenanceStatus("Dependencies installed")

        except subprocess.CalledProcessError as e:
            print(e)
            sys.exit(-1)

    def _fetch_nextcloud(self):
        """
        Fetch and Install nextcloud from internet
        Sources are about 100M.
        """
        self.unit.status = MaintenanceStatus("Begin fetching sources.")

        import requests
        import tarfile

        source = 'https://download.nextcloud.com/server/releases/nextcloud-18.0.3.tar.bz2'

        checksum = '7b67e709006230f90f95727f9fa92e8c73a9e93458b22103293120f9cb50fd72'

        try:

            response = requests.get(source, allow_redirects=True, stream=True)

            dst = Path('/var/www/')

            with tarfile.open(fileobj=BytesIO(response.content), mode='r:bz2') as tfile:
                tfile.extractall(path=dst)

            self.unit.status = MaintenanceStatus("Sources installed")

            self._stored.nextcloud_fetched = True

        except subprocess.CalledProcessError as e:
            print(e)
            sys.exit(-1)

    def _handle_storage(self):
        """ 

        Handles juju storage, using 'location' in metadata.yaml if provided on deploy.

        """
        pass  # not implemented
        self.unit.status = MaintenanceStatus("Begin handle storage...")

        data_dir = unitdata.kv().get("nextcloud.storage.data.mount")

        if os.path.exists(str(data_dir)):
            # Use non default for nextcloud

            logger.debug("nextcloud storage location for data set as: {}".format(data_dir))

            host.chownr(data_dir, "www-data", "www-data", follow_links=False, chowntopdir=True)

            os.chmod(data_dir, 0o700)

        else:
            # If no custom data_dir get to us via storage, we use the default
            data_dir = '/var/www/nextcloud/data'

    def _config_php(self):
        """
        Renders the phpmodule for nextcloud (nextcloud.ini)
        This is instead of manipulating the system wide php.ini
        which might be overwitten or changed from elsewhere.
        """
        self.unit.status = MaintenanceStatus("Begin config php.")

        phpmod_context = {
            'max_file_uploads': self.config.get('php_max_file_uploads'),
            'upload_max_filesize': self.config.get('php_upload_max_filesize'),
            'post_max_size': self.config.get('php_post_max_size'),
            'memory_limit': self.config.get('php_memory_limit')
        }

        template = Environment(
            loader=FileSystemLoader(Path(self.charm_dir / 'templates'))).get_template('nextcloud.ini.j2')

        target = Path('/etc/php/7.2/mods-available/nextcloud.ini')

        target.write_text(template.render(phpmod_context))

        subprocess.check_call(['phpenmod', 'nextcloud'])

        self._stored.php_configured = True

        self.unit.status = MaintenanceStatus("php config complete.")

    def _init_nextcloud(self):
        """
        Initializes nextcloud via the nextcloud occ interface.
        :return:
        """
        self.unit.status = MaintenanceStatus("Begin initializing nextcloud...")

        ctx = {'dbtype': self._stored.dbtype,
               'dbname': self._stored.dbname,
               'dbhost': self._stored.dbhost,
               'dbpass': self._stored.dbpass,
               'dbuser': self._stored.dbuser,
               'adminpassword': self.config.get('admin-password'),
               'adminusername': self.config.get('admin-username'),
               'datadir': '/var/www/nextcloud/data'
               }

        nextcloud_init = ("sudo -u www-data /usr/bin/php occ maintenance:install "
                          "--database {dbtype} --database-name {dbname} "
                          "--database-host {dbhost} --database-pass {dbpass} "
                          "--database-user {dbuser} --admin-user {adminusername} "
                          "--admin-pass {adminpassword} "
                          "--data-dir {datadir} ").format(**ctx)

        subprocess.call(nextcloud_init.split(), cwd='/var/www/nextcloud')

    def _add_initial_trusted_domain(self):
        """
        Adds in 2 trusted domains:
        1. ingress address.
        2. fqdn config
        :return:
        """
        ingress_addr = self.model.get_binding('website').network.ingress_address

        # Adds the ingress_address to trusted domains on index: 1
        occ_add_trusted_domain(ingress_addr, 1)

        # Adds the fqdn to trusted domains on index: 2 (if set)
        if self.config['fqdn']:
            occ_add_trusted_domain(self.config['fqdn'],2)


    def _set_directory_permissions(self):

        subprocess.call("sudo chown -R www-data:www-data /var/www/nextcloud".split(),
                        cwd='/var/www/nextcloud')

    def _patch_config(self):

        # TODO: This is wrong and will also replace other values in config.php
        # BUG - perhaps add a config here with trusted_domains.
        # self.unit.ingress_address
        Path('/var/www/nextcloud/config/config.php').write_text(
            Path('/var/www/nextcloud/config/config.php').open().read().replace(
                "localhost", self.config.get('fqdn') or "127.0.0.1"))

        self.unit.status = MaintenanceStatus("Nextcloud init complete.")

    def _config_apache2(self):
        """
        Configures apache2
        """
        self.unit.status = MaintenanceStatus("Begin config apache2.")

        template = Environment(
            loader=FileSystemLoader(Path(self.charm_dir / 'templates'))
        ).get_template('nextcloud.conf.j2')

        target = Path('/etc/apache2/sites-available/nextcloud.conf')

        ctx = {}

        target.write_text(template.render(ctx))
        # Enable required modules.
        for module in ['rewrite', 'headers', 'env', 'dir', 'mime']:
            subprocess.call(['a2enmod', module])

        # Disable default site
        subprocess.check_call(['a2dissite', '000-default'])

        # Enable nextcloud site (wich will be default)
        subprocess.check_call(['a2ensite', 'nextcloud'])

        self._stored.apache_configured = True

        self.unit.status = MaintenanceStatus("apache2 config complete.")

    def _on_update_status(self, event):
        """
        Evaluate the internal state to report on status.
        """

        if (self._stored.nextcloud_fetched and
                self._stored.nextcloud_initialized and
                self._stored.database_available and
                self._stored.apache_configured and
                self._stored.php_configured):

            self.unit.status = ActiveStatus("Ready")

            self.unit.set_workload_version(self.get_nextcloud_status()['version'])
        elif not self._stored.database_available:

            self.unit.status = BlockedStatus("No database.")

        else:

            self.unit.status = WaitingStatus("Not Ready...")

    def get_nextcloud_status(self) -> dict:
        """
        Return dict with nextcloud status.
        """
        ns = "sudo -u www-data /usr/bin/php occ status --output=json --no-warnings"

        try:
            output = subprocess.run(ns.split(),
                                    stdout=subprocess.PIPE,
                                    cwd='/var/www/nextcloud',
                                    universal_newlines=True).stdout

            returndict = json.loads(output)

            logger.debug(returndict)

        except subprocess.CalledProcessError as e:

            print(e)

            sys.exit(-1)

        return returndict

    def set_redis_info(self, info: dict):

        self._stored.redis_info = info

    def _on_redis_available(self,event):

        logger.debug("=== _on_redis_available ===")

        logger.debug(self._stored.redis_info)

        template = Environment(
            loader=FileSystemLoader(Path(self.charm_dir / 'templates'))
        ).get_template('redis.config.php.j2')

        target = Path('/var/www/nextcloud/config/redis.config.php')

        ctx = self._stored.redis_info

        target.write_text(template.render(ctx))


if __name__ == "__main__":
    main(NextcloudCharm)
