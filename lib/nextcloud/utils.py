import subprocess as sp
import sys
import requests
import tarfile
from pathlib import Path
import jinja2
import io


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
    sp.run([hook_tool, f"{port}{protocol}"])


def enable_ping():
    _modify_port(None, None, protocol='icmp', hook_tool="open-port")


def disable_ping():
    _modify_port(None, None, protocol='icmp', hook_tool="close-port")


def open_port(start, end=None, protocol="tcp"):
    _modify_port(start, end, protocol=protocol, hook_tool="open-port")


def close_port(start, end=None, protocol="tcp"):
    _modify_port(start, end, protocol=protocol, hook_tool="close-port")


def set_directory_permissions():
    sp.call("sudo chown -R www-data:www-data /var/www/nextcloud".split(),
            cwd='/var/www/nextcloud')


def install_dependencies():
    """
    Install dependencies for running nextcloud.
    """
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
        command = ["sudo", "apt", "install", "-y"]
        command.extend(packages)
        sp.run(command, check=True)
    except sp.CalledProcessError as e:
        print(e)
        sys.exit(-1)


def fetch_and_extract_nextcloud(tarfile_url):
    """
    Fetch and Install nextcloud from internet
    Sources are about 100M.
    """
    # tarfile_url = 'https://download.nextcloud.com/server/releases/nextcloud-18.0.3.tar.bz2'
    # checksum = '7b67e709006230f90f95727f9fa92e8c73a9e93458b22103293120f9cb50fd72'
    try:
        response = requests.get(tarfile_url, allow_redirects=True, stream=True)
        dst = Path('/var/www/')
        with tarfile.open(fileobj=io.BytesIO(response.content), mode='r:bz2') as tfile:
            tfile.extractall(path=dst)
    except sp.CalledProcessError as e:
        print(e)
        sys.exit(-1)


def config_apache2(templates_path, template):
    """
    Configures apache2
    """
    template = jinja2.Environment(
        loader=jinja2.FileSystemLoader(templates_path)
    ).get_template(template)
    target = Path('/etc/apache2/sites-available/nextcloud.conf')
    ctx = {}
    target.write_text(template.render(ctx))
    # Enable required modules.
    for module in ['rewrite', 'headers', 'env', 'dir', 'mime']:
        sp.call(['a2enmod', module])
    # Disable default site
    sp.check_call(['a2dissite', '000-default'])
    # Enable nextcloud site (wich will be default)
    sp.check_call(['a2ensite', 'nextcloud'])


def config_php(phpmod_context, templates_path, template):
    """
    Renders the phpmodule for nextcloud (nextcloud.ini)
    This is instead of manipulating the system wide php.ini
    which might be overwitten or changed from elsewhere.
    """
    template = jinja2.Environment(
        loader=jinja2.FileSystemLoader(templates_path)
    ).get_template(template)
    target = Path('/etc/php/7.2/mods-available/nextcloud.ini')
    target.write_text(template.render(phpmod_context))
    sp.check_call(['phpenmod', 'nextcloud'])


def config_redis(redis_info, templates_path, template):
    template = jinja2.Environment(
        loader=jinja2.FileSystemLoader(templates_path)
    ).get_template(template)
    target = Path('/var/www/nextcloud/config/redis.config.php')
    target.write_text(template.render(redis_info))
