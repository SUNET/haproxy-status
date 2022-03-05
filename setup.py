import os
from pathlib import PurePath
from typing import List

from setuptools import find_packages, setup


def load_requirements(path: PurePath) -> List[str]:
    """ Load dependencies from a requirements.txt style file, ignoring comments etc. """
    res = []
    with open(path) as fd:
        for line in fd.readlines():
            while line.endswith('\n') or line.endswith('\\'):
                line = line[:-1]
            line = line.strip()
            if not line or line.startswith('-') or line.startswith('#'):
                continue
            res += [line]
    return res

version = '0.0.4'

here = PurePath(__file__)

install_requires = load_requirements(here.with_name('requirements.txt'))
test_requires = load_requirements(here.with_name('test_requirements.txt'))

README = 'SUNET haproxy status'
try:
    README = open(os.path.join(here, 'README.rst')).read()
except IOError:
    pass

setup(
    name='haproxy_status',
    version=version,
    description='SUNET haproxy status page',
    long_description=README,
    # TODO: add classifiers
    classifiers=[
        # Get strings from http://pypi.python.org/pypi?%3Aaction=list_classifiers
    ],
    keywords='',
    author='SUNET',
    url='https://github.com/SUNET/haproxy-status',
    license='BSD',
    packages=find_packages('src'),
    package_dir = {'': 'src'},
    include_package_data=True,
    zip_safe=False,
    install_requires=install_requires,
    extras_require={
        'testing': test_requires,
    },
    test_suite='haproxy_status',
    entry_points={
        },
)
