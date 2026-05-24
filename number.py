from homeassistant.components.number import RestoreNumber
from homeassistant.const import UnitOfTemperature
from homeassistant.helpers.entity import EntityCategory

DOMAIN = "climag"

async def async_setup_entry(hass, config_entry, async_add_entities):
    entry_id = config_entry.entry_id
    name = config_entry.data["name"]
    
    async_add_entities([
        ClimagNumberEntity(name, "kpc", "kpc", entry_id, 2.0, 0.0, 2.0, 0.1, None, "mdi:calculator"),
        ClimagNumberEntity(name, "kpf", "kpf", entry_id, 1.0, 0.0, 2.0, 0.1, None, "mdi:calculator"),
        
        # tmf_b: Modificato range (5.0 - 24.0) e aggiornato il valore di default a 18.0 coerente con i nuovi limiti
        ClimagNumberEntity(name, "tmf_b", "Tmf-b", entry_id, 18.0, 5.0, 24.0, 0.5, UnitOfTemperature.CELSIUS, "mdi:snowflake-thermometer"),
        
        # tmc_b: Modificato range (35.0 - 70.0) e aggiornato il valore di default a 45.0 coerente con i nuovi limiti
        ClimagNumberEntity(name, "tmc_b", "Tmc-b", entry_id, 45.0, 35.0, 70.0, 0.5, UnitOfTemperature.CELSIUS, "mdi:heat-wave"),
        
        ClimagNumberEntity(name, "tmf_min", "Tmf min", entry_id, 9.0, 7.0, 24.0, 0.5, UnitOfTemperature.CELSIUS, "mdi:thermometer-low"),
        ClimagNumberEntity(name, "tmf_max", "Tmf max", entry_id, 12.0, 7.0, 24.0, 0.5, UnitOfTemperature.CELSIUS, "mdi:thermometer-high"),
        ClimagNumberEntity(name, "tmc_min", "Tmc min", entry_id, 37.0, 35.0, 70.0, 0.5, UnitOfTemperature.CELSIUS, "mdi:thermometer-low"),
        ClimagNumberEntity(name, "tmc_max", "Tmc max", entry_id, 50.0, 35.0, 70.0, 0.5, UnitOfTemperature.CELSIUS, "mdi:thermometer-high"),
        
        # Ritardi aggiornati con step=1.0 per una regolazione precisa al secondo
        ClimagNumberEntity(name, "valve_on_delay", "valve_on_delay", entry_id, 0.0, 0.0, 120.0, 1.0, "s", "mdi:timer-sand"),
        ClimagNumberEntity(name, "termo_off_delay", "termo_off_delay", entry_id, 0.0, 0.0, 120.0, 1.0, "s", "mdi:timer-sand-complete"),
        ClimagNumberEntity(name, "climag_mode_delay", "climag_mode_delay", entry_id, 0.0, 0.0, 120.0, 1.0, "s", "mdi:timer-sync"),
    ])

class ClimagNumberEntity(RestoreNumber):
    def __init__(self, master_name, key, friendly_name, entry_id, default_value, min_val, max_val, step, unit, icon):
        self._key = key
        self._attr_name = f"{master_name} - {friendly_name}"
        self._attr_unique_id = f"climag_{entry_id}_{key}"
        self._attr_native_min_value = min_val
        self._attr_native_max_value = max_val
        self._attr_native_step = step
        self._attr_native_value = default_value
        self._attr_native_unit_of_measurement = unit
        self._attr_icon = icon
        self._attr_entity_category = EntityCategory.CONFIG

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        if (last_number_data := await self.async_get_last_number_data()) is not None:
            # Controllo di sicurezza: se il vecchio stato ripristinato rispetta i nuovi intervalli lo carica, 
            # altrimenti mantiene il nuovo valore di default impostato nell'__init__
            if self._attr_native_min_value <= last_number_data.native_value <= self._attr_native_max_value:
                self._attr_native_value = last_number_data.native_value

    async def async_set_native_value(self, value: float) -> None:
        self._attr_native_value = value
        self.async_write_ha_state()
