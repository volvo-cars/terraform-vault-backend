# terraform-vault-backend

A Vault backend for Terraform implemented as an HTTP server.

Built using [FastAPI](https://fastapi.tiangolo.com/).

## Installation

Install using [Poetry](https://python-poetry.org/):
```sh
poetry install
```

## Usage

### 1. Running the server

#### Running it directly
  ```sh
  poetry run python -m src
  ```
#### Using a poetry shell
  ```sh
  poetry shell
  python -m src
  ```
This will run the backend with Vault defaults.
Please refer to `python -m src --help` for configuration options.

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
