# DevOps Microservices

## What Is This Project

This is a production-grade DevOps project. The application is a simple Product Catalog system built with three independent microservices. The application code is already written for you. Your job as the student is to build everything around it — the infrastructure, the containers, the orchestration, the pipeline, and the monitoring.

This is exactly what a DevOps engineer does at a real company. The developers write the code. You make it run reliably, automatically, and at scale on real cloud infrastructure.

## How the Three Services Work Together

The system has three services and they communicate in a specific way. Understanding this communication is essential before you touch anything.

**auth-service** is the only service that knows about users and passwords. It owns the `users` table in the database. No other service reads or writes to that table. When a user logs in it returns a JWT token. When a user registers it stores a hashed password — never a plain text password.

**api-service** is the only service that knows about products. It owns the `products` table in the database. It does not know anything about users or authentication. It trusts that if a request reaches it, it is allowed.

**frontend-service** is the only service that the browser talks to. It never touches the database directly. When the browser asks for the products page, the frontend-service calls the api-service internally and returns the result to the browser. When the browser logs in, the frontend-service sends the credentials to the auth-service and stores the JWT token in a browser cookie.

The flow for a user visiting the products page looks like this:

```
Browser
  → requests /products from frontend-service
    → frontend-service calls api-service /products internally
      → api-service queries PostgreSQL products table
      → api-service returns product list as JSON
    → frontend-service renders products.html with that data
  → Browser sees the products page
```

The flow for a user logging in looks like this:

```
Browser
  → submits email and password to frontend-service /login
    → frontend-service sends credentials to auth-service /auth/login
      → auth-service checks password against database
      → auth-service returns JWT token
    → frontend-service stores token in browser cookie
  → Browser is redirected to /products
```

No service ever calls the database of another service. No service ever exposes its database connection string to another service. This is the boundary rule and it must never be broken.

## What You Have to Build

The application code is done. Everything below is your responsibility.

### 1. Dockerfiles

Write a Dockerfile for each of the three services. Each Dockerfile must use a multi-stage build. The first stage installs dependencies. The second stage is the production image and must not contain pip, gcc, or any build tools. Each service must run as a non-root user inside the container. Test locally by running `docker build` in each service folder and making sure the image builds without errors.

### 2. AWS Infrastructure with Terraform

Write all Terraform code to provision the following on AWS. Everything must be in code — nothing clicked manually in the AWS console.

- A VPC with CIDR `10.0.0.0/16`
- Two public subnets across two availability zones for the load balancer
- Two private subnets across two availability zones for Kubernetes nodes and Jenkins
- Two isolated subnets for RDS
- An Internet Gateway attached to the VPC
- A NAT Instance (`t2.micro`) in the public subnet with `source_dest_check` disabled so private subnets can reach the internet
- Route tables connecting each subnet tier to the correct gateway
- Security groups with least privilege rules — ALB accepts internet traffic, K8s nodes only accept traffic from ALB, RDS only accepts traffic from K8s nodes
- Three `t3.medium` EC2 instances for Kubernetes (one master two workers) in private subnets
- One `t3.small` EC2 instance for Jenkins in the private subnet
- One RDS PostgreSQL `db.t3.micro` instance in the isolated subnets with single-AZ to save cost
- One Application Load Balancer in the public subnets
- Three ECR repositories one per service
- One S3 bucket for assets
- Store Terraform state in S3 with DynamoDB locking

### 3. Kubernetes Cluster

Set up a self-managed Kubernetes cluster on your EC2 instances using `kubeadm`. Do not use EKS. Write Kubernetes manifests for the following.

- A Namespace called `capstone`
- A Deployment for each service with 2 replicas rolling update strategy `maxUnavailable 0` liveness and readiness probes pointing to `/health` resource requests and limits and `imagePullSecrets` for ECR
- A NodePort Service for `api-service` on port `30001` and `frontend-service` on port `30080`
- A ClusterIP Service for `auth-service` since it only needs to be reachable internally
- A HorizontalPodAutoscaler for each service scaling between 2 and 6 replicas based on CPU
- A ServiceMonitor so Prometheus automatically discovers and scrapes your services

### 4. Jenkins CI/CD Pipeline

Install Jenkins on the Jenkins EC2 instance. Write a Jenkinsfile that does the following automatically every time code is pushed to the main branch on GitHub.

- Runs tests for `api-service` and `auth-service` in parallel
- Builds Docker images for all three services
- Tags each image with the Git commit SHA
- Pushes all images to ECR
- Updates the image tag in the Kubernetes manifests
- Runs `kubectl apply` to deploy to the cluster
- Waits for the rollout to complete
- Runs a smoke test by curling the health endpoints

