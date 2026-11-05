# Cloud and Kubernetes extensions

These extensions are source-complete learning exercises. They were not applied to your accounts or cluster. The Compose project is the main reference implementation.

## Terraform: a dedicated AWS VM

Terraform owns cloud resources; Ansible owns OS package configuration; Compose owns containers. Do not also manage those same containers with a Terraform Docker provider.

Prerequisites: an AWS account, authorized short-lived credentials, Terraform 1.6+, an SSH key, and an explicit budget. Set an AWS billing alert in your account before provisioning. EC2, EBS, public IPv4 and traffic can incur charges; no free-tier promise is made. An apply requires your own deliberate action. The default `t3.large` is intended for core/monitoring; consider a 16 GB instance for ELK.

```bash
cd terraform/aws
cp terraform.tfvars.example terraform.tfvars
# Edit: admin_cidr must be your public IPv4/32; provide your PUBLIC SSH key.
terraform init
terraform fmt -check
terraform validate
terraform plan -out=lab.tfplan
# Review every resource and expected cost before your optional apply:
terraform apply lab.tfplan
terraform output -raw public_ip
```

The module creates an isolated VPC/subnet, a default route through an Internet Gateway, a security group allowing SSH from one `/32`, a key pair and a VM with encrypted root storage and IMDSv2 required. The Ubuntu image is selected from Canonical's owner account. The selected AMI ID is output; pin that ID in a future immutable environment instead of always selecting the most recent image.

Only port 22 is reachable from your allowed source. No application, Vault, database or dashboard port is opened publicly. The VM uses outbound internet access to install packages and pull images. There is no NAT Gateway, managed database or load balancer in this small module.

Terraform state is local for this exercise and is ignored by Git. Keep it securely; it may contain sensitive infrastructure metadata. Teams should use a secured remote backend with encryption, locking and controlled access. Do not put API keys or Vault secrets into Terraform variables and assume `sensitive = true` keeps them out of state.

## Ansible: prepare the host

Install Ansible in a local virtual environment (`pip install ansible-core`). Copy `ansible/inventory.example.ini` to `ansible/inventory.ini`, replace host/user/key values, and verify SSH host identity independently. Host-key checking is not disabled.

```bash
ansible-playbook -i ansible/inventory.ini ansible/playbook.yml --syntax-check
ansible-playbook -i ansible/inventory.ini ansible/playbook.yml
```

The playbook targets a dedicated Ubuntu 22.04/24.04 amd64 host. It installs base utilities, configures Docker's signed apt repository, installs Engine/Compose, enables Docker and adds the SSH user to the Docker group. This group is root-equivalent. Reconnect SSH after it changes. A second run should largely report `ok`; inspect any changes rather than promising zero changes while package metadata evolves.

Copy only clean source to the VM; generate fresh secrets there. For example, create a clean source archive using Git, transfer it with `scp`, extract into `~/atlasops`, then run `make up`. Do not copy your local `.secrets`, backups, `.env` or Terraform state into a public repository.

```bash
# Local repository; requires an initial Git commit:
git archive --format=tar.gz --output=/tmp/atlasops-source.tar.gz HEAD
scp /tmp/atlasops-source.tar.gz ubuntu@VM_IP:~/
# On the VM:
mkdir -p ~/atlasops
tar -xzf ~/atlasops-source.tar.gz -C ~/atlasops
cd ~/atlasops
make up
```

Use tunnels from your laptop. Stop your local Compose stack first if those local ports are occupied:

```bash
ssh -N -L 8443:127.0.0.1:8443 -L 3000:127.0.0.1:3000 \
  -L 9090:127.0.0.1:9090 ubuntu@VM_IP
```

The browser then uses the VM's certificate through `https://localhost:8443`. For curl from your laptop, copy only the VM's public certificate and trust that file explicitly. Retrieve the VM's generated client key through your private SSH session. This is a private demo VM, not a public website deployment.

When finished, take any required off-host backups and review `terraform plan -destroy`. `terraform destroy` permanently removes the lab VM and its root disk/data. Run it only for this dedicated lab after deciding what to preserve. No destroy action has been performed by this project generator.

## Kubernetes: migrate the application to kind

Install Docker, kind and kubectl from their official sites. Run:

```bash
make k8s-up
kubectl --context kind-atlasops -n atlasops port-forward \
  --address 127.0.0.1 svc/api 8088:8000
```

Open `http://localhost:8088` and use `.secrets/api-key`. All commands target the named `kind-atlasops` context. This separate cluster has its own PostgreSQL data volume; your Compose tasks will not appear there.

The exercise contains a PostgreSQL StatefulSet with a PVC; a ConfigMap for database initialization; scoped credential volumes; a Deployment; a ClusterIP Service; startup, readiness and liveness probes; nonroot/read-only API settings; resource requests/limits; and a service account token disabled for pods that do not need Kubernetes API access.

After the first successful startup creates schema v1, practice scaling and recovery:

```bash
kubectl --context kind-atlasops -n atlasops scale deployment/api --replicas=2
kubectl --context kind-atlasops -n atlasops get pods
kubectl --context kind-atlasops -n atlasops rollout restart deployment/api
kubectl --context kind-atlasops -n atlasops rollout status deployment/api
```

To learn an image rollout, build a **different tag**, load it with `kind load docker-image IMAGE --name atlasops`, use `kubectl set image deployment/api api=IMAGE`, inspect rollout status, then `kubectl rollout undo deployment/api`. Reloading the same local tag alone does not prove an image change.

The Kubernetes exercise intentionally includes only the app/database migration. It uses a snapshot of the local key in a Kubernetes Secret; it has no live Vault integration, WAF, TLS ingress, metrics stack, log stack, NetworkPolicy enforcement, HPA or multi-node HA. Kubernetes Secrets are not inherently encrypted simply because their YAML representation is base64. Next tasks are Vault Kubernetes auth, an ingress controller, Helm packaging, a metrics collector and appropriate network controls.

`make k8s-down` deletes only the named kind cluster, including its lab database. Preserve anything you care about first.
