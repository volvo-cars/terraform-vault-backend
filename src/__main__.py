"""Implementation of a Vault backend for Terraform."""

from __future__ import annotations

import argparse
import base64
import gzip
import json
import logging
import os
from dataclasses import dataclass
from typing import Any, Callable, Collection, Iterable, TypeVar, cast

import hvac  # type: ignore
import hvac.exceptions  # type: ignore
import requests.exceptions  # type: ignore
import uvicorn
from fastapi import (
    Depends,
    FastAPI,
    HTTPException,
    Request,
    Response,
    status,
)
from fastapi.datastructures import State
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from typing_extensions import Annotated, Concatenate, ParamSpec

LockData = Any
StateData = Any


STATE_ENCODING = "utf-8"
GZIP_COMPRESSLEVEL = 9
FORMAT_VERSION = "v0"
SERIALIZED_STATE_PIECES = 2  # number of distinct pieces to a serialized state: version + payload


class StateFormatError(ValueError):
    """Error indicating that the given serialized state could not be parsed."""


class MissingFormatVersionError(StateFormatError):
    """Error indicating that the given serialized state has no format version specifier."""

    def __init__(self, *args: object) -> None:
        super().__init__("version format prefix is missing", *args)


class UnsupportedFormatVersionError(StateFormatError):
    """Error indicating that the given serialized state is of an unsupported version."""

    def __init__(self, actual_version: str, *args: str) -> None:
        self.actual_version = actual_version
        msg = f"unsupported state format version: {actual_version}"
        super().__init__(msg, *args)


def strtuple(xs: Iterable[Any]) -> str:
    """Make a tuple-looking string representation of an iterable.

    Args:
    ----
        xs: The iterable to stringify

    """
    return f"({', '.join(xs)})"


def pack_state(o: Any) -> str:
    """Turn an object into a compressed base64-string.

    This function is the inverse of unpack_state.

    Args:
    ----
        o: the object to stringify.

    """
    json_str = json.dumps(o)
    json_bytes = json_str.encode(STATE_ENCODING)
    gzip_bytes = gzip.compress(json_bytes, compresslevel=GZIP_COMPRESSLEVEL, mtime=0)
    b64bytes = base64.b64encode(gzip_bytes)
    b64 = b64bytes.decode(STATE_ENCODING)
    return f"{FORMAT_VERSION}:{b64}"


def unpack_state(state: str) -> Any:
    """Turn a compressed, version-prefixed Terraform state into a Python object.

    This function is the inverse of pack_state.

    Args:
    ----
        state: The compressed and versioned state.

    """
    version_and_payload = state.split(":", 1)
    if len(version_and_payload) != SERIALIZED_STATE_PIECES:
        raise MissingFormatVersionError
    version, b64 = version_and_payload
    if version != FORMAT_VERSION:
        raise UnsupportedFormatVersionError(version)

    b64bytes = b64.encode(STATE_ENCODING)
    gzip_bytes = base64.b64decode(b64bytes)
    json_bytes = gzip.decompress(gzip_bytes)
    json_str = json_bytes.decode(STATE_ENCODING)
    o = json.loads(json_str)
    return o


def _make_path(*parts: Any) -> str:
    return "/".join(str(part) for part in parts if str(part))


P = ParamSpec("P")
T = TypeVar("T")


def raise_bad_connection(f: Callable[P, T]) -> Callable[P, T]:
    """Convert connection errors to HTTPExceptions in decorated function."""

    def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
        try:
            return f(*args, **kwargs)
        except requests.exceptions.ConnectionError as e:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY) from e
        except hvac.exceptions.Forbidden as e:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Vault authentication failed. Bad token or insufficient token scope.",
            ) from e

    return wrapper


X = TypeVar("X")


def coercer(f: Callable[Concatenate[X, P], T]) -> Callable[Concatenate[X, P], T]:
    """Attr coercion wrapper with logging."""

    def wrapper(x: X, /, *args: P.args, **kwargs: P.kwargs) -> T:
        fstatic = f.__get__(object)
        y = cast(T, fstatic(x, *args, **kwargs))
        if y != x:
            logging.debug("'%s': '%s' --> '%s'", fstatic.__name__, x, y)
        else:
            logging.debug("'%s': no-op '%s'", fstatic.__name__, x)
        return y

    return wrapper


