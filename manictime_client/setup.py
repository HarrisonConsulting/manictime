from setuptools import setup, find_packages

setup(
    name="manictime-client",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "requests",
        "requests-ntlm",
        "python-dotenv",
        "backoff"
    ],
)