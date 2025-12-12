# Node Specifications & Access

## node1
=== CPU ===
CPU(s):                               12
Model name:                           Intel(R) Core(TM) i7-8700 CPU @ 3.20GHz
Thread(s) per core:                   2
Core(s) per socket:                   6
CPU(s) scaling MHz:                   31%

=== RAM ===
Mem:            31Gi       1.6Gi        28Gi       3.4Mi       1.5Gi        29Gi

=== DISK ===
/dev/sda2       218G  7.4G  200G   4% /

=== OS ===
Distributor ID: Ubuntu
Description:    Ubuntu 24.04.3 LTS
Release:        24.04
Codename:       noble

## node2 (llm)
=== CPU ===
CPU(s):                               20
Model name:                           12th Gen Intel(R) Core(TM) i7-12700T
Thread(s) per core:                   2
Core(s) per socket:                   12
CPU(s) scaling MHz:                   35%

=== RAM ===
Mem:            93Gi       2.2Gi        89Gi        14Mi       3.1Gi        91Gi

=== DISK ===
Primary (OS):
/dev/nvme0n1p2  937G   20G  870G   3% /
  Model: Sabrent (953.9GB NVMe)

Secondary (K8s Workload Storage):
/dev/nvme1n1    476.9GB Samsung MZVPV512HDGL-000H1
  Mountpoint: /mnt/k8s-storage
  Purpose: Dedicated storage for high-I/O workloads (Loki, Vector DB)
  Filesystem: ext4

=== OS ===
Distributor ID: Ubuntu
Description:    Ubuntu 24.04.3 LTS
Release:        24.04
Codename:       noble

## MacBook (Local)
- **kubectl**: Configured, points to 10.0.0.103:6443
- **kubeconfig**: ~/.kube/config
- **SSH config**: ~/.ssh/config has node1, node2 aliases

## Network
- **Subnet**: 10.0.0.0/24
- **Gateway**: 10.0.0.1
- **DNS**: [your DNS]

## Access Patterns

### SSH to nodes
```bash
ssh node1  # or ssh 10.0.0.102
ssh node2  # or ssh 10.0.0.103
```

### kubectl from Mac
```bash
kubectl get nodes  # uses ~/.kube/config
```

### loki datasource
http://loki.logging.svc.cluster.local:3100/