def is_maxlimit_error(e: hvac.exceptions.InternalServerError) -> bool:
    """Check if a Vault error seems to be about the state being too large.

    Args:
    ----
        e: The error being checked.

    """
    too_large = "put failed due to value being too large"
    if e.errors is None:
        return False
    if isinstance(e.errors, str):
        return too_large in e.errors
    return any(too_large in err for err in e.errors)


@dataclass(frozen=True)
class Vault:
    """Implementation class of a Vault backend for Terraform.

    Attributes
    ----------
        vault_url: An URL to a Vault instance.
        mount_point: Where the secrets store is mounted.
        secrets_path: The path to the terraform data.
        chunk_size: Size of the state chunks. Dynamically probe for chunk size if set to -1.

    """

    vault_url: str
    mount_point: str
    secrets_path: str
    chunk_size: int

    @property
    def lock_path(self) -> str:
        """The path to the lock, computed from `secrets_path`."""
        return _make_path(self.secrets_path, "lock")

    @property
    def state_path(self) -> str:
        """The path to the state, computed from `secrets_path`."""
        return _make_path(self.secrets_path, "state")

    def get_state_chunk_path(self, chunk: int | str) -> str:
        """Get the path of a state chunk.

        Args:
        ----
            chunk: The chunk number.

        Returns:
        -------
            The path to the chunk.

        """
        return _make_path(self.state_path, chunk)

    @coercer
    @staticmethod
    def _vault_url_coercer(vault_url: str) -> str:
        return vault_url if vault_url.startswith("http") else f"https://{vault_url}"

    @coercer
    @staticmethod
    def _url_path_coercer(url_path: str) -> str:
        return url_path.strip("/")

    @classmethod
    def from_coerced_attrs(
        cls: type[Vault], vault_url: str, mount_point: str, secrets_path: str, chunk_size: int
    ) -> Vault:
        """Return a Vault instance with attrs being coerced. Useful for CLI sanitizing."""
        return cls(
            vault_url=cls._vault_url_coercer(vault_url),
            mount_point=cls._url_path_coercer(mount_point),
            secrets_path=cls._url_path_coercer(secrets_path),
            chunk_size=chunk_size,
        )

    def _mk_client(self, token: str) -> hvac.Client:
        """Get an instance of a Vault client.

        Args:
        ----
        token: the vault token to use for authentication.

        """
        return hvac.Client(url=self.vault_url, token=token)

    @raise_bad_connection
    def get_lock_data(self, token: str) -> LockData:
        """Return the lock data."""
        logging.info("Getting lock data from vault...")
        return self._mk_client(token).secrets.kv.v2.read_secret_version(
            path=self.lock_path,
            mount_point=self.mount_point,
            raise_on_deleted_version=True,  # default will change to false in the near future
        )["data"]["data"]

    @raise_bad_connection
    def acquire_lock(self, token: str, lock_data: LockData) -> None:
        """Acquire the lock for the Terraform state.

        Args:
        ----
            token: the vault token to use for authentication.
            lock_data: Metadata that identifies the lock.

        Raises:
        ------
            HTTPException: Lock is already locked.

        """
        logging.info("Acquiring lock...")
        try:
            self._mk_client(token).secrets.kv.v2.create_or_update_secret(
                path=self.lock_path, secret=lock_data, mount_point=self.mount_point, cas=0
            )
        except hvac.exceptions.InvalidRequest as e:
            raise HTTPException(
                status_code=status.HTTP_423_LOCKED, detail="Lock cannot be acquired: already locked"
            ) from e
        logging.info("Acquired lock successfully!")

    @raise_bad_connection
    def release_lock(self, token: str) -> None:
        """Release the lock for the Terraform state.

        Args:
        ----
            token: the vault token to use for authentication.

        Raises:
        ------
            HTTPException: No state exists

        """
        logging.info("Releasing lock...")
        self._mk_client(token).secrets.kv.v2.delete_metadata_and_all_versions(
            path=self.lock_path, mount_point=self.mount_point
        )
        logging.info("Lock released!")

    @raise_bad_connection
    def _get_chunk_keys(self, token: str) -> Iterable[str]:
        logging.info("Looking for state chunks...")
        try:
            chunk_keys = cast(
                Collection[str],
                self._mk_client(token).secrets.kv.v2.list_secrets(
                    path=self.state_path,
                    mount_point=self.mount_point,
                )["data"]["keys"],
            )
            logging.info("Found %d state chunks: %s", len(chunk_keys), strtuple(chunk_keys))
        except hvac.exceptions.InvalidPath as e:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="No state exists"
            ) from e
        else:
            return chunk_keys

    @raise_bad_connection
    def get_state(self, token: str) -> StateData:
        """Return the Terraform state.

        Args:
        ----
            token: the vault token to use for authentication.

        Raises:
        ------
            HTTPException: State does not exist.

        """
        logging.info("Getting state...")
        chunks: dict[str, str | None] = {
            chunk_key: None for chunk_key in self._get_chunk_keys(token)
        }
        for chunk_key in chunks:
            logging.info("Getting state chunk %s...", chunk_key)
            data = self._mk_client(token).secrets.kv.v2.read_secret_version(
                path=self.get_state_chunk_path(chunk_key),
                mount_point=self.mount_point,
                raise_on_deleted_version=False,
            )
            if data["data"]["metadata"]["deletion_time"] != "":
                logging.info("State chunk %s has been deleted, marked as invalid", chunk_key)
            else:
                logging.info("State chunk %s: is OK", chunk_key)
                chunks[chunk_key] = data["data"]["data"]["value"]

        valid_chunks = {k: v for k, v in chunks.items() if v}
        invalid_chunks = {k: v for k, v in chunks.items() if not v}

        logging.info("Total chunks: %s", strtuple(chunks))
        logging.info("Valid chunks: %s", strtuple(valid_chunks))
        logging.info("Invalid chunks: %s", strtuple(invalid_chunks))
        return unpack_state("".join(valid_chunks.values())) or {}

    def _chunk_size_probe(self, token: str, data: str) -> int:
        cut_off = len(data)
        logging.info("Chunk size probing starting at %d chars", cut_off)
        while True:
            logging.info("Probing vault with a state chunk of %d chars...", cut_off)
            probing_chunk = data[:cut_off]
            try:
                self._mk_client(token).secrets.kv.v2.create_or_update_secret(
                    path=self.get_state_chunk_path(0),
                    mount_point=self.mount_point,
                    secret={"value": probing_chunk},
                )
            except hvac.exceptions.InternalServerError as e:
                if not is_maxlimit_error(e):
                    raise e from e
                new_cut_off = cut_off // 2
                logging.info("Chunk length %d too long, retry with %d", cut_off, new_cut_off)
                cut_off = new_cut_off
            else:
                logging.info("Chunk size probing succeeded: length of %d is OK!", cut_off)
                return cut_off

    def _get_static_cut_off_(self) -> int:
        # Assume that we use UTF8. This means that each char is stored as one (1) byte,
        # i.e. the length of a string equals its size in bytes.
        # That means, for example, that a secret store with a
        # max limit of 1MB should fit a million characters long string.
        # However, in practice, we also end up needing
        # a margin for things like the request dict size and CPython internals.
        if not STATE_ENCODING == "utf-8":
            raise NotImplementedError
        return self.chunk_size - 1000  # margin

    def _delete_old_chunks(self, token: str, chunks_done: int) -> None:
        unset_chunk_keys = [k for k in self._get_chunk_keys(token) if int(k) > (chunks_done - 1)]
        logging.info("Marking unset chunks %s as deleted...", strtuple(unset_chunk_keys))
        for chunk_key in unset_chunk_keys:
            logging.info("Marking %s as deleted...", chunk_key)
            self._mk_client(token).secrets.kv.v2.delete_latest_version_of_secret(
                path=self.get_state_chunk_path(chunk_key), mount_point=self.mount_point
            )
        logging.info("OK: Unset chunks marked as deleted.")

    @raise_bad_connection
    def set_state(self, token: str, value: Any) -> None:
        """Setter for Terraform state.

        Args:
        ----
            token: the vault token to use for authentication.
            value: The terraform state.

        """
        logging.info("Setting state...")
        logging.debug("Encoding & compressing state dict into string...")
        packed_state = pack_state(value)

        chunks_done = 0
        chunk_pos = 0
        if self.chunk_size == -1:  # probe
            logging.info("Chunk size probing enabled!")
            cut_off = self._chunk_size_probe(token=token, data=packed_state)
            chunks_done += 1
            chunk_pos += cut_off
        else:  # don't probe
            logging.info("Chunk size probing disabled! Set at %d bytes.", self.chunk_size)
            cut_off = self._get_static_cut_off_()

        while chunk_pos < len(packed_state):
            new_chunk_pos = chunk_pos + cut_off
            logging.info("Sending chunk [%d:%d]...", chunk_pos, new_chunk_pos)
            chunk = packed_state[chunk_pos:new_chunk_pos]
            self._mk_client(token).secrets.kv.v2.create_or_update_secret(
                path=self.get_state_chunk_path(chunks_done),
                mount_point=self.mount_point,
                secret={"value": chunk},
            )
            chunks_done += 1
            chunk_pos = new_chunk_pos

        self._delete_old_chunks(token=token, chunks_done=chunks_done)
        logging.info("OK: State set.")


