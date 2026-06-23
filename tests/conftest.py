import contextlib

import pytest
from starlette.testclient import TestClient

import app.main as main_module


@pytest.fixture
def client():
    """TestClient avec le lifespan (DB, bot Twitch, Node.js...) désactivé.

    Le but de ce test de fumée est de vérifier le câblage des routes et de
    l'auth admin sans dépendre d'une vraie base Postgres ni de credentials
    Twitch/Discord en environnement CI.
    """
    app = main_module.app

    @contextlib.asynccontextmanager
    async def noop_lifespan(_app):
        yield

    app.router.lifespan_context = noop_lifespan

    with TestClient(app) as c:
        yield c
