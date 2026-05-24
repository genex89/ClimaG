import logging
from homeassistant.components.select import SelectEntity
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.config_entries import ConfigEntry

_LOGGER = logging.getLogger(__name__)

DOMAIN = "climag"

async def async_setup_entry(
    hass: HomeAssistant, 
    config_entry: ConfigEntry, 
    async_add_entities: AddEntitiesCallback
) -> None:
    """Configura l'entità select partendo dal flusso di configurazione."""
    name = config_entry.data["name"]
    async_add_entities([ClimagModeSelect(hass, name, config_entry.entry_id)])

class ClimagModeSelect(SelectEntity, RestoreEntity):
    """Rappresenta il selettore di modalità globale per il sistema ClimaG."""

    def __init__(self, hass: HomeAssistant, master_name: str, entry_id: str) -> None:
        """Inizializza l'entità e assegna correttamente l'istanza hass."""
        self.hass = hass  # <-- FONDAMENTALE: Risolve il crash di self.hass mancante
        
        # Generazione dello slug coerente con climate.py per forzare l'entity_id corretto
        self._slug = master_name.lower().replace(" ", "_")
        self.entity_id = f"select.{self._slug}_climag_mode"
        
        self._attr_name = f"{master_name} - ClimaG Mode"
        self._attr_unique_id = f"climag_{entry_id}_mode"
        self._attr_options = ["off", "heat", "cool", "fan_only"]
        self._attr_icon = "mdi:thermostat-cog"
        self._attr_current_option = "off"

    async def async_added_to_hass(self) -> None:
        """Ripristina correttamente lo stato precedente al riavvio."""
        await super().async_added_to_hass()
        if (last_state := await self.async_get_last_state()) is not None:
            if last_state.state in self._attr_options:
                self._attr_current_option = last_state.state
                self.async_write_ha_state()
        _LOGGER.info("Selettore ClimaG Mode registrato con entity_id: %s", self.entity_id)

    @property
    def current_option(self) -> str:
        """Ritorna l'opzione attualmente selezionata."""
        return self._attr_current_option

    async def async_select_option(self, option: str) -> None:
        """Metodo asincrono nativo corretto richiesto da Home Assistant."""
        if option not in self._attr_options:
            _LOGGER.error("Opzione non valida richiesta: %s", option)
            return

        _LOGGER.info("Cambio opzione ClimaG Mode rilevato: %s", option)
        self._attr_current_option = option
        
        # Scrittura immediata, reattiva e sicura dello stato nell'event loop principale
        self.async_write_ha_state()
        
        # Ora self.hass è definito e l'evento viene generato sul bus senza errori
        self.hass.bus.async_fire("climag_mode_changed", {"mode": option})
