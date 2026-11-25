from sentry.config import CONFIG_PATH, load_config


def test_hardware_config_loads_without_simulation_settings():
    loaded = load_config(CONFIG_PATH)

    assert "runtime" not in loaded or "simulation" not in loaded["runtime"]
