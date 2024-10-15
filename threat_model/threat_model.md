# Terraform Vault Backend Threat Model

## Attacker personas

| Capabilities | Acronym |
|--------------|---------|
| Unauthenticated Internet attacker | UIA |
| Local network attacker | LNA |
| Malicious user | MUA |
| Compromised TVB | CTA |
| Compromised Vault | CVA |


## Assumptions
- Malicious TF state can cause information leaks when used by TF client to deploy an application.
- TVB and Vault are deployed on a local network separated from the Internet.
- Certificates issued by CAs are trustworthy.
  - If they are not, any use of "proper certificates" can be further secured with certificate pinning.


## Use cases

### UC1: Get State
A Terraform client calls the Terraform Vault Backend to obtain previously stored TF state.

| Use case | Attacker | What | Impact | Exposure | Severity | Countermeasures |
|----------|----------|------|--------|----------|----------|-----------------|
| UC1:1 | UIA | Impersonate service to obtain Vault API keys | High | Low | High | Protect traffic with TLS + proper certificates |
| UC1:1 | UIA | DoS server with garbage traffic | Low | Medium | Low | Deploy service on internal network or behind DoS protection |
| UC1:1 | UIA | Exhaust server resources using clever tricks like slow loris | Low | High | Medium | See above; or deploy service behind mitigating reverse proxy like nginx |
| UC1:1 | UIA | Eavesdrop on traffic to obtain Vault API keys | High | Low | High | Protect traffic with TLS |
| UC1:1 | MUA | Impersonate another user to obtain secrets from TF state | High | Low | High | Do not share Vault API keys between users/teams/projects |
| UC1:1 | LNA | DoS server with garbage traffic | Low | Low | Low | Ensure sufficient service resources; harden other machines on network so they can't be used for attacks |
| UC1:1 | LNA | Exhaust server resources using clever tricks like slow loris | Low | Low | Low | Filter traffic between service/proxy and rest of network |
| UC1:1 | CTA | Obtain and leak Vault API keys | High | Low | High | Filter outbound network traffic to avoid exfiltration; deploy IDS to increase chance of detection; ensure dependencies are minimal, trustworthy, and up to date |
| UC1:2 | LNA | Impersonate Vault to obtain Vault API keys | High | Low | High | Protect traffic with TLS + proper certificates |
| UC1:2 | LNA | Eavesdrop on traffic to obtain Vault API keys | High | Low | High | Protect traffic with TLS |
| UC1:2 | LNA | Impersonate user to obtain Vault secrets | High | Low | High | Require authentication for Vault access |
| UC1:2 | LNA | DoS Vault with garbage traffic | Low | Low | Low | Ensure sufficient service resources; harden other machines on network so they can't be used for attacks |
| UC1:2 | LNA | Exhaust Vault resources using clever tricks like slow loris | Low | Low | Low | Deploy Vault behind mitigating proxy; filter traffic between Vault/proxy and rest of network |
| UC1:2 | CVA | Obtain and leak Vault API keys | High | Low | High | Filter outbound network traffic to avoid exfiltration; deploy IDS to increase chance of detection; ensure Vault is kept up to date |
| UC1:3 | LNA | Return malicious state to user which steals data from deployment if deployed | High | Low | High | Protect traffic with TLS |
| UC1:3 | LNA | Eavesdrop on returned TF state to obtain secrets | High | Low | High | Protect traffic with TLS |
| UC1:3 | CTA | Leak secrets obtained from Vault | High | Low | High | Filter outbound traffic to prevent exfiltration; ensure dependencies are minimal, trustworthy, and up to date |
| UC1:3 | CVA | Return malicious state to user which DoSes deployment if deployed | Medium | Low | Low | Deploy IDS to increase chance of detection; implement gradual rollout and rollback strategy | UC1:3 | CVA | Return malicious state to user which steals data from deployment if deployed | High | Low | High | Deploy IDS to increase chance of detection; ensure Vault is kept up to date |
| UC1:4 | UIA | Impersonate user to obtain secrets from TF state | High | High | High | Authenticate using Vault API key |
| UC1:4 | UIA | Return malicious state to user which steals data from deployment if deployed | High | Low | Low | Protect traffic with TLS |
| UC1:4 | UIA | Eavesdrop on TF state as it is sent to user to obtain secrets | High | Low | Medium | Protect traffic with TLS |
| UC1:1 | MUA | Impersonate another user | Low | Medium | Low | Use mTLS with individual certificates, log accesses |
| UC1:4 | MUA | Leak secrets to unauthorized third parties | High | Low | High | Ensure all get requests are logged; do not share Vault API keys |
| UC1:4 | CTA | Return malicious state to user which DoSes deployment if deployed | Medium | Low | Low | Deploy IDS to increase chance of detection; implement gradual rollout and rollback strategy |
| UC1:4 | CTA | Return malicious state to user which steals data from deployment if deployed | High | Low | High | Deploy IDS to increase chance of detection; ensure dependencies are minimal, trustworthy, and up to date |


## UC2: Safely Update State
A Terraform client locks a particular state, updates it, and then unlocks it.

| Use case | Attacker | What | Impact | Exposure | Severity | Countermeasures |
|----------|----------|------|--------|----------|----------|-----------------|
| UC2:1 | MUA | Lock state without intention to ever unlock it. | Low | Medium | Low | Don't share Vault API keys; automatically unlock resources after a set timeout |
| UC2:1 | MUA | Exhaust Vault disk space by writing huge lock data | Low | Medium | Low | Restrict maximum lock data size |
| UC2:2 | CTA | Exhaust Vault disk space by writing huge lock data | Low | Medium | Low | Restrict maximum lock data size; ensure dependencies are minimal, trustworthy, and up to date |
| UC2:5 | UIA | Eavesdrop on traffic to obtain secrets from state | High | Low | High | Use TLS to protect traffic |
| UC2:5 | MUA | Exhaust Vault disk space by writing huge state | Low | Medium | Low | Restrict maximum state size |
| UC2:5 | MUA | Write malicious state to Vault to steal secrets if deployed | High | Medium | High | Use mTLS, log accesses |
| UC2:5 | LNA | Leak secrets obtained from state | High | Low | High | Filter outbound traffic |
| UC2:6 | CTA | Write malicious state to Vault to steal secrets if deployed | High | Low | High | Deploy IDS to increase chance of detection; ensure dependencies are minimal, trustworthy, and up to date |
| UC2:6 | CTA | Exhaust disk space by writing huge state | Low | Low | High | Restrict maximum state size; ensure dependencies are minimal, trustworthy, and up to date |
| UC2:6 | LNA | Eavesdrop on traffic to obtain secrets from state | High | Low | High | Use TLS to protect traffic |
| UC2:6 | CVA | Leak secrets obtained from state | High | Low | High | Filter outbound traffic; ensure Vault is kept up to date |
