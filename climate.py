import asyncio
import logging
from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    ClimateEntityFeature, 
    HVACMode, 
    HVACAction,
    FAN_AUTO, 
    FAN_LOW, 
    FAN_MEDIUM, 
    FAN_HIGH
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import callback
from homeassistant.helpers.event import async_track_state_change_event

_LOGGER = logging.getLogger(__name__)

DOMAIN = "climag"

async def async_setup_entry(hass, config_entry, async_add_entities):
    """Configura l'entità principale ClimaG Master partendo dai dati salvati."""
    data = config_entry.data
    async_add_entities([
        ClimagClimate(
            hass=hass,
            config_entry=config_entry,
            name=data["name"],
            outdoor_temp_sensor=data.get("outdoor_temp_sensor"), 
            target_climates=data["target_climates"],
            heat_pump_entity=data["heat_pump_entity"],
            entry_id=config_entry.entry_id
        )
    ])

class ClimagClimate(ClimateEntity):
    """Il termostato master che coordina valvole, termostati e pompa di calore."""

    def __init__(self, hass, config_entry, name, outdoor_temp_sensor, target_climates, heat_pump_entity, entry_id):
        self.hass = hass
        self.config_entry = config_entry
        self._attr_name = name
        self._outdoor_temp_sensor = outdoor_temp_sensor
        self._target_climates = target_climates
        self._heat_pump_entity = heat_pump_entity
        self._attr_unique_id = f"climag_{entry_id}"
        self._slug = name.lower().replace(" ", "_")
        
        self._select_entity_id = f"select.{self._slug}_climag_mode"
        
        self._attr_supported_features = (
            ClimateEntityFeature.TARGET_TEMPERATURE 
            | ClimateEntityFeature.TURN_ON 
            | ClimateEntityFeature.TURN_OFF
            | ClimateEntityFeature.FAN_MODE
        )
        
        self._attr_hvac_modes = [HVACMode.OFF, HVACMode.HEAT, HVACMode.COOL, HVACMode.FAN_ONLY]
        self._attr_hvac_mode = HVACMode.OFF
        self._attr_fan_modes = [FAN_AUTO, FAN_LOW, FAN_MEDIUM, FAN_HIGH]
        self._attr_fan_mode = FAN_AUTO
        self._attr_temperature_unit = UnitOfTemperature.CELSIUS
        
        self._attr_min_temp = 18.0
        self._attr_max_temp = 30.0
        self._attr_target_temperature_step = 0.5
        self._attr_target_temperature = 20.0
        
        self._valve_on_task = None
        self._termo_off_task = None
        self._mode_change_task = None
        self._master_cmd_task = None
        
        # Dizionario per tenere traccia dei task temporizzati attivi sulle singole zone
        self._zone_tasks = {}
        
        self._last_sent_tmf = None
        self._last_sent_tmc = None

        self._lock_count = 0
        
        # VARIABILE RICHIESTA: Vera per 1 secondo solo quando hvac cambia dall'interfaccia Master climate
        self._master_cmd = False

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        
        # Tracciamento dei termostati
        self.async_on_remove(
            async_track_state_change_event(self.hass, self._target_climates, self._handle_thermostat_change)
        )
        
        valve_entities = [climate_id.replace("climate.", "binary_sensor.") + "_valve" for climate_id in self._target_climates]
        self.async_on_remove(
            async_track_state_change_event(self.hass, valve_entities, self._handle_valve_change)
        )
        
        _LOGGER.info("ClimaG Master monitora il selettore associato: %s", self._select_entity_id)
        self.async_on_remove(
            async_track_state_change_event(self.hass, self._select_entity_id, self._handle_select_change)
        )

    def _get_number_value(self, key: str, default: float) -> float:
        entity_id = f"number.{self._slug}_{key}"
        state = self.hass.states.get(entity_id)
        if state and state.state not in ["unknown", "unavailable"]:
            return float(state.state)
        return default

    @property
    def ClimagMode(self) -> str:
        state = self.hass.states.get(self._select_entity_id)
        if state and state.state not in ["unknown", "unavailable"]:
            return state.state
        return "off"

    @property
    def Valve(self) -> bool:
        for climate_id in self._target_climates:
            valve_id = climate_id.replace("climate.", "binary_sensor.") + "_valve"
            state = self.hass.states.get(valve_id)
            if state and state.state == "on":
                return True
        return False

    @property
    def hvac_action(self) -> HVACAction:
        hp_state = self.hass.states.get(self._heat_pump_entity)
        if not hp_state or hp_state.state == "off":
            return HVACAction.OFF
        if hp_state.state == "heat":
            return HVACAction.HEATING
        if hp_state.state == "cool":
            return HVACAction.COOLING
        if hp_state.state == "fan_only":
            return HVACAction.FAN
        return HVACAction.IDLE

    @property
    def extra_state_attributes(self):
        return {
            "valve": self.Valve,
            "calculated_tmf": self.Tmf,
            "calculated_tmc": self.Tmc,
            "max_delta_t": self.max_delta_t,
            "climag_mode_current": self.ClimagMode,
            "lock_active": self._lock_count > 0,
            "master_cmd": self._master_cmd
        }

    @property
    def current_temperature(self) -> float:
        temperatures = []
        for climate_id in self._target_climates:
            state = self.hass.states.get(climate_id)
            if state:
                cur_temp = state.attributes.get("current_temperature")
                if cur_temp is not None:
                    try:
                        temperatures.append(float(cur_temp))
                    except (ValueError, TypeError):
                        continue
        if temperatures:
            return round(sum(temperatures) / len(temperatures), 1)
        return None

    @property
    def target_temperature(self) -> float:
        return self._attr_target_temperature

    async def async_set_temperature(self, **kwargs) -> None:
        if (temperature := kwargs.get(ATTR_TEMPERATURE)) is not None:
            self._attr_target_temperature = temperature
            self.async_write_ha_state()
            for climate_id in self._target_climates:
                await self.hass.services.async_call("climate", "set_temperature", {"entity_id": climate_id, "temperature": temperature})

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        self._attr_fan_mode = fan_mode
        self.async_write_ha_state()
        for climate_id in self._target_climates:
            try:
                await self.hass.services.async_call("climate", "set_fan_mode", {"entity_id": climate_id, "fan_mode": fan_mode})
            except Exception as err:
                _LOGGER.warning("Impossibile impostare fan_mode su %s: %s", climate_id, err)

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Intercetta i comandi diretti dall'interfaccia Master (climate.climag_master)."""
        _LOGGER.info("Interfaccia ClimaG Master: cambio modalità richiesto su %s. Attivazione master_cmd.", hvac_mode)
        
        # Attivazione della variabile master_cmd e gestione del timer di 1 secondo
        self._master_cmd = True
        if self._master_cmd_task:
            self._master_cmd_task.cancel()
        self._master_cmd_task = asyncio.create_task(self._reset_master_cmd_after_delay())

        # Esecuzione del listener interno associato all'attivazione del comando
        self._handle_master_cmd_trigger(hvac_mode)

        # Sincronizza il selettore che piloterà a cascata il resto del sistema
        await self.hass.services.async_call(
            "select", 
            "select_option", 
            {"entity_id": self._select_entity_id, "option": str(hvac_mode.value)}
        )
        self._attr_hvac_mode = hvac_mode
        self.async_write_ha_state()

    async def _reset_master_cmd_after_delay(self):
        """Task asincrono che mantiene vera la variabile master_cmd per esattamente un secondo."""
        await asyncio.sleep(1.0)
        self._master_cmd = False
        self.async_write_ha_state()
        _LOGGER.debug("master_cmd resettato a False dopo 1 secondo.")

    def _handle_master_cmd_trigger(self, target_mode: HVACMode):
        """Listener interno: se l'azione arriva dal Master e la modalità è attiva (HEAT o COOL),

        comanda tutti i termostati spenti o in ventilazione ad accendersi in modo coerente.
        """
        if str(target_mode.value) not in ["cool", "heat"]:
            return

        _LOGGER.info("Listener master_cmd: Rilevato comando da entità climate Master. Allineo i termostati in off/fan_only su %s", target_mode.value)
        for climate_id in self._target_climates:
            z_state = self.hass.states.get(climate_id)
            if z_state and z_state.state in ["off", "fan_only"]:
                _LOGGER.info("master_cmd forza accensione per zona indipendente: %s -> %s", climate_id, target_mode.value)
                self.hass.async_create_task(
                    self.hass.services.async_call("climate", "set_hvac_mode", {"entity_id": climate_id, "hvac_mode": str(target_mode.value)})
                )

    @property
    def dTf(self) -> float:
        """Calcola il massimo delta termico in modulo considerando solo i termostati in COOL o HEAT."""
        max_delta = 0.0
        for climate_id in self._target_climates:
            state = self.hass.states.get(climate_id)
            if not state or state.state not in ["cool", "heat"]:
                continue
            current_temp = state.attributes.get("current_temperature")
            target_temp = state.attributes.get("temperature")
            if current_temp is not None and target_temp is not None:
                delta = abs(float(current_temp) - float(target_temp))
                if delta > max_delta:
                    max_delta = delta
        return max_delta

    @property
    def max_delta_t(self) -> float:
        """Ritorna il delta T massimo reale (con segno: attuale - desiderata) tra i soli termostati in COOL o HEAT."""
        selected_delta = None
        for climate_id in self._target_climates:
            state = self.hass.states.get(climate_id)
            if not state or state.state not in ["cool", "heat"]:
                continue
            current_temp = state.attributes.get("current_temperature")
            target_temp = state.attributes.get("temperature")
            if current_temp is not None and target_temp is not None:
                real_delta = float(current_temp) - float(target_temp)
                if selected_delta is None or abs(real_delta) > abs(selected_delta):
                    selected_delta = real_delta
        return round(selected_delta, 2) if selected_delta is not None else 0.0

    @property
    def Tmf(self) -> float:
        tmf_b = self._get_number_value("tmf_b", 45.0)
        kpc = self._get_number_value("kpc", 2.0)
        tmf_min = self._get_number_value("tmf_min", 9.0)
        tmf_max = self._get_number_value("tmf_max", 12.0)
        return round(max(tmf_min, min(tmf_b - (kpc * self.dTf), tmf_max)), 2)

    @property
    def Tmc(self) -> float:
        tmc_b = self._get_number_value("tmc_b", 9.0)
        kpf = self._get_number_value("kpf", 1.0)
        tmc_min = self._get_number_value("tmc_min", 37.0)
        tmc_max = self._get_number_value("tmc_max", 50.0)
        return round(max(tmc_min, min(tmc_b + (kpf * self.dTf), tmc_max)), 2)

    def _check_and_update_pump_temperature(self):
        """Invia le temperature calcolate alla pompa solo se si trova nella rispettiva modalità corretta."""
        hp_state = self.hass.states.get(self._heat_pump_entity)
        if not hp_state or hp_state.state in ["unknown", "unavailable", "off"]:
            return
            
        current_hp_mode = hp_state.state
        
        if current_hp_mode == "cool" and self.Tmf != self._last_sent_tmf:
            _LOGGER.info("Ricalcolo Tmf rilevato. Invio alla pompa di calore: %s°C", self.Tmf)
            self._last_sent_tmf = self.Tmf
            self.hass.async_create_task(self.hass.services.async_call("climate", "set_temperature", {"entity_id": self._heat_pump_entity, "temperature": self.Tmf}))
            
        elif current_hp_mode == "heat" and self.Tmc != self._last_sent_tmc:
            _LOGGER.info("Ricalcolo Tmc rilevato. Invio alla pompa di calore: %s°C", self.Tmc)
            self._last_sent_tmc = self.Tmc
            self.hass.async_create_task(self.hass.services.async_call("climate", "set_temperature", {"entity_id": self._heat_pump_entity, "temperature": self.Tmc}))

    @callback
    def _handle_thermostat_change(self, event):
        """Gestisce le variazioni provenienti dalle singole stanze (stati e attributi)."""
        if self._lock_count > 0:
            return

        old_state = event.data.get("old_state")
        new_state = event.data.get("new_state")
        entity_id = event.data.get("entity_id")
        
        if not new_state:
            return

        old_mode = old_state.state if old_state else "off"
        room_mode = new_state.state
        current_climag_mode = self.ClimagMode

        old_target = old_state.attributes.get("temperature") if old_state else None
        new_target = new_state.attributes.get("temperature")
        old_current = old_state.attributes.get("current_temperature") if old_state else None
        new_current = new_state.attributes.get("current_temperature")

        is_thermal_change = (old_mode == room_mode) and ((old_target != new_target) or (old_current != new_current))

        # Se è cambiato un attributo termico, aggiorna calcoli e stato in modo reattivo immediato
        if is_thermal_change:
            self._check_and_update_pump_temperature()
            self.async_write_ha_state()
            return

        if old_mode == room_mode and not is_thermal_change:
            return

        # --- LOGICA DI CONTROLLO DELLE ZONE ---
        if entity_id in self._zone_tasks:
            self._zone_tasks[entity_id].cancel()
            del self._zone_tasks[entity_id]

        if room_mode in ["cool", "heat"]:
            if current_climag_mode == "off":
                _LOGGER.info("REGOLA 1: %s passa a %s con Master OFF. Accendo subito il selettore.", entity_id, room_mode)
                self._lock_count += 1
                try:
                    self.hass.async_create_task(
                        self.hass.services.async_call("select", "select_option", {"entity_id": self._select_entity_id, "option": room_mode})
                    )
                    self._attr_hvac_mode = HVACMode(room_mode)
                    self.async_write_ha_state()
                finally:
                    self._lock_count -= 1
            
            elif current_climag_mode != "off" and room_mode != current_climag_mode:
                if old_mode in ["off", "fan_only"]:
                    _LOGGER.info("Pianifico adeguamento di %s su %s (ClimaG Mode corrente) tra 2 secondi.", entity_id, current_climag_mode)
                    self._zone_tasks[entity_id] = asyncio.create_task(
                        self._handle_zone_delay_action(entity_id, "align", current_climag_mode)
                    )
                elif old_mode in ["cool", "heat"]:
                    _LOGGER.info("Pianifico inversione globale di ClimaG Mode su %s causata da %s tra 2 secondi.", room_mode, entity_id)
                    self._zone_tasks[entity_id] = asyncio.create_task(
                        self._handle_zone_delay_action(entity_id, "invert", room_mode)
                    )

        self._check_and_update_pump_temperature()
        
        active_zones = 0
        for cid in self._target_climates:
            c_state = self.hass.states.get(cid)
            if c_state and c_state.state in ["cool", "heat"]:
                active_zones += 1

        if active_zones == 0 and current_climag_mode != "off" and self._lock_count == 0:
            _LOGGER.info("Tutte le zone sono spente. Spengo il sistema ClimaG Master ed avvio timer spegnimento pompa.")
            self._lock_count += 1
            try:
                self.hass.async_create_task(
                    self.hass.services.async_call("select", "select_option", {"entity_id": self._select_entity_id, "option": "off"})
                )
                self._attr_hvac_mode = HVACMode.OFF
                self.async_write_ha_state()
                
                # Innesca il timer quando lo spegnimento è causato dall'azzeramento delle zone operative
                if not self._termo_off_task:
                    if self._valve_on_task:
                        self._valve_on_task.cancel()
                        self._valve_on_task = None
                    self._termo_off_task = asyncio.create_task(self._handle_termo_off_delay())
            finally:
                self._lock_count -= 1
        else:
            self.async_write_ha_state()

    async def _handle_zone_delay_action(self, entity_id, action_type, target_mode):
        await asyncio.sleep(2.0)
        self._lock_count += 1
        try:
            if action_type == "align":
                _LOGGER.info("Scaduti 2s. Forzo l'allineamento di %s su ClimaG Mode: %s", entity_id, target_mode)
                await self.hass.services.async_call("climate", "set_hvac_mode", {"entity_id": entity_id, "hvac_mode": target_mode})
            elif action_type == "invert":
                current_room_state = self.hass.states.get(entity_id)
                if current_room_state and current_room_state.state == target_mode:
                    _LOGGER.info("Scaduti 2s. L'inversione su %s è confermata. Cambio ClimaG Mode generale su: %s", entity_id, target_mode)
                    await self.hass.services.async_call("select", "select_option", {"entity_id": self._select_entity_id, "option": target_mode})
                    self._attr_hvac_mode = HVACMode(target_mode)
                    self.async_write_ha_state()
        finally:
            self._lock_count -= 1
            if entity_id in self._zone_tasks:
                del self._zone_tasks[entity_id]

    @callback
    def _handle_select_change(self, event):
        if self._lock_count > 0:
            return
        new_state = event.data.get("new_state")
        if not new_state:
            return
        new_mode = new_state.state
        _LOGGER.info("Il selettore generale ClimaG Mode è cambiato in %s. Esecuzione differita di climag_mode_delay.", new_mode)
        if self._mode_change_task:
            self._mode_change_task.cancel()
        self._mode_change_task = asyncio.create_task(self._handle_climag_mode_delay(new_mode))

    async def _handle_climag_mode_delay(self, target_mode):
        delay = self._get_number_value("climag_mode_delay", 0.0)
        _LOGGER.info("Attendo climag_mode_delay di %s secondi prima di applicare la modalità globale %s.", delay, target_mode)
        await asyncio.sleep(delay)
        
        self._lock_count += 1
        try:
            try:
                self._attr_hvac_mode = HVACMode(target_mode)
                self.async_write_ha_state()
            except ValueError:
                pass

            for climate_id in self._target_climates:
                z_state = self.hass.states.get(climate_id)
                if not z_state:
                    continue
                if target_mode == "off" and z_state.state != "off":
                    await self.hass.services.async_call("climate", "set_hvac_mode", {"entity_id": climate_id, "hvac_mode": "off"})
                elif z_state.state in ["cool", "heat"] and z_state.state != target_mode:
                    await self.hass.services.async_call("climate", "set_hvac_mode", {"entity_id": climate_id, "hvac_mode": target_mode})

            hp_state = self.hass.states.get(self._heat_pump_entity)
            if hp_state and hp_state.state != "off" and target_mode in ["cool", "heat", "fan_only"]:
                await self.hass.services.async_call("climate", "set_hvac_mode", {"entity_id": self._heat_pump_entity, "hvac_mode": target_mode})
                self._check_and_update_pump_temperature()
            
            # NUOVA LOGICA: Se il selettore passa ad off (o ci è andato a seguito del delay), avvia lo spegnimento ritardato della pompa
            elif target_mode == "off" and hp_state and hp_state.state != "off":
                if not self._termo_off_task:
                    if self._valve_on_task:
                        self._valve_on_task.cancel()
                        self._valve_on_task = None
                    _LOGGER.info("ClimaG Mode impostato su OFF. Pianifico lo spegnimento ritardato della pompa di calore.")
                    self._termo_off_task = asyncio.create_task(self._handle_termo_off_delay())
        finally:
            self._lock_count -= 1

    @callback
    def _handle_valve_change(self, event):
        self.async_write_ha_state()
        if self.Valve:
            if not self._valve_on_task:
                if self._termo_off_task:
                    self._termo_off_task.cancel()
                    self._termo_off_task = None
                self._valve_on_task = asyncio.create_task(self._handle_valve_on_delay())
        else:
            if self._valve_on_task:
                self._valve_on_task.cancel()
                self._valve_on_task = None

    async def _handle_valve_on_delay(self):
        delay = self._get_number_value("valve_on_delay", 0.0)
        await asyncio.sleep(delay)
        mode = self._attr_hvac_mode
        if mode in [HVACMode.COOL, HVACMode.HEAT]:
            target_temp = self.Tmf if mode == HVACMode.COOL else self.Tmc
            # Forziamo l'invio della stringa primitiva dell'enum per scongiurare rifiuti da Home Assistant
            await self.hass.services.async_call("climate", "set_hvac_mode", {"entity_id": self._heat_pump_entity, "hvac_mode": str(mode.value)})
            await self.hass.services.async_call("climate", "set_temperature", {"entity_id": self._heat_pump_entity, "temperature": target_temp})

    async def _handle_termo_off_delay(self):
        # Utilizza il valore configurato nel componente number per gestire il ritardo dello spegnimento
        delay = self._get_number_value("termo_off_delay", 0.0)
        _LOGGER.info("Attendo termo_off_delay di %s secondi prima di spegnere la pompa di calore.", delay)
        await asyncio.sleep(delay)
        
        hp_state = self.hass.states.get(self._heat_pump_entity)
        if hp_state and hp_state.state != "off":
            _LOGGER.info("Ritardo scaduto. Spengo la pompa di calore (%s)", self._heat_pump_entity)
            await self.hass.services.async_call("climate", "set_hvac_mode", {"entity_id": self._heat_pump_entity, "hvac_mode": "off"})
            
        self._termo_off_task = None