### 5. Domain and SSL

Buy a domain. Point its nameservers to Route 53. Request an SSL certificate through ACM using DNS validation. Set up CloudFront as the CDN in front of your ALB. Set up Route 53 records pointing your domain to CloudFront. All of this must be written in Terraform.

### 6. Monitoring

Install the `kube-prometheus-stack` using Helm inside your Kubernetes cluster. Import the following Grafana dashboards: Kubernetes Cluster Overview (ID 7249), Node Exporter Full (ID 1860), and PostgreSQL Overview (ID 9628). Build a custom Grafana dashboard manually using the Prometheus metrics that the FastAPI services expose on their `/metrics` endpoints.

### 7. Presentation Slides

Write a technical documentation page that explains how all the DevOps tools work together — Jenkins, Docker, Kubernetes, Terraform, Prometheus, Grafana, and GitHub — the exact flow from a developer pushing code to it being live on the infrastructure, what each tool does at each step and how it hands off to the next. Include a full AWS architecture diagram showing the VPC, all subnet tiers, EC2 instances, RDS, ALB, CloudFront, Route 53, NAT instance, Internet Gateway, ECR, and S3 with arrows showing how traffic flows through the system.

## The Flow From Start to Finish

Follow this order exactly. Do not skip ahead.

### Step 1 — Run locally first

Run `docker-compose up` and make sure all three services start, you can reach the frontend at `localhost:8080`, you can register a user, login, and see the products page. All tests must pass with `pytest` before you move on.

### Step 2 — Write the Dockerfiles

Write a Dockerfile for each service. Build each image locally. Run each container individually and verify the `/health` endpoint responds. Then run `docker-compose up` with your Dockerfiles and confirm everything still works.

### Step 3 — Set up AWS

Configure your AWS CLI. Create the S3 bucket and DynamoDB table for Terraform state manually. Then write and apply your Terraform code phase by phase — VPC first, then compute, then RDS, then ALB.

### Step 4 — Set up Kubernetes

SSH into your EC2 instances. Install `kubeadm` on all nodes. Initialize the master. Join the workers. Install Calico. Create the ECR pull secret and database secret. Apply all your Kubernetes manifests.

### Step 5 — Push images to ECR

Build all three Docker images and push them to your ECR repositories. Verify the images appear in ECR.

### Step 6 — Verify the deployment

Check all pods are running. Check the ALB health checks are passing. Access your application through the ALB DNS name.

### Step 7 — Set up Jenkins

Install Jenkins on the Jenkins EC2. Install required plugins. Add your AWS credentials and kubeconfig. Create the pipeline job connected to your GitHub repo. Set up the GitHub webhook. Push a code change and watch the full pipeline run automatically.

### Step 8 — Domain and CloudFront

Apply the Terraform for Route 53 and CloudFront. Validate your ACM certificate. Confirm your application is accessible on your real domain with HTTPS.

### Step 9 — Monitoring

Install Helm. Deploy `kube-prometheus-stack`. Access Grafana through an SSH tunnel. Import the community dashboards. Build your custom FastAPI metrics dashboard.

### Step 10 — Presentation

Generate your slides. Replace every placeholder with real values from your actual running system. Practice your live demo at least three times before presenting.

## What the Final Project Must Have

By the end you must be able to demonstrate all of the following:

- The application running live on your real domain with HTTPS
- A `git push` that triggers Jenkins automatically and deploys to Kubernetes within 5 minutes with zero downtime
- `kubectl get pods` showing all pods healthy across both worker nodes
- The HPA scaling pods up under load and back down after
- Grafana dashboards showing real metrics from your running pods
- Terraform state in S3 showing all infrastructure managed as code
- ECR repositories containing images tagged with real Git commit SHAs
- A professional 22-slide presentation explaining every component and a live demo during the presentation

## Cost Management

Stop your EC2 instances and RDS every evening when you finish working. Write a `stop-all.sh` script that stops all instances tagged with your project name and stops the RDS instance. Write a `start-all.sh` script that starts everything back up. Running the infrastructure all day every day costs around $75 per month. Stopping it when not in use brings it down significantly.

Never commit your AWS credentials, database passwords, or JWT secret keys to GitHub. The `.gitignore` handles most cases but double check before every push.

## Local Development

To run everything locally:

```
docker-compose up --build
```

Frontend available at <http://localhost:8080>
API available at <http://localhost:8000>
Auth available at <http://localhost:8001>

To run tests:

```
cd services/api-service && pytest tests/ -v
cd services/auth-service && pytest tests/ -v
```
