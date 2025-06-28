"""Setup configuration for Steer LLM SDK."""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="steer-llm-sdk",
    version="0.1.0",
    author="Steer Team",
    author_email="team@steer.ai",
    description="Multi-provider LLM integration SDK with normalization and validation",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/steer-ai/steer-llm-sdk",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
    python_requires=">=3.8",
    install_requires=[
        "pydantic>=2.0.0",
        "openai>=1.0.0",
        "anthropic>=0.18.0",
        "xai-sdk>=0.0.7",
        "transformers>=4.30.0",
        "torch>=2.0.0",
        "accelerate>=0.20.0",
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
        ],
        "local": [
            "bitsandbytes>=0.41.0",  # For quantization
        ]
    },
    entry_points={
        "console_scripts": [
            "steer-llm=steer_llm_sdk.cli:main",
        ],
    },
)