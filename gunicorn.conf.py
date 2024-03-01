import os
from dataclasses import asdict, dataclass

from server import BERN2Args


@dataclass
class Server:
    dir: str
    bin: str
    args: list[str]


SERVERS = [
    Server(
        dir="multi_ner",
        bin="python",
        args=[
            "ner_server.py",
            "--mtner_home",
            ".",
            "--mtner_port",
            "{mtner_port}",
        ],
    ),
    Server(
        dir="resources/GNormPlusJava",
        bin="java",
        args=[
            "-Xmx16G",
            "-Xms16G",
            "-jar",
            "GNormPlusServer.main.jar",
            "{gnormplus_port}",
        ],
    ),
    Server(
        dir="resources/tmVarJava",
        bin="java",
        args=["-Xmx8G", "-Xms8G", "-jar", "tmVar2Server.main.jar", "{tmvar2_port}"],
    ),
    Server(
        dir="resources/normalization",
        bin="java",
        args=[
            "-Xmx16G",
            "-jar",
            "normalizers/disease/disease_normalizer_21.jar",
            "inputs/disease",
            "outputs/disease",
            "dictionary/dict_Disease_20210630.txt",
            "normalizers/disease/resources",
            "9",
            "{disease_norm_port}",
        ],
    ),
    Server(
        dir="resources/normalization/normalizers/gene",
        bin="java",
        args=[
            "-Xmx20G",
            "-jar",
            "gnormplus-normalization_21.jar",
            "{gene_norm_port}",
        ],
    ),
]


def post_worker_init(worker):
    import subprocess

    args = BERN2Args()
    for arg in [
        "mtner_port",
        "gnormplus_port",
        "tmvar2_port",
        "gene_norm_port",
        "disease_norm_port",
    ]:
        setattr(args, arg, getattr(args, arg) + os.getpid())

    cwd = os.getcwd()
    for server in SERVERS:
        dir = args.tmpdir + "/" + server.dir
        logdir = "/var/log/bern2/" + server.dir
        os.makedirs(logdir, exist_ok=True)
        os.makedirs(dir, exist_ok=True)
        os.chdir(dir)
        subprocess.run(f"ln -fs {cwd}/{server.dir}/* .", shell=True)
        for subdir in ["input", "output", "tmp"]:
            subprocess.run(f"rm -rf {dir}/{subdir}", shell=True)
            os.makedirs(f"{dir}/{subdir}")
            print("Created", f"{dir}/{subdir}")
        log = open(f"{logdir}/{os.getpid()}.{id(worker.app.callable)}.log", "w")
        subprocess.Popen(
            [server.bin, *[arg.format(**asdict(args)) for arg in server.args]],
            stdout=log,
            stderr=subprocess.STDOUT,
        )
        print("Started", server.dir, "in", dir)
        os.chdir(cwd)

    import bern2
    from app.result_parser import ResultParser

    flask = worker.app.callable
    flask.config["model"] = bern2.BERN2(
        **{
            k: v
            for k, v in asdict(args).items()
            if k not in ["host", "port", "tmpdir", "front_dev"]
        }
    )
    flask.config["r_parser"] = ResultParser()

    print("PID", worker.pid, "started with", asdict(args))
