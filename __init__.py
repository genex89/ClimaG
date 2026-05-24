import logging
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry

DOMAIN = "climag"
PLATFORMS = ["climate", "number", "select"]

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Configura ClimaG partendo da una Config Entry."""
    hass.data.setdefault(DOMAIN, {})

    # Registra il listener che intercetta le modifiche quando premi "Configura"
    entry_async_on_unload = entry.add_update_listener(async_reload_entry)
    hass.data[DOMAIN][entry.entry_id] = entry_async_on_unload

    # Inizializza le piattaforme (climate, number, select)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Scarica una Config Entry in sicurezza."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        # Rimuove il listener per evitare leak di memoria
        update_listener = hass.data[DOMAIN].pop(entry.entry_id)
        update_listener()
    return unload_ok

async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Ricarica l'integrazione quando i dati vengono modificati nella UI."""
    _LOGGER.info("Configurazione ClimaG modificata via UI. Ricaricamento dell'integrazione...")
    await hass.config_entries.async_reload(entry.entry_id)