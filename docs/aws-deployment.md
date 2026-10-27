# Learn AWS by deploying this application

This guide prepares a single-server, password-protected demo. No AWS resources were created during development. Run the local application first, then work through these steps deliberately; `terraform apply` creates chargeable resources.

## What each piece does

| Piece | Purpose |
| --- | --- |
| Docker image | Packages Python, the app and a pinned CPU embedding model |
| ECR | Private AWS registry where the image is stored |
| EC2 | Virtual server that runs the container |
| EBS | Encrypted disk containing Docker's persistent SQLite volume |
| Security group | Allows web traffic on 80/443; no public SSH or app port |
| IAM instance role | Lets the server pull this image and use Systems Manager without stored AWS keys |
| Systems Manager | Browser/CLI administration of the server |
| Caddy | HTTPS certificates, HTTP-to-HTTPS redirect and reverse proxy |
| Terraform | Creates and records infrastructure from the files in `infra/aws/` |

The design deliberately uses one EC2 server and one application worker. A server failure causes downtime. A named Docker volume survives container replacement but not instance termination or disk loss. This is a learning/demo architecture, not a highly available multi-user deployment.

## 1. Prepare your account and tools

Use an IAM/Identity Center identity with permission to provision the resources in `infra/aws/main.tf`, not the account root credentials. Configure AWS CLI access locally, preferably via SSO, and verify the intended account:

```powershell
aws sso login --profile YOUR_PROFILE
$env:AWS_PROFILE = "YOUR_PROFILE"
aws sts get-caller-identity
```

Install AWS CLI v2, Terraform 1.6+ and Docker Desktop with Linux containers. The repository does not contain AWS credentials. Do not put credentials or Terraform state in Git. Create an AWS budget and check current pricing for Sydney EC2, EBS, public IPv4, data transfer and ECR storage before proceeding. A `t3.medium` is a starting point for model memory, not a load-tested sizing guarantee. Standard CPU credits cap burst behaviour rather than enabling unlimited-credit charges.

You also need a DNS hostname you control, such as `analyser.yourdomain.com`, for HTTPS. Registration/DNS costs are separate. You can learn infrastructure setup without a domain, but do not send a production password over a plain HTTP public IP.

## 2. Build and test the image locally

Commit the desired code version first. From the repository root:

```powershell
docker compose up --build -d
```

Open http://127.0.0.1:8000, try both search methods, review a link candidate, and check overlap. Inspect logs with `docker compose logs app`. Stop the local container with `docker compose down` when done. The image build downloads CPU PyTorch and the pinned model; allow time and disk space.

## 3. Review and create infrastructure

```powershell
cd infra/aws
terraform init
terraform plan -out deployment.tfplan
```

Read the plan. It creates a VPC, public subnet, gateway, route table, web-only security group, IAM roles, an EC2 server, encrypted root disk, Elastic IP and ECR repository. It does not set your application password or deploy your code.

When you choose to incur those charges:

```powershell
terraform apply deployment.tfplan
terraform output
```

Keep the ignored Terraform state securely; it is needed for updates and cleanup. For team use, configure an access-controlled remote state backend before sharing infrastructure ownership. User-data installs Docker and a checksum-verified Compose plugin. Allow a few minutes for the instance to boot.

## 4. Push an immutable image to ECR

Still in `infra/aws`:

```powershell
$ecrRepository = terraform output -raw ecr_repository_url
$instanceId = terraform output -raw instance_id
$serverIp = terraform output -raw public_ip
$awsRegion = "ap-southeast-2"
$releaseTag = git rev-parse --short HEAD
$imageUri = "${ecrRepository}:${releaseTag}"
$registryHost = ($ecrRepository -split '/')[0]
aws ecr get-login-password --region $awsRegion | docker login --username AWS --password-stdin $registryHost
cd ../..
docker build --platform linux/amd64 -t $imageUri .
docker push $imageUri
```

The ECR repository uses immutable tags, so an existing tag cannot be overwritten. Use a new committed release tag for each update. Keep an earlier working image for rollback. The EC2 role can pull only from this repository; it does not have push permissions.

## 5. Point DNS to the server

Create an A record for your hostname pointing to `$serverIp`. Wait for DNS resolution. Ports 80 and 443 are open for certificate validation and HTTPS; port 8000 and SSH are not public. Caddy handles certificates after the application becomes healthy.

## 6. Connect through Systems Manager

In AWS Console, select the instance and choose Connect → Session Manager, or use the command from `terraform output -raw ssm_command`. CLI sessions require the Session Manager plugin. The instance role and agent provide administration without an inbound SSH rule.

Inside the server's Linux shell, substitute your actual repository URI, release tag and hostname:

```bash
export AWS_REGION=ap-southeast-2
export IMAGE=123456789012.dkr.ecr.ap-southeast-2.amazonaws.com/semantic-content-analyser:YOUR_RELEASE_TAG
export DOMAIN=analyser.yourdomain.com
REGISTRY="${IMAGE%%/*}"
aws ecr get-login-password --region "$AWS_REGION" | sudo docker login --username AWS --password-stdin "$REGISTRY"
sudo docker pull "$IMAGE"
```

