import pytest

from dotenv import load_dotenv
from os import getenv

load_dotenv()

@pytest.fixture(scope="session")
def token():
    DISCORD_TOKEN = getenv("DISCORD_TOKEN")
    
    assert DISCORD_TOKEN is not None
    return DISCORD_TOKEN
