from sentry.config import CONFIG_PATH, load_config


def test_hardware_mode_is_default(monkeypatch):
    monkeypatch.delenv("PRAHARI_SIM", raising=False)

    loaded = load_config(CONFIG_PATH)

    assert loaded["runtime"]["simulation"] is False


def test_simulation_requires_explicit_opt_in(monkeypatch):
    monkeypatch.setenv("PRAHARI_SIM", "1")

    loaded = load_config(CONFIG_PATH)

    assert loaded["runtime"]["simulation"] is True