Deployment files are bundled in the image, so the instance does not need access to your private GitHub repository:

```bash
PACKAGE=$(sudo docker create "$IMAGE")
sudo docker cp "$PACKAGE":/app/deploy/aws/. /opt/semantic/
sudo docker rm "$PACKAGE"
cd /opt/semantic
sudo bash deploy.sh "$IMAGE" "$DOMAIN"
```

On first deployment the helper prompts for a 16+ character password using letters, numbers, underscores or hyphens. Input is hidden. It generates a signing secret and writes a root-only `.env`; it does not print secrets. `release.env` records the image and domain. Later deployments retain the password, signing key, SQLite volume and certificates.

The helper starts the application and Caddy. Open **https://your-hostname**, sign in and verify search, link exclusions and a saved editorial decision. Production cookies are HTTPS-only and expire after eight hours. No end-user text is sent to Hugging Face for inference; the Docker image already contains the model and uses offline model access.

## 7. Verify and operate

```bash
cd /opt/semantic
sudo docker compose --project-name semantic --env-file .env --env-file release.env -f compose.production.yaml ps
sudo docker compose --project-name semantic --env-file .env --env-file release.env -f compose.production.yaml logs --tail 100 app
```

Check `/health` for process/database health. A healthy process is not a full quality or latency check; also run a real query after deployment. Docker logs rotate at 10 MB with three files per service. The app logs request paths/statuses rather than article text or passwords. Set up external HTTPS uptime monitoring and CPU/memory/disk alerts for any ongoing use; this first template does not automatically configure those services.

The workspace password protects one shared collection. It does not provide individual accounts, tenant isolation, password recovery or an administrative audit trail. Treat imported data according to your own authorisation and retention requirements.

## 8. Back up before replacing or terminating the server

Article CSV export is useful but does not contain saved review decisions. Make a consistent SQLite backup through SQLite's backup API rather than copying a database while its WAL is active:

```bash
cd /opt/semantic
sudo docker compose --project-name semantic --env-file .env --env-file release.env -f compose.production.yaml exec -T app python -c "import sqlite3; source=sqlite3.connect('/app/runtime/workspace.sqlite3'); target=sqlite3.connect('/app/runtime/backup.sqlite3'); source.backup(target); target.close(); source.close()"
APP_CONTAINER=$(sudo docker compose --project-name semantic --env-file .env --env-file release.env -f compose.production.yaml ps -q app)
sudo docker cp "$APP_CONTAINER":/app/runtime/backup.sqlite3 /opt/semantic/backup.sqlite3
```

Copy the backup to protected off-instance storage, such as your own encrypted S3 bucket, before terminating/replacing EC2. Keep root-only `.env` and Caddy certificate data backed up securely as appropriate. Establish scheduled backups and test recovery before relying on the application for important data. No backup schedule is configured automatically.

To restore, stop the app, copy the backup into its volume as `workspace.sqlite3`, preserve UID 10001 ownership and remove stale WAL/SHM files while the app is stopped. Start the app and verify articles and decisions. Practise this with disposable data before a real recovery.

## 9. Update and roll back

Build/push a new immutable release image, then repeat the image pull, deployment-file extraction and `deploy.sh` command with the new tag. Back up first. To roll back, run the helper with the previous known-good image tag. Schema migrations and cross-version data compatibility would need separate planning if the database format changes in a future release.

The root EBS disk is deleted when the instance terminates, and Terraform can replace the instance after user-data changes. A named Docker volume does not protect against either event. Check every infrastructure plan for replacements.

## 10. Clean up charges when finished

Back up/export anything you want to keep. From `infra/aws`, review `terraform plan -destroy`, then intentionally run `terraform destroy`. The ECR repository has `force_delete=false`, so Terraform will refuse to delete a non-empty repository: explicitly remove only the release images you no longer need in ECR, then retry. Remove your DNS record and review retained snapshots, images, storage and any other resources outside this Terraform stack. Stopping EC2 alone does not stop EBS, public IPv4 or registry-storage charges.

## Official references

- [EC2 concepts](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/concepts.html)
- [Systems Manager sessions](https://docs.aws.amazon.com/systems-manager/latest/userguide/session-manager.html)
- [Push a private ECR image](https://docs.aws.amazon.com/AmazonECR/latest/userguide/docker-push-ecr-image.html)
- [Terraform AWS infrastructure tutorial](https://developer.hashicorp.com/terraform/tutorials/aws-get-started/aws-create)
- [FastAPI Docker deployment](https://fastapi.tiangolo.com/deployment/docker/)

## Verification boundary

The application and Terraform configuration were tested locally; no AWS plan/apply or production deployment was run. Docker was unavailable on the original Windows machine, so the image-build and container smoke checks are provided in GitHub Actions but were not executed locally. Validate the image and review the AWS plan in your environment before paying for resources.
