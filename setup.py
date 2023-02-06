from setuptools import setup, find_namespace_packages
from src.hightea.client import __version__

setup(
    name = "hightea-client",
    version = __version__,
    author = "Hightea Collaboration",
    author_email = "hightea@hep.phy.cam.ac.uk",
    url = "https://github.com/HighteaCollaboration/hightea-client",
    description = "Command line interface to hightea project",
    license = "MIT",
    packages=find_namespace_packages(
        where='src',
        # include=[
        #     'hightea.client.*'
        #     ]
        ),
    package_dir={
        '': 'src',
    },
    scripts=['./bin/highteacli'],
    install_requires = [
        "numpy",
        "requests",
        "urllib3",
        "pyyaml",
    ],
    python_requires = ">=3.7",
)
