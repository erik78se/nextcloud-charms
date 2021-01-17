from setuptools import setup, find_packages

VERSION = '0.0.1' 
DESCRIPTION = 'Nextcloud utils'
LONG_DESCRIPTION = 'Libraries for nextcloud'

setup(
        name="nextcloud", 
        version=VERSION,
        author="Joakim Nyman",
        author_email="<joakim.nyman86@gmail.com>",
        description=DESCRIPTION,
        long_description=LONG_DESCRIPTION,
        packages=find_packages(),
        install_requires=[]
)
