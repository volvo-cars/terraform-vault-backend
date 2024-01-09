#!/bin/bash
set -euo pipefail

while ! wget -q --spider "http://vault:8200"; do sleep 1; done

out="$(vault operator init -key-shares=1 -key-threshold=1 -format 'json')"
unseal_key="$(echo "$out" | jq -r '.unseal_keys_hex[0]')"
echo "$unseal_key"
VAULT_TOKEN="$(echo "$out" | jq -r '.root_token')"
echo "hello $VAULT_TOKEN"
TF_HTTP_PASSWORD="$VAULT_TOKEN"

export VAULT_TOKEN 
export TF_HTTP_PASSWORD
export TF_IN_AUTOMATION=true

vault operator unseal "$unseal_key"
vault secrets enable -version=2 -path=secret kv


script="$1"
if [ -z "$2" ]; then
    # Set a default value for the second argument
    size="small"
else
    size="$2"
fi

ln -s "main.tf.$size" "main.tf"
. "tests/$script.sh"


