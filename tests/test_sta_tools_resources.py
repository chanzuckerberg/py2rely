from types import SimpleNamespace

import pytest

from py2rely.prepare import parameters
from py2rely.utils import sta_tools


class JobOption:
    def __init__(self, value):
        self.value = value

    def get_boolean(self):
        if isinstance(self.value, str):
            return self.value.lower() == "yes"
        return bool(self.value)


class FakeExecutor:
    instances = []

    def __init__(self, folder):
        self.folder = folder
        self.updates = []
        self.instances.append(self)

    def update_parameters(self, **kwargs):
        self.updates.append(kwargs)

    def submit(self, *args):
        return SimpleNamespace(result=lambda: ("Succeeded", "CPU/job001/"))


def make_helper():
    helper = sta_tools.PipelineHelper.__new__(sta_tools.PipelineHelper)
    helper.cpu_budget = 16
    helper.cpu_nodes = 1
    helper.ncpus = 16
    helper.mem_per_cpu = 12
    helper.timeout = 24
    helper.timeout_min = 24 * 60
    helper.gpu_constraint = None
    helper.gpu_nodes = [1, 4]
    helper.num_gpus = 4
    helper.ntasks = helper.num_gpus + 1
    helper.myProject = SimpleNamespace(pipeline_name="pipeline")
    return helper


def make_job(tmp_path, *, use_gpu=False, threads=5, ranks=3):
    return SimpleNamespace(
        OUT_DIR=str(tmp_path / "CPU"),
        joboptions={
            "use_gpu": JobOption(use_gpu),
            "nr_threads": JobOption(threads),
            "nr_mpi": JobOption(ranks),
        },
    )


def test_cpu_ranks_use_configured_budget(tmp_path):
    helper = make_helper()
    job = make_job(tmp_path, threads=5)

    assert helper.cpu_ranks_for(job) == 3

    helper.cpu_budget = 10
    assert helper.cpu_ranks_for(job) == 2


def test_cpu_parallelism_uses_boolean_option_and_sets_mpi_command(tmp_path):
    helper = make_helper()
    helper.cpu_budget = 20
    job = make_job(tmp_path, use_gpu="No", threads=5)
    job.joboptions["mpi_command"] = JobOption("mpirun")

    helper.apply_parallelism(job, "class3D")

    assert job.joboptions["nr_mpi"].value == 4
    assert job.joboptions["mpi_command"].value == "mpirun --oversubscribe -n XXXmpinodesXXX"


def test_gpu_parallelism_uses_one_leader_and_one_rank_per_gpu(tmp_path):
    helper = make_helper()
    job = make_job(tmp_path, use_gpu="Yes", threads=5)

    helper.apply_parallelism(job, "class3D")

    assert job.joboptions["nr_mpi"].value == 5


def test_auto_refine_uses_an_odd_rank_count(tmp_path):
    helper = make_helper()
    helper.cpu_budget = 20
    job = make_job(tmp_path, threads=5)

    helper.apply_parallelism(job, "refine3D")

    assert job.joboptions["nr_mpi"].value == 3


def test_refinement_models_combine_weights_through_disk():
    assert parameters.Refine3D.model_fields["do_combine_thru_disc"].default == "yes"
    assert parameters.Class3D.model_fields["do_combine_thru_disc"].default == "yes"


def test_cpu_submission_uses_one_node_and_total_memory(tmp_path, monkeypatch):
    FakeExecutor.instances.clear()
    monkeypatch.setattr(sta_tools.submitit, "AutoExecutor", FakeExecutor)
    monkeypatch.setattr(sta_tools, "get_load_commands", lambda **kwargs: ("", ""))

    helper = make_helper()
    job = make_job(tmp_path)

    helper.submit_job(job, "CPU job")

    executor = FakeExecutor.instances[-1]
    assert executor.updates[0]["tasks_per_node"] == 3
    assert executor.updates[0]["cpus_per_task"] == 5
    assert executor.updates[0]["slurm_mem"] == "192G"
    assert "slurm_mem_per_cpu" not in executor.updates[0]
    assert executor.updates[1]["slurm_additional_parameters"] == {"nodes": 1}


def test_multi_node_gpu_submission_is_rejected(tmp_path, monkeypatch):
    FakeExecutor.instances.clear()
    monkeypatch.setattr(sta_tools.submitit, "AutoExecutor", FakeExecutor)

    helper = make_helper()
    helper.gpu_nodes = [2, 4]
    helper.num_gpus = 8
    job = make_job(tmp_path, use_gpu=True, ranks=9)

    with pytest.raises(ValueError, match="multi-node GPU jobs are not supported"):
        helper.submit_job(job, "GPU job")


def test_gpu_submission_packs_gpus_on_one_node(tmp_path, monkeypatch):
    FakeExecutor.instances.clear()
    monkeypatch.setattr(sta_tools.submitit, "AutoExecutor", FakeExecutor)
    monkeypatch.setattr(sta_tools, "get_load_commands", lambda **kwargs: ("", ""))

    helper = make_helper()
    job = make_job(tmp_path, use_gpu=True, ranks=5)

    helper.submit_job(job, "GPU job")

    executor = FakeExecutor.instances[-1]
    assert executor.updates[1]["slurm_additional_parameters"] == {
        "nodes": 1,
        "gpus_per_node": 4,
    }
