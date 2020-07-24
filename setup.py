import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="peeplatex",
    version="0.0.1",
    author="Jonathan Yong",
    author_email="yongrenjie@gmail.com",
    description="Minimalistic command-line reference manager",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yongrenjie/peeplatex",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    # Requirements
    python_requires='>=3.7',
    requires=[
        "prompt_toolkit",
        "aiohttp",
        "unidecode",
        "pyyaml"
    ],
    # Entry points (command-line)
    entry_points = {
        'console_scripts': ['peep=peeplatex.main:main'],
    }
)
