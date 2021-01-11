from subprocess import run, call, PIPE
import logging

logger = logging.getLogger(__name__)


class Occ:

    @staticmethod
    def occ_add_trusted_domain(domain, index):
        """
        Adds a trusted domain to nextcloud config.php with occ
        """
        Occ.add_trusted_domain = ("sudo -u www-data php /var/www/nextcloud/occ config:system:set "
                                  "trusted_domains {index} "
                                  " --value={domain} ").format(index=index, domain=domain)
        call(Occ.add_trusted_domain.split(), cwd='/var/www/nextcloud')

    @staticmethod
    def add_trusted_domain(domain):
        """
        Adds a trusted domain to nextcloud config.php
        """
        current_domains = Occ.occ_get_trusted_domains()
        new_index = len(current_domains)
        Occ.occ_add_trusted_domain(domain, new_index)

    @staticmethod
    def occ_remove_trusted_domain(domain):
        """
        Removes a trused domain from nextcloud with occ
        """
        current_domains = Occ.occ_get_trusted_domains()
        if domain in current_domains:
            current_domains.remove(domain)
            # First delete all trusted domains from config.php
            # since they might have indices not in order.
            Occ.occ_remove_all_trusted_domains()
            if current_domains:
                # Now, add all the domains with indices in order starting from 0
                for index, domain in enumerate(current_domains):
                    Occ.occ_add_trusted_domain(domain, index)

    @staticmethod
    def occ_remove_all_trusted_domains():
        delete_trusted_domains = "sudo -u www-data php /var/www/nextcloud/occ \
                                  config:system:delete trusted_domains"
        run(delete_trusted_domains.split(), cwd='/var/www/nextcloud')

    @staticmethod
    def remove_trusted_domain(domain):
        Occ.occ_remove_trusted_domain(domain)

    @staticmethod
    def occ_get_trusted_domains():
        """
        Get all current trusted domains in config.php with occ
        return list
        """
        trusted_domains = "sudo -u www-data php /var/www/nextcloud/occ \
                           config:system:get trusted_domains"
        output = run(trusted_domains.split(), cwd='/var/www/nextcloud',
                     stdout=PIPE, universal_newlines=True)
        domains = output.stdout.split()
        return domains

    @staticmethod
    def update_trusted_domains_peer_ips(domains):
        current_domains = Occ.occ_get_trusted_domains()
        # Copy 'localhost' and fqdn but replace all peers IP:s
        # with the ones currently available in the relation.
        new_domains = current_domains[0:2] + domains[:]
        Occ.occ_remove_all_trusted_domains()
        for index, d in enumerate(new_domains):
            Occ.occ_add_trusted_domain(d, index)

    @staticmethod
    def db_add_missing_indices():
        cmd = "sudo -u www-data php /var/www/nextcloud/occ db:add-missing-indices"
        output = run(cmd.split(), cwd='/var/www/nextcloud', stdout=PIPE, universal_newlines=True)
        return output

    @staticmethod
    def convert_filecache_bigint():
        cmd = "sudo -u www-data php /var/www/nextcloud/occ \
               db:convert-filecache-bigint --no-interaction"
        output = run(cmd.split(), cwd='/var/www/nextcloud', stdout=PIPE, universal_newlines=True)
        return output

    @staticmethod
    def maintenance(enable):
        m = "--on" if enable else "--off"
        cmd = f"sudo -u www-data php /var/www/nextcloud/occ maintenance:mode {m}"
        output = run(cmd.split(), cwd='/var/www/nextcloud', stdout=PIPE, universal_newlines=True)
        return output
