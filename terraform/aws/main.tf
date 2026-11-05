terraform {
  required_version = ">= 1.6, < 2.0"
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 6.0" }
  }
}

provider "aws" {
  region = var.region
  default_tags { tags = { Project = "atlasops", Environment = "learning" } }
}

variable "region" {
  type    = string
  default = "eu-west-1"
}
variable "admin_cidr" {
  description = "Your public IPv4 address followed by /32. SSH only; no public dashboards."
  type        = string
  validation {
    condition     = can(cidrnetmask(var.admin_cidr)) && endswith(var.admin_cidr, "/32")
    error_message = "Supply a single IPv4 /32, never 0.0.0.0/0."
  }
}
variable "ssh_public_key" {
  description = "Public key text, not a private key."
  type        = string
  validation {
    condition     = can(regex("^ssh-(ed25519|rsa) ", var.ssh_public_key))
    error_message = "Supply an OpenSSH ed25519 or RSA public key."
  }
}
variable "instance_type" {
  type    = string
  default = "t3.large"
}

data "aws_ami" "ubuntu" {
  most_recent = true
  owners      = ["099720109477"]
  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd-gp3/ubuntu-noble-24.04-amd64-server-*"]
  }
  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
  filter {
    name   = "architecture"
    values = ["x86_64"]
  }
}
resource "aws_vpc" "lab" {
  cidr_block           = "10.42.0.0/16"
  enable_dns_hostnames = true
}
resource "aws_subnet" "lab" {
  vpc_id                  = aws_vpc.lab.id
  cidr_block              = "10.42.1.0/24"
  map_public_ip_on_launch = true
}
resource "aws_internet_gateway" "lab" { vpc_id = aws_vpc.lab.id }
resource "aws_route_table" "lab" {
  vpc_id = aws_vpc.lab.id
  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.lab.id
  }
}
resource "aws_route_table_association" "lab" {
  subnet_id      = aws_subnet.lab.id
  route_table_id = aws_route_table.lab.id
}
resource "aws_security_group" "lab" {
  name_prefix = "atlasops-"
  description = "SSH from one administrator IP; use local tunnels for the lab"
  vpc_id      = aws_vpc.lab.id
  ingress {
    description = "Administrator SSH"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = [var.admin_cidr]
  }
  egress {
    description = "Package downloads and container image pulls"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}
resource "aws_key_pair" "lab" {
  key_name_prefix = "atlasops-"
  public_key      = var.ssh_public_key
}
resource "aws_instance" "lab" {
  ami                    = data.aws_ami.ubuntu.id
  instance_type          = var.instance_type
  subnet_id              = aws_subnet.lab.id
  vpc_security_group_ids = [aws_security_group.lab.id]
  key_name               = aws_key_pair.lab.key_name
  metadata_options {
    http_tokens                 = "required"
    http_put_response_hop_limit = 1
  }
  root_block_device {
    volume_size           = 40
    volume_type           = "gp3"
    encrypted             = true
    delete_on_termination = true
  }
  tags       = { Name = "atlasops-lab" }
  depends_on = [aws_route_table_association.lab]
}
output "public_ip" { value = aws_instance.lab.public_ip }
output "ami_id" { value = data.aws_ami.ubuntu.id }
output "ssh_command" { value = "ssh ubuntu@${aws_instance.lab.public_ip}" }
