"""Setup configuration for Steer LLM SDK."""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="steer-llm-sdk",
    version="0.1.0",
    author="Max Rossi",
    author_email="maxrossi2002@hotmail.co.uk",
    description="Multi-provider LLM integration SDK with normalization and validation",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/steer-ai/steer-llm-sdk",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: Other/Proprietary License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
    python_requires=">=3.10",
    install_requires=[
        "pydantic>=2.0.0",
        "openai>=1.0.0",
        "anthropic>=0.18.0",
        "xai-sdk>=1.0.0rc1",
        "jinja2>=3.0.0",
        "fastapi>=0.100.0",
        "httpx>=0.24.0",
        "python-dotenv>=1.0.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-asyncio>=0.21.0",
            "pytest-cov>=4.0.0",
            "black>=23.0.0",
            "ruff>=0.1.0",
        ]
    },
    entry_points={
        "console_scripts": [
            "steer-llm=steer_llm_sdk.cli:main",
        ],
    },
)
