#!/bin/bash

# sabotage lock release
sed -i \
  's/unlock_method = "DELETE"/unlock_method = "GET"/g' \
  main.tf
terraform init -reconfigure
terraform apply -auto-approve
sed -i 's/STRING/APPENDSTRING/g' "main.tf"
out=$(! terraform apply -no-color -auto-approve 2>&1)
echo $out
target='HTTP remote state already locked'
if ! [[ "$out" == *"$target"* ]]; then
  exit 1
fi
sed -i \
  's/unlock_method = "GET"/unlock_method = "DELETE"/g' \
  main.tf
terraform init -reconfigure
terraform force-unlock -force this-is-a-dummy-string
terraform destroy -auto-approve
