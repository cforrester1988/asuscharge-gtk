# type: ignore
from setuptools import find_packages, setup
from asuscharge_gtk import __version__ as version

with open("README.md", "r") as fh:
    long_description = fh.read()

setup(
    name="asuscharge-gtk",
    version=version,
    description="Set your recent ASUS notebook's maximum charge level on Linux, with a GTK GUI.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/cforrester1988/asuscharge-gtk",
    author="Christopher Forrester",
    author_email="christopher@cforrester.ca",
    license="GPLv3+",
    classifiers=[
        "Environment :: Console",
        "Intended Audience :: End Users/Desktop",
        "License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)",
        "Natural Language :: English",
        "Operating System :: POSIX :: Linux",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Topic :: Utilities",
    ],
    packages=find_packages(exclude=("tests",)),
    include_package_data=True,
    python_requires=">=3.7",
)
