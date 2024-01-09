#!/bin/bash
terraform init

terraform apply -auto-approve
out="$(vault kv list -format=json secret/tf-backend/state)"
echo "$out"
num_of_secrets="$(echo "$out" | jq length)"
[[ "$num_of_secrets" -gt "1" ]]
echo "OK: Is chunked."
terraform destroy -auto-approve



