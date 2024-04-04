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


def worker_exit(server, worker):
    flask = worker.app.callable
    args = flask.config["args"]

    for port in [
        args.gnormplus_port,
        args.tmvar2_port,
        args.gene_norm_port,
        args.disease_norm_port,
    ]:
        os.system(f"kill -9 $(lsof -t -i tcp:{port})")

    os.system(f"rm -rf {args.tmpdir}")
    print("Killed", worker.pid, "and removed", args.tmpdir)


def post_worker_init(worker):
    import subprocess

    args = BERN2Args()

    for server in SERVERS:
        os.makedirs(logdir := "/var/log/bern2/" + server.dir, exist_ok=True)
        os.makedirs(dir := args.tmpdir + "/" + server.dir, exist_ok=True)

        subprocess.run(f"cp -ra {server.dir}/* {dir}", shell=True)
        for subdir in ["input", "output", "tmp"]:
            subprocess.run(f"rm -rf {dir}/{subdir}", shell=True)
            os.makedirs(f"{dir}/{subdir}")
        print("Created", dir)

        log = open(f"{logdir}/{os.getpid()}.{id(worker.app.callable)}.log", "w")
        subprocess.Popen(
            [server.bin, *[arg.format(**asdict(args)) for arg in server.args]],
            cwd=dir,
            # stdout=log,
            # stderr=subprocess.STDOUT,
        )
        print(
            "Started",
            server.dir,
            "in",
            args.tmpdir,
            "with gnormplus_port",
            args.gnormplus_port,
            "and tmvar2_port",
            args.tmvar2_port,
            "and gene_norm_port",
            args.gene_norm_port,
            "and disease_norm_port",
            args.disease_norm_port,
        )

    for type in ["disease", "gene"]:
        for dir in ["inputs", "outputs"]:
            path = f"{args.tmpdir}/resources/normalization/{dir}/{type}"
            subprocess.run(f"rm -rf {path}", shell=True)
            os.makedirs(path, exist_ok=True)
            print("Created", path)

    os.chdir(args.tmpdir)

    import bern2
    from app.result_parser import ResultParser

    flask = worker.app.callable
    flask.config["args"] = args
    flask.config["model"] = bern2.BERN2(
        **{
            k: v
            for k, v in asdict(args).items()
            if k not in ["host", "port", "tmpdir", "front_dev", "port_offset"]
        }
    )
    flask.config["r_parser"] = ResultParser()

    print("PID", worker.pid, "started with", asdict(args))
