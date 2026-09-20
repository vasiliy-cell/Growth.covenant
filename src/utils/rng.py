import random
import time
import zlib

import numpy as np
import torch


class RunRandom:
    """
    Every stream of chance in a run, named and grown from one seed.

    A run used to share one random.Random between the map, the spawns and
    the movement conflicts, and to leave the replay sampling and the torch
    exploration on the global generators nobody ever seeded. That is two
    different problems:

      - a shared stream COUPLES everything that draws from it. Two agents
        fighting over a cell consume a draw, so the next refill of the map
        lands somewhere else - and a run with one more birth in it stops
        being the same run from that tick on,
      - a global stream is not part of the run at all: its state comes from
        whatever the process happened to be doing, so the same seed gives a
        different training run every time.

    Here a stream is addressed by a NAME - ("world",), ("agent", 7,
    "policy") - and derived from the run seed alone, through numpy's
    SeedSequence. Nothing a stream draws can move another one: an agent
    keeps its own exploration whether it was born into a crowd or alone,
    and the map is generated the same way however many bodies were fighting
    that tick. The kind is part of the name, so numpy("world") and
    python("world") are two different streams and not the same numbers
    twice.

    Streams are cached, so asking twice returns the same generator and not
    a second copy that repeats the first one's draws.

    state()/load_state() carry every live stream, which is what lets a
    checkpoint resume a run instead of restarting it with the same seed.
    """

    def __init__(self, seed):
        self.seed = int(seed)

        # (kind, name) -> generator
        self._streams = {}

    @staticmethod
    def new_seed():
        """A fresh seed for a run nobody asked to reproduce."""
        return int(time.time() * 1e6)

    # -----------------------------
    # STREAMS
    # -----------------------------
    def python(self, *name):
        """random.Random - the API the world and the replay buffer speak."""
        return self._stream("python", name)

    def numpy(self, *name):
        """np.random.Generator - the API the genome speaks."""
        return self._stream("numpy", name)

    def torch(self, *name):
        """torch.Generator - the API the policy speaks."""
        return self._stream("torch", name)

    def seed_for(self, *name):
        """
        A plain 64-bit seed for code that cannot be handed a generator.

        torch builds a layer's weights from the GLOBAL generator and takes
        no generator argument, so the only way to make one mind's weights
        its own is to seed a forked global state with this.
        """
        sequence = self._sequence("seed", name)
        return int(sequence.generate_state(1, dtype=np.uint64)[0])

    def _stream(self, kind, name):
        key = (kind, name)

        if key not in self._streams:
            self._streams[key] = self._make(kind, self._sequence(kind, name))

        return self._streams[key]

    def _make(self, kind, sequence):
        if kind == "numpy":
            return np.random.default_rng(sequence)

        if kind == "python":
            return random.Random(int(sequence.generate_state(1, dtype=np.uint64)[0]))

        if kind == "torch":
            generator = torch.Generator()
            generator.manual_seed(int(sequence.generate_state(1, dtype=np.uint64)[0]))
            return generator

        raise ValueError(f"Unknown stream kind: {kind}")

    def _sequence(self, kind, name):
        """
        The seed of one stream: the run seed plus the name, hashed.

        The name goes into spawn_key, which is what SeedSequence is built
        for - two different keys give two statistically independent
        streams, and the same key always gives the same one, no matter what
        else the run has already drawn.
        """
        return np.random.SeedSequence(
            entropy=self.seed,
            spawn_key=(self._key(kind),) + tuple(self._key(part) for part in name),
        )

    @staticmethod
    def _key(part):
        """
        A name part as a stable 32-bit number.

        crc32 and not hash(): python randomizes string hashing per process,
        so hash() would give a different stream on every launch - exactly
        the bug this class exists to remove.
        """
        if isinstance(part, int):
            return part & 0xFFFFFFFF

        return zlib.crc32(str(part).encode("utf-8"))

    # -----------------------------
    # STATE (SNAPSHOT / RESUME)
    # -----------------------------
    # Names that start with this belong to one agent; everything else is
    # the world's (the map, the movement draws, the genome, the spawns).
    AGENT = "agent"

    def state(self, scope="all"):
        """
        Every live stream, as JSON-able values.

        Only streams that were actually asked for are in here: a stream
        nobody used has drawn nothing, and re-deriving it from the seed
        gives it back untouched.

        scope: "all", "world" or "agents". A snapshot of the agents costs
        about 16 KB per agent and does not compress - the numbers are
        random, that is the point - so a log that wants the world's streams
        every window and the population's rarely asks for them apart.
        """
        states = {"seed": self.seed, "streams": {}}

        for (kind, name), stream in self._streams.items():
            belongs_to_agent = bool(name) and name[0] == self.AGENT

            if scope == "world" and belongs_to_agent:
                continue
            if scope == "agents" and not belongs_to_agent:
                continue

            states["streams"][self._label(kind, name)] = self._dump(kind, stream)

        return states

    def load_state(self, states):
        """
        Puts every stream back where the snapshot found it, IN PLACE.

        The objects are never replaced, and that is the whole of it: by the
        time a run is restored, a policy is already holding its generator
        and a replay buffer its sampler. Handing back fresh objects would
        restore the state of streams nobody is drawing from, and every mind
        in the world would carry on from an untouched generator - which
        looks exactly like a resume that works, until the numbers are
        compared.
        """
        self.seed = int(states["seed"])

        for label, dumped in states["streams"].items():
            kind, name = self._parse(label)
            stream = self._stream(kind, name)
            self._restore(kind, stream, dumped)

    @staticmethod
    def _dump(kind, stream):
        if kind == "numpy":
            return stream.bit_generator.state

        if kind == "python":
            version, internal, gauss_next = stream.getstate()
            return {
                "version": version,
                "state": list(internal),
                "gauss_next": gauss_next,
            }

        # byte tensor -> hex, twice as compact as a list of ints
        return stream.get_state().numpy().tobytes().hex()

    @staticmethod
    def _restore(kind, stream, dumped):
        if kind == "numpy":
            stream.bit_generator.state = dumped
            return

        if kind == "python":
            stream.setstate(
                (dumped["version"], tuple(dumped["state"]), dumped["gauss_next"])
            )
            return

        stream.set_state(torch.ByteTensor(list(bytes.fromhex(dumped))))

    @staticmethod
    def _label(kind, name):
        return kind + ":" + "/".join(str(part) for part in name)

    @staticmethod
    def _parse(label):
        kind, _, joined = label.partition(":")

        # An index written into the label as a number has to come back as a
        # number, or it would address a different stream than it named.
        name = tuple(
            int(part) if part.lstrip("-").isdigit() else part
            for part in joined.split("/")
        )

        return kind, name

    def __repr__(self):
        return f"RunRandom(seed={self.seed}, streams={len(self._streams)})"
