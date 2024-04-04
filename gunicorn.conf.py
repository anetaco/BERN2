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

    cwd = os.getcwd()
    os.chdir(args.tmpdir)

    for server in SERVERS:
        logdir = "/var/log/bern2/" + server.dir
        os.makedirs(logdir, exist_ok=True)
        os.makedirs(server.dir, exist_ok=True)
        subprocess.run(f"cp -ra {cwd}/{server.dir} {server.dir}", shell=True)
        for subdir in ["input", "output", "tmp"]:
            subprocess.run(f"rm -rf {server.dir}/{subdir}", shell=True)
            os.makedirs(f"{server.dir}/{subdir}")
            print("Created", f"{server.dir}/{subdir}")
        log = open(f"{logdir}/{os.getpid()}.{id(worker.app.callable)}.log", "w")
        subprocess.Popen(
            [server.bin, *[arg.format(**asdict(args)) for arg in server.args]],
            cwd=server.dir,
            # stdout=log,
            # stderr=subprocess.STDOUT,
        )
        print("Started", server.dir, "in", args.tmpdir, "with PID", worker.pid)
        os.chdir(cwd)

    for type in ["disease", "gene"]:
        for dir in ["inputs", "outputs"]:
            path = f"{args.tmpdir}/resources/normalization/{dir}/{type}"
            subprocess.run(f"rm -rf {path}", shell=True)
            os.makedirs(path, exist_ok=True)
            print("Created", path)

    import bern2
    from app.result_parser import ResultParser

    flask = worker.app.callable
    flask.config["model"] = bern2.BERN2(
        **{
            k: v
            for k, v in asdict(args).items()
            if k not in ["host", "port", "tmpdir", "front_dev", "port_offset"]
        }
    )
    flask.config["r_parser"] = ResultParser()

    print("PID", worker.pid, "started with", asdict(args))
