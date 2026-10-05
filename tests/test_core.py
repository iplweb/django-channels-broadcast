import asyncio
import sys

import pytest
from model_bakery import baker

from channels_broadcast.core import (
    convert_obj_to_channel_name,
    force_sync,
    get_obj_from_channel_name,
)


async def _echo(wartosc):
    return wartosc


def test_force_sync_bez_petli_w_watku():
    assert force_sync(_echo, 42) == 42


def test_force_sync_z_zywa_petla_w_watku_wolajacym():
    """Typowy przypadek: kod sync wołany z wątku, w którym żyje pętla.

    Tak wygląda wątek pod sync-API Playwrighta (pętla zaparkowana w greenlecie
    przez całą sesję) oraz każdy wątek obsługujący request w ASGI.
    """

    async def main():
        return force_sync(_echo, 42)

    assert asyncio.run(main()) == 42


def test_force_sync_nie_siega_po_nest_asyncio():
    """``force_sync`` nie może modyfikować asyncio na poziomie procesu.

    Poprzednia implementacja wołała ``nest_asyncio.apply()``, gdy trafiła na
    żywą pętlę. Ta łatka jest globalna i nieodwracalna dla procesu: podmienia
    fabryki zadań i ``_run_once`` pętli. Wystarczyło, że JEDEN wywołujący
    trafił na żywą pętlę, by zatruć całą resztę procesu — u konsumenta (BPP)
    dawało to dwie różne awarie zależne od kolejności testów w workerze
    xdista: zakleszczenie ``AsyncToSync`` ↔ ``nest_asyncio._run_once`` (job
    wisiał do 25-minutowego limitu) oraz ``RuntimeError: asyncio.run() cannot
    be called from a running event loop``, gdy ``apply()`` nie dawał rady,
    a gałąź ``except`` powtarzała dokładnie to samo wywołanie.

    Dlatego mierzymy sam fakt sięgnięcia po łatkę, a nie jej skutki: skutki
    zależą od wersji Pythona i od tego, co wydarzyło się wcześniej w procesie.
    """
    sys.modules.pop("nest_asyncio", None)

    async def main():
        return force_sync(_echo, 1)

    assert asyncio.run(main()) == 1
    assert "nest_asyncio" not in sys.modules, (
        "force_sync załatał asyncio globalnie przez nest_asyncio"
    )


@pytest.mark.django_db
def test_convert_obj_to_channel_name():
    from tests.testapp.models import Thing

    obj = baker.make(Thing)
    name = convert_obj_to_channel_name(obj)
    assert name.startswith("testapp.thing-")
    assert name.endswith(str(obj.pk))


@pytest.mark.django_db
def test_get_obj_from_channel_name_roundtrip():
    from tests.testapp.models import Thing

    obj = baker.make(Thing)
    name = convert_obj_to_channel_name(obj)
    assert get_obj_from_channel_name(name) == obj
