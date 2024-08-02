terraform {
  required_providers {
    vault = {
      source  = "hashicorp/vault"
      version = ">= 4.3.0"
    }
  }

  backend "http" {
    address = "http://0.0.0.0:8300/state/terraform" 
    lock_address = "http://0.0.0.0:8300/lock/terraform"
    unlock_address = "http://0.0.0.0:8300/lock/terraform"
    lock_method = "POST"
    unlock_method = "DELETE"
    username = "*" # unused but must be defined
  }
}

data "vault_kv_secret_v2" "password_data" {
  mount = "secret"
  name  = "password_data"
}

resource "local_file" "password" { 
  content = data.vault_kv_secret_v2.password_data.data.password
  filename = "${path.module}/somefile.txt"
}