from subprocess import run, call, PIPE


def _modify_port(start=None, end=None, protocol='tcp', hook_tool="open-port"):
    assert protocol in {'tcp', 'udp', 'icmp'}
    if protocol == 'icmp':
        start = None
        end = None

    if start and end:
        port = f"{start}-{end}/"
    elif start:
        port = f"{start}/"
    else:
        port = ""
    run([hook_tool, f"{port}{protocol}"])


def occ_add_trusted_domain(domain, index):
    """
    Adds a trusted domain to nextcloud config.php with occ
    """
    add_trusted_domain = ("sudo -u www-data php /var/www/nextcloud/occ config:system:set "
                        "trusted_domains {index} "
                        " --value={domain} ").format(index=index,domain=domain)
    call(add_trusted_domain.split(), cwd='/var/www/nextcloud')

def add_trusted_domain(domain):
    """
    Adds a trusted domain to nextcloud config.php
    """
    current_domains = occ_get_trusted_domains()
    new_index = len(current_domains)
    occ_add_trusted_domain(domain, new_index)

def occ_remove_trusted_domain(domain):
    """
    Removes a trused domain from nextcloud with occ
    """
    current_domains = occ_get_trusted_domains()
    if domain in current_domains:
        current_domains.remove(domain)
        # First delete all trusted domains from config.php since they might have indices not in order.
        occ_remove_all_trusted_domains()
        if current_domains:
            # Now, add all the domains with indices in order starting from 0
            for index, domain in enumerate(current_domains):
                occ_add_trusted_domain(domain, index)

def occ_remove_all_trusted_domains():
    delete_trusted_domains = "sudo -u www-data php /var/www/nextcloud/occ config:system:delete trusted_domains"
    run(delete_trusted_domains.split(), cwd='/var/www/nextcloud')

def remove_trusted_domain(domain):
    occ_remove_trusted_domain(domain)

def occ_get_trusted_domains():
    """
    Get all current trusted domains in config.php with occ
    return list
    """
    get_trusted_domain = "sudo -u www-data php /var/www/nextcloud/occ config:system:get trusted_domains"
    output = run(get_trusted_domain.split(), cwd='/var/www/nextcloud', stdout=PIPE, universal_newlines=True)
    domains = output.stdout.split()
    return domains

def update_trusted_domains_peer_ips(domains):
    current_domains = occ_get_trusted_domains()
    # Copy 'localhost' and fqdn but replace all peers IP:s with the ones currently available in the relation.
    new_domains = current_domains[0:2] + domains[:]
    occ_remove_all_trusted_domains()
    for index, d in enumerate(new_domains):
        occ_add_trusted_domain(d, index)

def enable_ping():
    _modify_port(None, None, protocol='icmp', hook_tool="open-port")


def disable_ping():
    _modify_port(None, None, protocol='icmp', hook_tool="close-port")


def open_port(start, end=None, protocol="tcp"):
    _modify_port(start, end, protocol=protocol, hook_tool="open-port")


def close_port(start, end=None, protocol="tcp"):
    _modify_port(start, end, protocol=protocol, hook_tool="close-port")
