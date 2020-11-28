import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

# Grab the version number without importing cygnet.
exec(open('cygnet/_version.py').read())

setuptools.setup(
    name="cygnet",
    version=__version__,
    author="Jonathan Yong",
    author_email="yongrenjie@gmail.com",
    description="Minimalistic command-line reference manager",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yongrenjie/cygnet",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    # Requirements
    python_requires='>=3.7',
    install_requires=[
        "prompt_toolkit",
        "aiohttp",
        "unidecode",
        "pyyaml"
    ],
    # Entry points (command-line)
    entry_points = {
        'console_scripts': ['cygnet=cygnet.startup:main',
                            'cygnet-cite=cygnet:cite_entrypoint'],
    }
)
