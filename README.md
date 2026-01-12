# terraform-vault-backend

A Vault backend for Terraform implemented as an HTTP server.

Built using [FastAPI](https://fastapi.tiangolo.com/).

## Installation

Install with pip (recommended):

```sh
pip3 install --user 'git+ssh://git@github.com/volvo-cars/terraform-vault-backend.git'
```

## Development

You can use `nix develop` or install the following tools by hand:

* [uv](https://docs.astral.sh/uv/#installation)
* [terraform](https://developer.hashicorp.com/terraform/install)

### 1. Running ruff format & checks

```sh
uv run ruff format src
uv run ruff check src
```

### 2. Running the unit tests

```sh
uv run pytest
```

### 3. Running mypy

```sh
uv run mypy src --strict
```

## Usage

### 1. Running the server

#### Running without TLS

```sh
python3 -m tvb
```

#### Running with TLS

```sh
python3 -m tvb --tls-keyfile key.pem --tls-certfile cert.pem --host 0.0.0.0
```

For testing, you can generate `key.pem` and a self-signed `cert.pem` with:

```shell
openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -sha256 -days 3650 -nodes -subj "/CN=localhost"
```

### 2. Configuring Terraform backend

Example configuration, assuming of the backend to be 
hosted at `https://example.com`:

```hcl
terraform {
  backend "http" {
    address = "https://example.com/v1/state/<path>" 
    lock_address = "https://example.com/v1/lock/<path>"
    unlock_address = "https://example.com/v1/lock/<path>"
    lock_method = "POST"
    unlock_method = "DELETE"
  }
}
```

`<path>` is the path to use within the configured mountpoint.

**NOTE:**
For local testing or an otherwise non-TLS setup, you might need to use `skip_cert_verification = true`. 

Refer to the [Terraform documentation](https://developer.hashicorp.com/terraform/language/settings/backends/http)
for additional options. 

### 3. Running Terraform

To authenticate to the Vault backend, you need to send your `VAULT_TOKEN` with your
Terraform invocations. How do we do this? By passing it through HTTP Basic Auth:

```shell
$ export TF_HTTP_USERNAME="${VAULT_TOKEN:?}"
$ terraform apply
```

More info on Vault authentication can be found at [Vault's official documentation](https://developer.hashicorp.com/vault/tutorials/getting-started/getting-started-authentication).
