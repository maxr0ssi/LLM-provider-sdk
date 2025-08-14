"""Main entry point when running as module."""

from dotenv import load_dotenv

# Load environment variables on import
load_dotenv()

from .cli import main

if __name__ == "__main__":
    main()