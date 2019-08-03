from distutils.core import setup

setup(
    name='pycopier',
    author='csm10495',
    author_email='csm10495@gmail.com',
    url='http://github.com/csm10495/pycopier',
    version='1.0.0',
    packages=['pycopier'],
    license='MIT License',
    python_requires='>=2.7',
    long_description=open('README.md').read(),
    long_description_content_type="text/markdown",
    classifiers=[
        'Intended Audience :: Developers',
        'Natural Language :: English',
        'Operating System :: POSIX',
        'Operating System :: Microsoft :: Windows',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
    ],
    include_package_data = True,
    install_requires=['scandir', 'humanize', 'pytest'],
    entry_points={
        'console_scripts': [
            'pycopier = pycopier.__main__:main',
        ]
    },
)