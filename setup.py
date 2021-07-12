from setuptools import find_packages, setup

# read the contents of your README file
from os import path

this_directory = path.abspath(path.dirname(__file__))
with open(path.join(this_directory, "README.rst"), encoding="utf-8") as f:
    long_description = f.read()

setup(
    name="fjaraskupan",
    version="0.1.0",
    description="A python library for speaking to fjäråskupan",
    long_description=long_description,
    long_description_content_type="text/x-rst",
    license="MIT",
    packages=["fjaraskupan"],
    package_dir={"": "src"},
    python_requires=">=3.8",
    author="Joakim Plate",
    install_requires=["bleak"],
    extras_require={
        "tests": [
            "pytest>3.6.4",
            "pytest-mock",
            "pytest-cov",
        ]
    },
    url="https://github.com/elupus/fjaraskupan",
    classifiers=[
        "License :: OSI Approved :: MIT License",
        "Development Status :: 4 - Beta",
        "Environment :: Console",
        "Framework :: AsyncIO",
    ],
)
