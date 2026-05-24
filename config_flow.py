import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector

DOMAIN = "climag"

class ClimagConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Gestione del flusso di configurazione grafico iniziale per ClimaG."""
    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Primo step guidato per l'inserimento dei parametri fondamentali."""
        if user_input is not None:
            return self.async_create_entry(title=user_input["name"], data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required("name", default="ClimaG Master"): str,
                vol.Optional("outdoor_temp_sensor"): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor", device_class="temperature")
                ),
                vol.Required("target_climates"): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="climate", multiple=True)
                ),
                vol.Required("heat_pump_entity"): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="climate", multiple=False)
                ),
            })
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Abilita il flusso delle opzioni modificabili premendo 'Configura'."""
        return ClimagOptionsFlowHandler()

class ClimagOptionsFlowHandler(config_entries.OptionsFlow):
    """Gestisce le modifiche ai parametri della configurazione senza dover reinstallare."""

    async def async_step_init(self, user_input=None):
        """Mostra il modulo per modificare i parametri esistenti dell'integrazione."""
        if user_input is not None:
            # Aggiorna i dati utilizzando il riferimento interno self.config_entry
            new_data = dict(self.config_entry.data)
            new_data["outdoor_temp_sensor"] = user_input.get("outdoor_temp_sensor")
            new_data["target_climates"] = user_input.get("target_climates")
            new_data["heat_pump_entity"] = user_input.get("heat_pump_entity")
            
            if not new_data["outdoor_temp_sensor"]:
                new_data.pop("outdoor_temp_sensor", None)

            self.hass.config_entries.async_update_entry(self.config_entry, data=new_data)
            return self.async_create_entry(title="", data=user_input)

        # Recupera i valori attuali per precompilare i campi del modulo
        current_outdoor = self.config_entry.data.get("outdoor_temp_sensor")
        current_climates = self.config_entry.data.get("target_climates", [])
        current_hp = self.config_entry.data.get("heat_pump_entity")

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Optional("outdoor_temp_sensor", default=current_outdoor): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor", device_class="temperature")
                ),
                vol.Required("target_climates", default=current_climates): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="climate", multiple=True)
                ),
                vol.Required("heat_pump_entity", default=current_hp): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="climate", multiple=False)
                ),
            })
        )