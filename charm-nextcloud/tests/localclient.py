import requests
import pathlib
import subprocess as sp
import tarfile
import sys
import io
import os
import shutil

def fetch_and_extract_nextcloud(tarfile_url):
    """
    Fetch and Install nextcloud from internet
    Sources are about 100M.
    """
    # tarfile_url = 'https://download.nextcloud.com/server/releases/nextcloud-18.0.3.tar.bz2'
    # checksum = '7b67e709006230f90f95727f9fa92e8c73a9e93458b22103293120f9cb50fd72'
    try:
        response = requests.get(tarfile_url, allow_redirects=True, stream=True)
        dst = pathlib.Path('/tmp/')

        print(os.path.exists("nextcloud.tar.bz2"))

        print( tarfile.is_tarfile( 'nextcloud.tar.bz2' ) )


        with tarfile.open('nextcloud.tar.bz2', mode='r:bz2') as tfile:
            print("Begin extracting tar.")
            tfile.extractall(path=dst)
            tfile.close()

    except sp.CalledProcessError as e:
        print(e)
        sys.exit(-1)



if __name__ == "__main__":
    fetch_and_extract_nextcloud('http://localhost:8081/nextcloud.tar.bz2')
