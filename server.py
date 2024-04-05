import os
from dataclasses import dataclass, field
from multiprocessing import Value
from tempfile import mkdtemp

_count = Value("i", 0)


def _next_offset():
    with _count.get_lock():
        _count.value += 1
        return _count.value * 10


@dataclass
class BERN2Args:
    tmpdir: str = field(default_factory=mkdtemp)
    port_offset: int = field(default_factory=_next_offset)

    mtner_home: str = "multi_ner"
    mtner_port: int = 18894
    gnormplus_home: str = "resources/GNormPlusJava"
    gnormplus_port: int = 18895
    tmvar2_home: str = "resources/tmVarJava"
    tmvar2_port: int = 18896
    gene_norm_port: int = 18888
    disease_norm_port: int = 18892

    cache_host: str = "localhost"
    cache_port: int = 27017
    host: str = "0.0.0.0"
    port: int = 8888

    use_neural_normalizer: bool = True
    keep_files: bool = False
    no_cuda: bool = False
    front_dev: bool = False

    def __post_init__(self):
        self.mtner_home = os.path.join(self.tmpdir, self.mtner_home)
        self.gnormplus_home = os.path.join(self.tmpdir, self.gnormplus_home)
        self.tmvar2_home = os.path.join(self.tmpdir, self.tmvar2_home)

        self.mtner_port += self.port_offset
        self.gnormplus_port += self.port_offset
        self.tmvar2_port += self.port_offset
        self.gene_norm_port += self.port_offset
        self.disease_norm_port += self.port_offset


args = BERN2Args()

if __name__ == "__main__":
    os.execlp(
        "gunicorn",
        "gunicorn",
        # "--preload",
        "--timeout",
        "600",
        "-w",
        "6",
        "-b",
        f"{args.host}:{args.port}",
        "--log-level",
        "debug",
        "--access-logfile",
        "-",
        "--error-logfile",
        "-",
        "server:bern2",
    )
else:
    from app import create_app

    bern2 = create_app(args)
