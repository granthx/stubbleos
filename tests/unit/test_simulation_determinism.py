"""Unit tests verifying strict byte-identical simulation determinism."""

from stubbleos.simulation.config import ScenarioConfig
from stubbleos.simulation.metrics import compute_run_metrics
from stubbleos.simulation.simulator import DistrictSimulator
from stubbleos.simulation.strategy import BaselineAStrategy, BaselineBStrategy


def test_baseline_a_byte_identical_determinism() -> None:
    config = ScenarioConfig(name="test-determinism")
    seed = 4242

    # Run 1
    strat1 = BaselineAStrategy()
    sim1 = DistrictSimulator(config=config, strategy=strat1, seed=seed)
    state1 = sim1.run()
    metrics1 = compute_run_metrics(
        state=state1,
        strategy=strat1,
        scenario_name=config.name,
        seed=seed,
        config_hash=config.config_hash(),
        season_length_days=config.season_length_days,
    )

    # Run 2
    strat2 = BaselineAStrategy()
    sim2 = DistrictSimulator(config=config, strategy=strat2, seed=seed)
    state2 = sim2.run()
    metrics2 = compute_run_metrics(
        state=state2,
        strategy=strat2,
        scenario_name=config.name,
        seed=seed,
        config_hash=config.config_hash(),
        season_length_days=config.season_length_days,
    )

    # Exclude git_commit timestamp/hash variance if any, though it's identical
    json1 = metrics1.model_dump_json()
    json2 = metrics2.model_dump_json()

    assert json1 == json2, "Runs with identical config and seed must produce byte-identical metrics output"


def test_baseline_b_byte_identical_determinism() -> None:
    config = ScenarioConfig(name="test-determinism")
    seed = 8888

    # Run 1
    strat1 = BaselineBStrategy()
    sim1 = DistrictSimulator(config=config, strategy=strat1, seed=seed)
    state1 = sim1.run()
    metrics1 = compute_run_metrics(
        state=state1,
        strategy=strat1,
        scenario_name=config.name,
        seed=seed,
        config_hash=config.config_hash(),
        season_length_days=config.season_length_days,
    )

    # Run 2
    strat2 = BaselineBStrategy()
    sim2 = DistrictSimulator(config=config, strategy=strat2, seed=seed)
    state2 = sim2.run()
    metrics2 = compute_run_metrics(
        state=state2,
        strategy=strat2,
        scenario_name=config.name,
        seed=seed,
        config_hash=config.config_hash(),
        season_length_days=config.season_length_days,
    )

    assert metrics1.model_dump_json() == metrics2.model_dump_json()


def test_different_seeds_produce_different_metrics() -> None:
    config = ScenarioConfig(name="test-determinism")

    strat1 = BaselineBStrategy()
    sim1 = DistrictSimulator(config=config, strategy=strat1, seed=1111)
    state1 = sim1.run()
    metrics1 = compute_run_metrics(
        state=state1,
        strategy=strat1,
        scenario_name=config.name,
        seed=1111,
        config_hash=config.config_hash(),
        season_length_days=config.season_length_days,
    )

    strat2 = BaselineBStrategy()
    sim2 = DistrictSimulator(config=config, strategy=strat2, seed=2222)
    state2 = sim2.run()
    metrics2 = compute_run_metrics(
        state=state2,
        strategy=strat2,
        scenario_name=config.name,
        seed=2222,
        config_hash=config.config_hash(),
        season_length_days=config.season_length_days,
    )

    assert metrics1.model_dump_json() != metrics2.model_dump_json()
