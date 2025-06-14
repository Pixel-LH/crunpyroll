import setuptools

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setuptools.setup(
    name="crunpyroll",
    version="2.4.7.5",
    author="stefanodvx",
    author_email="pp.stefanodvx@gmail.com",
    description="Async API wrapper for Crunchyroll",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/Pixel-LH/crunpyroll.git",
    project_urls={
        "Tracker": "https://github.com/Pixel-LH/crunpyroll/issues",
    },
    install_requires=["httpx", "xmltodict"],
    packages=setuptools.find_packages(),
    python_requires=">=3.7",
)