app = FastAPI()


def start() -> None:
    """HTTP Server for Terraform Vault backend.

    Environment:
    ------------
        VAULT_ADDR:   Default Vault URL to connect to.
                        - Optional.
                        - Overridable with --vault-url.

    """
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter, description=start.__doc__
    )
    parser.add_argument(
        "--vault-url",
        help="URL to the Vault instance. Defaults to $VAULT_ADDR or '127.0.0.1:8200'",
        default=os.environ.get("VAULT_ADDR", "127.0.0.1:8200"),
    )
    parser.add_argument(
        "--mount-point",
        help="Where the Vault secrets store is mounted. Defaults to 'secret/'",
        default="secret/",
    )
    parser.add_argument(
        "--host", help="The host address to bind to. Defaults to '127.0.0.1'.", default="127.0.0.1"
    )
    parser.add_argument(
        "--port", help="The port to bind to. Defaults to '8300'.", type=int, default=8300
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        help="""
            Max size, in bytes, that a state chunk can be as a Vault secret.
            If set to -1, automatically probe for max chunk size.
            Defaults to -1.
        """,
        default="-1",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="count",
        default=0,
        help="""
            Increases logging verbosity.
        """,
    )
    args = parser.parse_args()

    loglevels = (logging.WARNING, logging.INFO, logging.DEBUG)
    logging.basicConfig(level=loglevels[args.verbose])

    app.state.vault_url = args.vault_url
    app.state.mount_point = args.mount_point
    app.state.chunk_size = args.chunk_size

    uvicorn.run(app, host=args.host, port=args.port)


