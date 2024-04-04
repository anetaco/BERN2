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
    try:
        args = flask.config["args"]
    except (KeyError, AttributeError):
        return

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

    os.chdir("/opt/bern2")
    args = BERN2Args()

    prefixes = set()
    for server in SERVERS:
        dir = args.tmpdir + "/" + server.dir
        subprocess.run(f"rm -rf {dir}", shell=True)
        subprocess.run(f"mkdir -p {dir}", shell=True)

        if any(server.dir.startswith(prefix) for prefix in prefixes):
            print(f"Skipping ln of duplicate prefix: {server.dir}")
        else:
            prefixes.add(server.dir)
            subprocess.run(f"ln -s /opt/bern2/{server.dir}/* {dir}", shell=True)

        for subdir in ["input", "output", "tmp"]:
            subprocess.run(f"rm -rf {dir}/{subdir}", shell=True)
            os.makedirs(f"{dir}/{subdir}")
        print("Created", dir)

    for type in ["disease", "gene"]:
        for dir in ["inputs", "outputs"]:
            path = f"{args.tmpdir}/resources/normalization/{dir}/{type}"
            subprocess.run(f"rm -rf {path}", shell=True)
            os.makedirs(path, exist_ok=True)
            print("Created", path)

    for server in SERVERS:
        os.makedirs(logdir := "/var/log/bern2/" + server.dir, exist_ok=True)
        log = open(f"{logdir}/{os.getpid()}.{id(worker.app.callable)}.log", "w")
        subprocess.Popen(
            [server.bin, *[arg.format(**asdict(args)) for arg in server.args]],
            cwd=args.tmpdir + "/" + server.dir,
            # stdout=log,
            # stderr=subprocess.STDOUT,
        )
    print(
        "Started",
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
