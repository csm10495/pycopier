from setuptools import setup
import os
import sys

THIS_FOLDER = os.path.abspath(os.path.dirname(__file__))

def getVersion():
    with open(os.path.join(THIS_FOLDER, 'pycopier', 'pycopier.py'), 'r') as f:
        text = f.read()

    for line in text.splitlines():
        if line.startswith('__version__'):
            version = line.split('=', 1)[1].replace('\'', '').replace('"', '')
            return version.strip()

    raise EnvironmentError("Unable to find __version__!")

setup(
    name='pycopier',
    author='csm10495',
    author_email='csm10495@gmail.com',
    url='http://github.com/csm10495/pycopier',
    version=getVersion(),
    packages=['pycopier'],
    license='MIT License',
    python_requires='>=2.7,!=3.0.*,!=3.1.*,!=3.2.*,!=3.3.*,!=3.4.*',
    long_description=open('README.md').read(),
    long_description_content_type="text/markdown",
    classifiers=[
        'Intended Audience :: Developers',
        'Natural Language :: English',
        'Operating System :: POSIX',
        'Operating System :: Microsoft :: Windows',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
    ],
    include_package_data = True,
    install_requires=['scandir', 'humanize', 'pytest'] + (['contextlib2'] if sys.version_info.major == 2 else []),
    entry_points={
        'console_scripts': [
            'pycopier = pycopier.__main__:main',
        ]
    },
)