def get_app_state(request: Request) -> State:
    """Depend explicitly on app state only, without access to the request."""
    return cast(FastAPI, request.app).state


AppStateDep = Annotated[State, Depends(get_app_state)]


def get_vault(state: AppStateDep, secrets_path: str) -> Vault:
    """Return vault instance for use as a FastAPI dependency."""
    vault = Vault.from_coerced_attrs(
        vault_url=state.vault_url,
        mount_point=state.mount_point,
        chunk_size=state.chunk_size,
        secrets_path=secrets_path,
    )
    return vault


SecurityDep = Annotated[HTTPBasicCredentials, Depends(HTTPBasic())]


def get_vault_token(credentials: SecurityDep) -> str:
    """Return vault token from HTTP Basic auth for use as a FastAPI dependency."""
    return credentials.username


VaultDep = Annotated[Vault, Depends(get_vault)]
TokenDep = Annotated[str, Depends(get_vault_token)]


# https://github.com/tiangolo/fastapi/issues/1773
@app.head("/")
@app.get("/")
async def read_root_head() -> Response:
    """Support HTTP GET and HEAD for /."""
    return Response()


@app.get("/state/{secrets_path:path}")
async def get_state(vault: VaultDep, token: TokenDep) -> StateData:
    """Get the Vault state."""
    return vault.get_state(token=token)


@app.post("/state/{secrets_path:path}")
async def update_state(request: Request, vault: VaultDep, token: TokenDep) -> None:
    """Update the Vault state."""
    try:
        data = await request.json()
    except json.JSONDecodeError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Recieved malformed JSON!"
        ) from e
    vault.set_state(token=token, value=data)


@app.get("/lock/{secrets_path:path}")
async def get_lock_info(vault: VaultDep, token: TokenDep) -> LockData:
    """Get lock info."""
    return vault.get_lock_data(token=token)


@app.post("/lock/{secrets_path:path}")
async def acquire_lock(request: Request, vault: VaultDep, token: TokenDep) -> None:
    """Acquire the lock for Terraform state."""
    data = await request.json()
    return vault.acquire_lock(token=token, lock_data=data)


@app.delete("/lock/{secrets_path:path}")
async def release_lock(vault: VaultDep, token: TokenDep) -> None:
    """Acquire the lock for Terraform state."""
    return vault.release_lock(token=token)


if __name__ == "__main__":
    start()
