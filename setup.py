from setuptools import setup, find_packages
import os


here = os.path.abspath(os.path.dirname(__file__))
README = 'SUNET haproxy status'
CHANGES = ''
try:
    README = open(os.path.join(here, 'README.rst')).read()
except IOError:
    pass
try:
    CHANGES = open(os.path.join(here, 'CHANGES.rst')).read()
except IOError:
    pass

version = '0.0.3'

install_requires = [x for x in open(os.path.join(here, 'requirements.txt')).read().split('\n') if len(x) > 0]
testing_extras = [x for x in open(os.path.join(here, 'test_requirements.txt')).read().split('\n')
                  if len(x) > 0 and not x.startswith('-')]

setup(
    name='haproxy_status',
    version=version,
    description='SUNET haproxy status page',
    long_description=README + '\n\n' + CHANGES,
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
        'testing': testing_extras,
    },
    test_suite='haproxy_status',
    entry_points={
        },
)
